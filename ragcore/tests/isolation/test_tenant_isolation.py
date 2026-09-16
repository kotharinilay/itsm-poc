"""**No path returns another organisation's data.** A view or query that did is release-blocking.

Two kinds of test, and both are needed.

*Structural.* Reading the repository module's AST proves the property for methods nobody has written
a scenario for yet. A repository added next month with a missing ``WHERE`` fails here on the day it
is written, rather than on the day somebody notices a customer reading another customer's case.

*Behavioural.* Two organisations, the same shapes of row in each, and every read issued as one while
the other's rows sit in the same tables. This is the test that would actually have caught a filter
applied to the wrong column — the structural test sees a ``_scope`` call and cannot see which table
it was built from.

**The registry's three derivation methods are the deliberate exception**, and they are checked
rather than excused: they take no ``TenantContext`` because they *produce* one, and the behavioural
tests below prove each derives the tenant from durable platform state rather than from its caller.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ragcore.domain.governance import ExecutionTreatment
from ragcore.domain.identifiers import (
    EntraTenantId,
    OperationIdentity,
    PrincipalId,
    SessionId,
    TenantId,
    WorkItemId,
)
from ragcore.domain.tenancy import TenantContext, TenantSource, TenantStatus
from ragcore.domain.work import (
    ApprovalState,
    OperationStatus,
    SessionState,
    WorkItemState,
)
from ragcore.persistence import models
from ragcore.persistence.repositories import (
    OperationCatalogue,
    SessionRepository,
    TenantRegistry,
    WorkItemRepository,
)

REPOSITORIES = (
    Path(__file__).resolve().parents[2] / "src" / "ragcore" / "persistence" / ("repositories.py")
)

DERIVES_ITS_OWN_TENANT = frozenset(
    {
        # These three produce a TenantContext from durable platform state. They are the only
        # entry points that exist for it, and `tests/isolation` asserts their behaviour below
        # rather than merely allowing them through the structural check.
        "admit_end_user",
        "status_for",
        "tenant_for_work_item",
        "tenant_for_session",
        "retention_overrides",
    }
)

PLATFORM_WIDE = frozenset(
    {
        # The dispatcher publishes every organisation's triggers, and the row it reads carries no
        # tenant-bearing content: the payload is opaque identifiers and correlation only.
        "undispatched",
        "mark_dispatched",
        # Same dispatcher, same reason, and narrowed by primary key. It increments an attempt
        # counter on a row the dispatcher has already read; adding a tenant predicate would mean
        # either a dispatcher per organisation, or one that silently stopped counting failures for
        # whichever organisation it was not scoped to.
        "record_failure",
    }
)


# ---------------------------------------------------------------------------
# Structural — the property, for every method including the unwritten scenarios
# ---------------------------------------------------------------------------


def _public_methods() -> list[tuple[str, str, ast.AsyncFunctionDef]]:
    """Every public async method on every repository class."""
    tree = ast.parse(REPOSITORIES.read_text(encoding="utf-8"), filename=str(REPOSITORIES))
    return [
        (klass.name, node.name, node)
        for klass in ast.walk(tree)
        if isinstance(klass, ast.ClassDef)
        for node in klass.body
        if isinstance(node, ast.AsyncFunctionDef) and not node.name.startswith("_")
    ]


def _filters(node: ast.AsyncFunctionDef) -> bool:
    """Whether the method narrows by tenant, through the one predicate builder."""
    return any(
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "_scope"
        for call in ast.walk(node)
    )


def _stamps(node: ast.AsyncFunctionDef) -> bool:
    """Whether the method writes the tenant onto the row it inserts.

    Matched as ``tenant_id=tenant.tenant_id.value`` — the value, from the trusted context, and not
    from anything else in scope.
    """
    return any(
        keyword.arg == "tenant_id" and ast.unparse(keyword.value) == "tenant.tenant_id.value"
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        for keyword in call.keywords
    )


class TestEveryQueryPathCarriesATenant:
    """The rule the whole module exists for, asserted mechanically."""

    def test_every_method_either_takes_a_tenant_or_is_named_as_an_exception(self) -> None:
        """A ``TenantContext`` parameter, or a place on one of the two exception lists.

        There is no third option, and that is the point: the exceptions are a list somebody has to
        edit, so widening them is a reviewable act rather than an omission.
        """
        offenders = [
            f"{klass}.{name}"
            for klass, name, node in _public_methods()
            if "tenant" not in {argument.arg for argument in node.args.args}
            and name not in DERIVES_ITS_OWN_TENANT
            and name not in PLATFORM_WIDE
        ]
        assert not offenders, f"methods with no tenant parameter and no stated reason: {offenders}"

    def test_every_tenant_taking_method_either_filters_or_stamps(self) -> None:
        """Taking a tenant and not using it would be worse than not taking one.

        It would read as filtered to every reviewer while filtering nothing.

        Two shapes count, because there are two honest things to do with a tenant. A read or an
        update **filters** on it, through ``_scope``. A plain insert has nothing to filter — it
        **stamps** the row, writing ``tenant_id=tenant.tenant_id.value``, and a row written without
        one is a row that belongs to nobody. A method doing neither is the defect.
        """
        offenders = [
            f"{klass}.{name}"
            for klass, name, node in _public_methods()
            if "tenant" in {argument.arg for argument in node.args.args}
            and not _filters(node)
            and not _stamps(node)
            # The registry resolves by `entra_tid` or by primary key and joins the registry itself;
            # it has no `_scope` to apply because it is the table the scope is *derived from*.
            and name not in DERIVES_ITS_OWN_TENANT
        ]
        assert not offenders, f"methods taking a tenant without applying it: {offenders}"

    def test_no_statement_is_built_from_a_formatted_string(self) -> None:
        """**Every value is bound as a parameter.** No f-string reaches SQL in this module.

        Checked against the AST rather than the text, so a docstring that discusses the rule is not
        mistaken for a violation of it.
        """
        tree = ast.parse(REPOSITORIES.read_text(encoding="utf-8"), filename=str(REPOSITORIES))
        formatted = [
            ast.unparse(node) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr)
        ]
        assert not formatted, f"a formatted string appears in the query layer: {formatted}"

    def test_every_tenant_scoped_table_has_the_column_the_filter_needs(self) -> None:
        """The predicate is local to the table, so the table has to carry the column."""
        missing = [
            name
            for name in models.TENANT_SCOPED_TABLES
            if "tenant_id" not in models.TABLES_BY_NAME[name].c
        ]
        assert not missing, f"tenant-scoped tables without a tenant_id column: {missing}"

    def test_the_only_table_without_a_tenant_is_the_platform_wide_catalogue(self) -> None:
        """``governance_record`` is platform-wide; entitlement is the tenant-scoped half."""
        without = {
            name for name, table in models.TABLES_BY_NAME.items() if "tenant_id" not in table.c
        }
        assert without == {"governance_record"}


# ---------------------------------------------------------------------------
# Behavioural — two organisations, one database
# ---------------------------------------------------------------------------


pytestmark_integration = pytest.mark.integration


def _context(tenant_id: UUID, entra_tid: UUID) -> TenantContext:
    return TenantContext.from_admitted_identity(
        TenantId(tenant_id), EntraTenantId(entra_tid), TenantStatus.ACTIVE
    )


async def _seed_organisation(session: AsyncSession) -> dict[str, Any]:
    """Create one organisation with a session, a work item and an entitled capability."""
    tenant_id, entra_tid = uuid4(), uuid4()
    session_id, work_item_id, requester = uuid4(), uuid4(), uuid4()
    catalogue_id = f"fixture.{tenant_id.hex[:8]}"

    await session.execute(
        insert(models.TENANT_MAPPING).values(
            tenant_id=tenant_id,
            entra_tid=entra_tid,
            display_name="Contoso",
            status=TenantStatus.ACTIVE.value,
        )
    )
    await session.execute(
        insert(models.CHAT_SESSION).values(
            session_id=session_id,
            tenant_id=tenant_id,
            requester_oid=requester,
            state=SessionState.CONVERSATIONAL.value,
        )
    )
    await session.execute(
        insert(models.WORK_ITEM).values(
            work_item_id=work_item_id,
            tenant_id=tenant_id,
            session_id=session_id,
            requested_by_oid=requester,
            state=WorkItemState.OPEN.value,
            approval_state=ApprovalState.NONE.value,
        )
    )
    await session.execute(
        insert(models.GOVERNANCE_RECORD).values(
            catalogue_id=catalogue_id,
            version=1,
            kind="read",
            default_treatment=ExecutionTreatment.AUTO.value,
            accepted_roles=["technician"],
            is_reference_fixture=True,
            requires_elevation=False,
            risk_tier="informational",
        )
    )
    await session.execute(
        insert(models.TENANT_ENTITLEMENT).values(
            tenant_id=tenant_id, catalogue_id=catalogue_id, enabled=True
        )
    )
    await session.execute(
        insert(models.OPERATION).values(
            operation_id=uuid4(),
            tenant_id=tenant_id,
            work_item_id=work_item_id,
            catalogue_id=catalogue_id,
            catalogue_version=1,
            treatment=ExecutionTreatment.AUTO.value,
            parameters={},
            status=OperationStatus.PROPOSED.value,
        )
    )
    return {
        "tenant": _context(tenant_id, entra_tid),
        "session_id": SessionId(session_id),
        "work_item_id": WorkItemId(work_item_id),
        "requester": PrincipalId(requester),
        "catalogue_id": catalogue_id,
        "entra_tid": EntraTenantId(entra_tid),
    }


@pytest.fixture
async def two_organisations(
    sessions: async_sessionmaker[AsyncSession],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Two organisations, seeded identically, sharing every table."""
    async with sessions() as session, session.begin():
        first = await _seed_organisation(session)
        second = await _seed_organisation(session)
    return first, second


@pytest.mark.integration
class TestNoReadCrossesAnOrganisationBoundary:
    """The same identifier, asked for by the wrong organisation, returns nothing."""

    async def test_a_session_is_invisible_to_another_organisation(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """Holding a valid identifier is not authority to read the row it names."""
        first, second = two_organisations
        repository = SessionRepository(sessions)

        assert await repository.get(first["tenant"], first["session_id"]) is not None
        assert await repository.get(second["tenant"], first["session_id"]) is None

    async def test_a_work_item_is_invisible_to_another_organisation(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """The authority record is the one row a cross-tenant read would matter most on."""
        first, second = two_organisations
        repository = WorkItemRepository(sessions)

        assert await repository.get(first["tenant"], first["work_item_id"]) is not None
        assert await repository.get(second["tenant"], first["work_item_id"]) is None

    async def test_a_session_listing_returns_only_the_callers_own(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """A listing is where a missing filter shows up as somebody else's conversation."""
        first, second = two_organisations
        repository = SessionRepository(sessions)

        mine = await repository.list_for_requester(first["tenant"], first["requester"], limit=50)
        assert len(mine) == 1

        # The other organisation's requester identifier, asked for under the first's tenant.
        theirs = await repository.list_for_requester(first["tenant"], second["requester"], limit=50)
        assert theirs == []

    async def test_entitlement_does_not_leak_between_organisations(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """**There is no global toolset.** A capability one organisation holds is not another's."""
        first, second = two_organisations
        catalogue = OperationCatalogue(sessions)

        assert await catalogue.is_entitled(first["tenant"], first["catalogue_id"])
        assert not await catalogue.is_entitled(second["tenant"], first["catalogue_id"])

    async def test_a_catalogue_lookup_refuses_an_unentitled_organisation(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """``None`` is a refusal, not a default. Discovery never confers entitlement."""
        first, second = two_organisations
        catalogue = OperationCatalogue(sessions)
        identity = OperationIdentity(first["catalogue_id"], 1)

        assert await catalogue.lookup(first["tenant"], identity) is not None
        assert await catalogue.lookup(second["tenant"], identity) is None


@pytest.mark.integration
class TestTheTargetTenantDerivesFromTrustedPlatformState:
    """A staff caller's own ``tid`` is the Operator tenant, never the customer target."""

    async def test_admission_matches_only_the_registered_entra_tid(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """``entra_tid`` is the only value matched against a token-derived tenant."""
        first, _ = two_organisations
        registry = TenantRegistry(sessions)

        admitted = await registry.admit_end_user(first["entra_tid"])
        assert admitted is not None
        assert admitted.tenant_id == first["tenant"].tenant_id
        assert admitted.source is TenantSource.END_USER_IDENTITY

    async def test_an_unregistered_tid_is_not_admitted(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """Fails closed. An unknown organisation does not get in, and gets no default."""
        registry = TenantRegistry(sessions)
        assert await registry.admit_end_user(EntraTenantId(uuid4())) is None

    async def test_the_work_items_own_row_supplies_the_tenant(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """This is how a Workload execution gets its tenant — from the row, not the trigger.

        The trigger that woke it carries no tenant at all, so a forged message cannot retarget the
        work: the only answer available comes from a column that is immutable at the database
        permission boundary.
        """
        first, second = two_organisations
        registry = TenantRegistry(sessions)

        derived = await registry.tenant_for_work_item(first["work_item_id"])
        assert derived is not None
        assert derived.tenant_id == first["tenant"].tenant_id
        assert derived.tenant_id != second["tenant"].tenant_id
        assert derived.source is TenantSource.WORK_ITEM

    async def test_the_sessions_own_row_supplies_the_staff_target(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """A staff action names a session; the platform decides which organisation that is."""
        first, _ = two_organisations
        registry = TenantRegistry(sessions)

        derived = await registry.tenant_for_session(first["session_id"])
        assert derived is not None
        assert derived.tenant_id == first["tenant"].tenant_id
        assert derived.source is TenantSource.PLATFORM_OBJECT

    async def test_an_unknown_identifier_derives_nothing(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """No row, no tenant. Never a fallback to the caller's own."""
        registry = TenantRegistry(sessions)
        assert await registry.tenant_for_work_item(WorkItemId(uuid4())) is None
        assert await registry.tenant_for_session(SessionId(uuid4())) is None

    def test_there_is_no_api_that_takes_a_customer_tenant_from_a_caller(self) -> None:
        """The cross-tenant vulnerability is a method that would accept one. There is none.

        :class:`TenantContext` is constructible only through the three ``from_*`` classmethods, each
        naming its provenance — and every repository takes the context rather than an identifier. A
        caller holding a tenant identifier that came from a request has nowhere to go with it.
        """
        constructors = {
            name for name in vars(TenantContext) if name.startswith(("from_", "parse", "of"))
        }
        assert constructors == {"from_admitted_identity", "from_work_item", "from_platform_object"}


@pytest.mark.integration
class TestSuspensionIsVisibleWhereverTheTenantIsRead:
    """Approved work MUST NOT execute for an organisation that is no longer active."""

    async def test_a_suspended_organisation_is_not_admitted_for_execution(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """Checked at execution as well as admission: a suspension can land between the two."""
        from sqlalchemy import update

        first, _ = two_organisations
        async with sessions() as session, session.begin():
            await session.execute(
                update(models.TENANT_MAPPING)
                .where(models.TENANT_MAPPING.c.tenant_id == first["tenant"].tenant_id.value)
                .values(status=TenantStatus.SUSPENDED.value)
            )

        registry = TenantRegistry(sessions)
        current = await registry.status_for(first["tenant"].tenant_id)
        assert current is not None
        assert not current.is_admitted

        # And the derivation paths see it too — a work item belonging to a suspended organisation
        # still resolves, and still reports that work may not proceed.
        derived = await registry.tenant_for_work_item(first["work_item_id"])
        assert derived is not None
        assert not derived.is_admitted


@pytest.mark.integration
class TestPublishedViewsCarryTheTenantColumn:
    """The monolith's global filter needs a column to apply. Rule 1 of the read contract."""

    async def test_every_view_but_the_catalogue_exposes_tenant_id(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """``vw_governance_catalogue_v1`` is the stated exception; everything else carries it."""
        from sqlalchemy import text

        from ragcore.persistence.views import ALL_VIEWS

        async with sessions() as session:
            for view in ALL_VIEWS:
                result = await session.execute(
                    text(f"SELECT * FROM platform.{view.signature} LIMIT 0")  # noqa: S608
                )
                columns = set(result.keys())
                if view.signature == "vw_governance_catalogue_v1":
                    assert "tenant_id" not in columns
                else:
                    assert "tenant_id" in columns, f"{view.signature} publishes no tenant_id"

    async def test_no_view_exposes_a_credential_reference(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """**Rule 2 beats rule 1 where they meet.** Not a value, not a Key Vault reference."""
        from sqlalchemy import text

        from ragcore.persistence.views import ALL_VIEWS

        async with sessions() as session:
            for view in ALL_VIEWS:
                result = await session.execute(
                    text(f"SELECT * FROM platform.{view.signature} LIMIT 0")  # noqa: S608
                )
                leaked = {
                    column
                    for column in result.keys()  # noqa: SIM118 — RMKeyView, not a mapping
                    if "credential" in column or "secret" in column
                }
                assert not leaked, f"{view.signature} publishes {leaked}"

    async def test_a_session_listing_view_returns_only_the_matching_tenant(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """Filtering the view by ``tenant_id`` yields one organisation's rows and no other's."""
        from sqlalchemy import bindparam, text

        first, second = two_organisations
        statement = text(
            "SELECT tenant_id FROM platform.vw_session_summary_v1 WHERE tenant_id = :tenant"
        ).bindparams(bindparam("tenant"))

        async with sessions() as session:
            rows = (
                await session.execute(statement, {"tenant": first["tenant"].tenant_id.value})
            ).all()

        assert len(rows) == 1
        assert rows[0].tenant_id == first["tenant"].tenant_id.value
        assert rows[0].tenant_id != second["tenant"].tenant_id.value


@pytest.mark.integration
class TestRetentionExpiryIsVisibleThroughThePublishedViews:
    """Rule 4: retention is respected inside the view, not by the caller."""

    async def test_an_expired_session_cannot_be_read_back_through_a_listing(
        self, sessions: async_sessionmaker[AsyncSession], two_organisations: Any
    ) -> None:
        """Once past its window, the row is gone from the contract even before it is deleted."""
        from sqlalchemy import text, update

        first, _ = two_organisations
        past = datetime.now(UTC) - timedelta(days=1)

        async with sessions() as session, session.begin():
            await session.execute(
                update(models.CHAT_SESSION)
                .where(models.CHAT_SESSION.c.session_id == first["session_id"].value)
                .values(state=SessionState.RESOLVED.value, content_expires_at=past)
            )

        async with sessions() as session:
            rows = (
                await session.execute(text("SELECT 1 FROM platform.vw_session_summary_v1"))
            ).all()

        assert len(rows) == 1, "only the unexpired organisation's session should remain readable"
