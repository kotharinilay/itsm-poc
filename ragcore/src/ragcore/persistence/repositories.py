"""Repositories. **Every query applies ``tenant_id``, and no method omits it.**

This is the module the tenant-isolation rule lives or dies in (constitution Principle IV,
spec FR-IDENT-008). Three things make it structural rather than disciplined:

1. **Every method that reads or writes tenant-owned rows takes a
   :class:`~ragcore.domain.tenancy.TenantContext`.** Not a ``TenantId``, and not an optional one.
   A ``TenantContext`` can only be built through a ``from_*`` classmethod that names its
   provenance, so a caller holding a tenant identifier that came from a client has nowhere to go.
2. **Every statement starts at :meth:`_TenantScoped._scope`.** The predicate is built from the
   table's own ``tenant_id`` column, so it is local to the table rather than dependent on a join a
   future edit could change. ``tests/isolation/`` reads this module's AST and fails on a method
   that does not use it.
3. **Three methods deliberately take no tenant, and they are the three that *derive* one.**
   :meth:`TenantRegistry.admit_end_user`, :meth:`TenantRegistry.tenant_for_work_item` and
   :meth:`TenantRegistry.tenant_for_session` are the trusted sources a
   :class:`TenantContext` comes from. **A staff caller's own ``tid`` is the Operator tenant and is
   never the customer target**: a staff action resolves its target by reading the durable platform
   object it operates on and taking that row's ``tenant_id``. That is what those two lookups are,
   and they are the only entry points that exist for it.

**Reads do not track.** Every read goes through :func:`~ragcore.persistence.engine.read_session`
and returns rows rather than mapped instances that a later attribute access could lazily reload or
a stray flush could write back — the same reasoning as the monolith's ``AsNoTracking`` default.

**Every value is bound as a parameter.** Predicates are built from column objects and comparisons,
never from formatted SQL. There is no f-string in a statement anywhere in this module, which is the
property ``tests/security/`` asserts.

**No repository commits.** A repository joins the caller's transaction, because the transactional
outbox requires an outbox row to become durable in the same transaction as the state change it
describes. A repository that committed would break that silently.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, Interval, Table, insert, literal, select, true, update
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.functions import func

from ragcore.domain.audit import ActorChain, AuditFacts
from ragcore.domain.decisions import EndUserConsent, StaffVerdict
from ragcore.domain.envelopes import TriggerEnvelope
from ragcore.domain.governance import VerificationOutcome
from ragcore.domain.identifiers import (
    ApprovalId,
    AuditEventId,
    ConsentId,
    CorrelationId,
    EntraTenantId,
    IdempotencyKey,
    OperationId,
    OperationIdentity,
    PrincipalId,
    SessionId,
    TenantId,
    WorkItemId,
)
from ragcore.domain.roles import RoleSet, StaffRole
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.domain.work import ApprovalVerdict, ConsentVerdict, WorkItemState
from ragcore.persistence import enums, models
from ragcore.persistence.concurrency import (
    VersionedRow,
    claim_once,
    guarded_update,
    rows_affected,
)
from ragcore.persistence.engine import current_session, read_session
from ragcore.persistence.retention import RetentionClass, window_for


class _TenantScoped:
    """The shared half of every tenant-owned repository.

    Holds the session factory and the one predicate builder. Deliberately not a generic
    ``Repository[T]``: the constitution prohibits a generic repository, and the reason applies
    directly here — a ``get(id)`` inherited from a base class is a query path with no tenant in it,
    and it would exist on every aggregate at once.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    @staticmethod
    def _scope(tenant: TenantContext, table: Table) -> ColumnElement[bool]:
        """The tenant predicate for ``table``.

        Args:
            tenant: The trusted binding. Its provenance is recorded on the context itself.
            table: The table being queried.

        Returns:
            ``table.tenant_id = :tenant_id``, with the value bound as a parameter.
        """
        return table.c.tenant_id == tenant.tenant_id.value


# ---------------------------------------------------------------------------
# Tenant registry — where a TenantContext comes from, and the only such place
# ---------------------------------------------------------------------------


class TenantRegistry:
    """Platform tenant-registry state. Satisfies
    :class:`~ragcore.application.ports.TenantRegistryPort`.

    **This class is the trusted platform state a tenant binding derives from.** It takes no
    ``TenantContext``, because its callers do not have one yet — that is precisely what they are
    here to obtain. Every other repository in this module takes one and cannot be reached without.

    **Fails closed.** An unknown organisation returns ``None``, which callers treat as *not
    admitted*. An unavailable registry raises, and a raise is the correct outcome: admitting on a
    failed lookup would make a database outage into an authorization bypass.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def admit_end_user(self, entra_tenant_id: EntraTenantId) -> TenantContext | None:
        """Resolve admission for an end user's validated ``tid``.

        **``entra_tid`` is the only value that may be matched against a token-derived tenant.** It
        is matched against this column and nothing else; there is no fallback to a name, a domain
        or a header.

        Args:
            entra_tenant_id: The ``tid`` from the validated token. Not from a body, not from a
                query string — the middleware rejects a self-asserted one before routing.

        Returns:
            The trusted context, or ``None`` when the organisation is unknown.
        """
        table = models.TENANT_MAPPING
        statement = select(table.c.tenant_id, table.c.entra_tid, table.c.status).where(
            table.c.entra_tid == entra_tenant_id.value
        )
        async with read_session(self._sessions) as session:
            row = (await session.execute(statement)).one_or_none()

        if row is None:
            return None
        return TenantContext.from_admitted_identity(
            TenantId(row.tenant_id), EntraTenantId(row.entra_tid), TenantStatus(row.status)
        )

    async def status_for(self, tenant_id: TenantId) -> TenantContext | None:
        """Resolve current admission state for a known organisation.

        Read before execution as well as at admission, because a suspension can land between the
        two and approved work MUST NOT execute for an organisation that is no longer active
        (spec FR-EXEC-003).
        """
        table = models.TENANT_MAPPING
        statement = select(table.c.tenant_id, table.c.entra_tid, table.c.status).where(
            table.c.tenant_id == tenant_id.value
        )
        async with read_session(self._sessions) as session:
            row = (await session.execute(statement)).one_or_none()

        if row is None:
            return None
        return TenantContext.from_admitted_identity(
            TenantId(row.tenant_id), EntraTenantId(row.entra_tid), TenantStatus(row.status)
        )

    async def tenant_for_work_item(self, work_item_id: WorkItemId) -> TenantContext | None:
        """Derive the target organisation from the durable work item.

        **This is how a Workload execution and a resume get their tenant.** The Workload principal
        carries no customer-tenant authority of its own, and the trigger that woke it carries no
        tenant either (``contracts/triggers.md``) — so the tenant comes from the row, joined to the
        registry for its current status. A message that claimed a tenant could be forged; a row
        that states one cannot be, because ``work_item.tenant_id`` is immutable at the database
        permission boundary.
        """
        work = models.WORK_ITEM
        registry = models.TENANT_MAPPING
        statement = (
            select(registry.c.tenant_id, registry.c.entra_tid, registry.c.status)
            .select_from(work.join(registry, work.c.tenant_id == registry.c.tenant_id))
            .where(work.c.work_item_id == work_item_id.value)
        )
        async with read_session(self._sessions) as session:
            row = (await session.execute(statement)).one_or_none()

        if row is None:
            return None
        return TenantContext.from_work_item(
            TenantId(row.tenant_id), EntraTenantId(row.entra_tid), TenantStatus(row.status)
        )

    async def tenant_for_session(self, session_id: SessionId) -> TenantContext | None:
        """Derive the target organisation from the durable session a staff action operates on.

        **A staff token's ``tid`` is the Operator tenant and is never the customer target.** A staff
        caller names a session; this resolves which organisation that session belongs to, from
        platform state. There is deliberately no method taking a customer tenant identifier from a
        staff request, because such a method is the whole of the cross-tenant vulnerability.
        """
        sessions = models.CHAT_SESSION
        registry = models.TENANT_MAPPING
        statement = (
            select(registry.c.tenant_id, registry.c.entra_tid, registry.c.status)
            .select_from(sessions.join(registry, sessions.c.tenant_id == registry.c.tenant_id))
            .where(sessions.c.session_id == session_id.value)
        )
        async with read_session(self._sessions) as session:
            row = (await session.execute(statement)).one_or_none()

        if row is None:
            return None
        return TenantContext.from_platform_object(
            TenantId(row.tenant_id), EntraTenantId(row.entra_tid), TenantStatus(row.status)
        )

    async def retention_overrides(self, tenant: TenantContext) -> dict[str, Any] | None:
        """Read an organisation's retention overrides.

        Returns:
            The overrides, or ``None`` when none are configured. **``None`` means the platform
            default applies**, never unbounded retention (spec FR-SESS-008).
        """
        table = models.TENANT_MAPPING
        statement = select(table.c.retention_overrides).where(
            table.c.tenant_id == tenant.tenant_id.value
        )
        async with read_session(self._sessions) as session:
            row = (await session.execute(statement)).one_or_none()
        if row is None:
            return None
        overrides: dict[str, Any] | None = row.retention_overrides
        return overrides


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class SessionRepository(_TenantScoped):
    """Chat sessions and their messages.

    Satisfies :class:`~ragcore.application.ports.SessionRepositoryPort`.
    """

    async def get(self, tenant: TenantContext, session_id: SessionId) -> Any | None:  # noqa: ANN401
        """Load one session within the tenant.

        The tenant predicate is applied **as well as** the primary key, which looks redundant and
        is not: it means a caller holding a session identifier from another organisation reads
        nothing rather than reading that organisation's row.
        """
        table = models.CHAT_SESSION
        statement = select(table).where(
            self._scope(tenant, table), table.c.session_id == session_id.value
        )
        async with read_session(self._sessions) as session:
            return (await session.execute(statement)).one_or_none()

    async def list_for_requester(
        self, tenant: TenantContext, requester: PrincipalId, limit: int
    ) -> list[Any]:
        """List a user's own sessions, newest first."""
        table = models.CHAT_SESSION
        statement = (
            select(table)
            .where(
                self._scope(tenant, table),
                table.c.requester_oid == requester.value,
            )
            .order_by(table.c.created_at.desc())
            .limit(limit)
        )
        async with read_session(self._sessions) as session:
            return list((await session.execute(statement)).all())

    async def transition(
        self,
        tenant: TenantContext,
        session_id: SessionId,
        state: str,
        expected_version: int,
        content_expires_at: datetime | None = None,
    ) -> bool:
        """Move a session to a new state under optimistic concurrency.

        ``content_expires_at`` is passed rather than computed here: the retention window belongs to
        :mod:`ragcore.persistence.retention`, which knows the organisation's overrides, and a
        repository that computed it would be a second place the default could be got wrong.

        Returns:
            ``False`` when the version no longer matches. The caller re-reads; nothing blocks.
        """
        table = models.CHAT_SESSION
        changes: dict[str, Any] = {"state": state}
        if content_expires_at is not None:
            changes["content_expires_at"] = content_expires_at
        return await guarded_update(
            current_session(),
            table,
            VersionedRow(
                identity=self._scope(tenant, table) & (table.c.session_id == session_id.value),
                expected_version=expected_version,
            ),
            **changes,
        )


# ---------------------------------------------------------------------------
# Work — the durable authority record
# ---------------------------------------------------------------------------


class WorkItemRepository(_TenantScoped):
    """Durable authority records.

    Satisfies :class:`~ragcore.application.ports.WorkItemRepositoryPort`.
    """

    async def get(self, tenant: TenantContext, work_item_id: WorkItemId) -> Any | None:  # noqa: ANN401
        """Load one work item within the tenant."""
        table = models.WORK_ITEM
        statement = select(table).where(
            self._scope(tenant, table), table.c.work_item_id == work_item_id.value
        )
        async with read_session(self._sessions) as session:
            return (await session.execute(statement)).one_or_none()

    async def claim(
        self,
        tenant: TenantContext,
        work_item_id: WorkItemId,
        claimed_by: str,
        now: datetime,
    ) -> bool:
        """Atomically claim a work item — **idempotency boundary 1**.

        A conditional update on ``claimed_at IS NULL``. At-least-once delivery means a duplicate
        trigger is routine rather than exceptional, and this is what absorbs it: the second caller
        gets ``False`` and does nothing.

        The predicate also requires the item to be ``authorized`` and still inside its window. An
        expired item is not claimable, and that is **not an error** (spec FR-EXEC-001) — it is a
        ``False`` the caller reports as an expiry.

        Returns:
            ``True`` when this caller won the claim, ``False`` when another already holds it or the
            item was not claimable.
        """
        table = models.WORK_ITEM
        return await claim_once(
            current_session(),
            table,
            self._scope(tenant, table)
            & (table.c.work_item_id == work_item_id.value)
            & table.c.claimed_at.is_(None)
            & (table.c.state == WorkItemState.AUTHORIZED.value)
            & table.c.expires_at.isnot(None)
            & (table.c.expires_at > now),
            claimed_at=now,
            claimed_by=claimed_by,
            state=WorkItemState.CLAIMED.value,
        )

    async def transition(
        self,
        tenant: TenantContext,
        work_item_id: WorkItemId,
        state: WorkItemState,
        expected_version: int,
    ) -> bool:
        """Move a work item to a new state under optimistic concurrency.

        **None of the six authority fields is writable through this method**, and none is writable
        through any other: the database trigger installed by revision ``0017`` refuses the update
        whatever issues it.

        Returns:
            ``False`` when the version no longer matches — the caller re-reads rather than blocks.
            **There is no distributed lock anywhere in this platform.**
        """
        table = models.WORK_ITEM
        return await guarded_update(
            current_session(),
            table,
            VersionedRow(
                identity=self._scope(tenant, table) & (table.c.work_item_id == work_item_id.value),
                expected_version=expected_version,
            ),
            state=state.value,
        )

    async def list_expired(self, tenant: TenantContext, now: datetime, limit: int) -> list[Any]:
        """Unclaimed authorized items whose window has closed. The expiry sweeper's one query."""
        table = models.WORK_ITEM
        statement = (
            select(table.c.work_item_id, table.c.version)
            .where(
                self._scope(tenant, table),
                table.c.claimed_at.is_(None),
                table.c.expires_at.isnot(None),
                table.c.expires_at <= now,
                table.c.state == WorkItemState.AUTHORIZED.value,
            )
            .order_by(table.c.expires_at)
            .limit(limit)
        )
        async with read_session(self._sessions) as session:
            return list((await session.execute(statement)).all())


# ---------------------------------------------------------------------------
# Human decisions
# ---------------------------------------------------------------------------


class ApprovalRepository(_TenantScoped):
    """Approval requests and recorded verdicts.

    Satisfies :class:`~ragcore.application.ports.ApprovalRepositoryPort`.
    """

    async def record_verdict(
        self,
        tenant: TenantContext,
        approval_id: ApprovalId,
        decided_by: PrincipalId,
        roles_held: RoleSet,
        verdict: ApprovalVerdict,
        expires_at: datetime,
    ) -> bool:
        """Record a verdict, binding the approver and the roles they held at decision time.

        **First valid verdict wins** (spec FR-INTR-010). The ``decided_at IS NULL`` predicate is
        the mechanism: a second decider's update matches no row, so a later verdict is recorded
        elsewhere but changes nothing here.

        ``roles_held`` is captured rather than re-derived, because a role removed afterwards must
        not retroactively change what the record says was authorized.

        Returns:
            ``True`` when this verdict decided the outcome; ``False`` when a valid verdict already
            existed.
        """
        table = models.APPROVAL
        return await claim_once(
            current_session(),
            table,
            self._scope(tenant, table)
            & (table.c.approval_id == approval_id.value)
            & table.c.decided_at.is_(None),
            decided_at=func.now(),
            decided_by_oid=decided_by.value,
            decided_by_roles=sorted(role.value for role in roles_held.roles),
            verdict=verdict.value,
            expires_at=expires_at,
        )

    async def decision_for(
        self, tenant: TenantContext, work_item_id: WorkItemId
    ) -> StaffVerdict | None:
        """Read back the decision that actually stands for this work item.

        **This is where authority is read**, and it is why a resume worker does not need to trust
        the trigger that woke it. The message says a verdict happened; this says what the verdict
        was, who made it, and which roles they held — from the durable row.

        Returns:
            The standing verdict, or ``None`` when none has been recorded. **``None`` means
            undecided, never approved.**
        """
        table = models.APPROVAL
        operation = models.OPERATION
        # The catalogue identity the approver was shown, read from the operation rather than
        # passed in. `bound_to` is what makes an approval specific: a verdict is granted against
        # one catalogue entry at one version, and reconstructing it from a caller's argument would
        # let a resume claim the verdict applied to something else.
        bound = (
            select(operation.c.catalogue_id, operation.c.catalogue_version)
            .where(
                self._scope(tenant, operation),
                operation.c.work_item_id == work_item_id.value,
            )
            .order_by(operation.c.created_at.desc())
            .limit(1)
            .subquery()
            .lateral()
        )
        statement = (
            select(
                table.c.approval_id,
                table.c.decided_by_oid,
                table.c.decided_by_roles,
                table.c.verdict,
                table.c.decided_at,
                table.c.expires_at,
                bound.c.catalogue_id,
                bound.c.catalogue_version,
            )
            .select_from(table.join(bound, true()))
            .where(
                self._scope(tenant, table),
                table.c.work_item_id == work_item_id.value,
                table.c.decided_at.isnot(None),
            )
        )
        async with read_session(self._sessions) as session:
            row = (await session.execute(statement)).one_or_none()

        if row is None or row.verdict is None or row.decided_by_oid is None:
            return None
        return StaffVerdict(
            approval_id=ApprovalId(row.approval_id),
            decided_by=PrincipalId(row.decided_by_oid),
            roles_held=RoleSet.of(*(StaffRole(name) for name in row.decided_by_roles or ())),
            verdict=ApprovalVerdict(row.verdict),
            bound_to=OperationIdentity(row.catalogue_id, row.catalogue_version),
            decided_at=row.decided_at,
            expires_at=row.expires_at,
        )


class ConsentRepository(_TenantScoped):
    """End-user consent records.

    Satisfies :class:`~ragcore.application.ports.ConsentRepositoryPort`.
    """

    async def record(
        self,
        tenant: TenantContext,
        consent_id: ConsentId,
        work_item_id: WorkItemId,
        consented_by: PrincipalId,
        verdict: ConsentVerdict,
    ) -> bool:
        """Record a consent decision.

        **The requester is verified against the durable work item, in this transaction** — not
        against anything the request asserted. The ``INSERT ... SELECT`` below is what makes that
        atomic: there is no window between checking who the requester is and writing the row.

        Consent is an explicit authenticated action and is never inferred from chat text
        (spec FR-SESS-011); it **never** satisfies a ``STAFF_APPROVAL`` requirement
        (spec FR-INTR-007), which is why it is written here and not into ``approval``.

        Returns:
            ``True`` when the consent was recorded, ``False`` when the principal is not the work
            item's own requester or the work item does not belong to this organisation.
        """
        consent = models.CONSENT
        work = models.WORK_ITEM

        source = select(
            work.c.tenant_id.label("tenant_id"),
            work.c.work_item_id.label("work_item_id"),
            literal(consent_id.value, PG_UUID(as_uuid=True)).label("consent_id"),
            literal(consented_by.value, PG_UUID(as_uuid=True)).label("consented_by_oid"),
            func.now().label("decided_at"),
            literal(verdict.value, enums.CONSENT_VERDICT).label("verdict"),
        ).where(
            self._scope(tenant, work),
            work.c.work_item_id == work_item_id.value,
            work.c.requested_by_oid == consented_by.value,
        )
        statement = insert(consent).from_select(
            [
                "tenant_id",
                "work_item_id",
                "consent_id",
                "consented_by_oid",
                "decided_at",
                "verdict",
            ],
            source,
        )
        result = await current_session().execute(statement)
        return rows_affected(result) == 1

    async def decision_for(
        self, tenant: TenantContext, work_item_id: WorkItemId
    ) -> EndUserConsent | None:
        """Read back the consent recorded for this work item.

        Returns:
            The consent, or ``None`` when none has been recorded. An affirmative chat message is
            not a consent and never produces a value here.
        """
        table = models.CONSENT
        operation = models.OPERATION
        bound = (
            select(operation.c.catalogue_id, operation.c.catalogue_version)
            .where(
                self._scope(tenant, operation),
                operation.c.work_item_id == work_item_id.value,
            )
            .order_by(operation.c.created_at.desc())
            .limit(1)
            .subquery()
            .lateral()
        )
        statement = (
            select(
                table.c.consent_id,
                table.c.consented_by_oid,
                table.c.verdict,
                table.c.decided_at,
                bound.c.catalogue_id,
                bound.c.catalogue_version,
            )
            .select_from(table.join(bound, true()))
            .where(self._scope(tenant, table), table.c.work_item_id == work_item_id.value)
            .order_by(table.c.decided_at.desc())
            .limit(1)
        )
        async with read_session(self._sessions) as session:
            row = (await session.execute(statement)).one_or_none()

        if row is None:
            return None
        return EndUserConsent(
            consent_id=ConsentId(row.consent_id),
            consented_by=PrincipalId(row.consented_by_oid),
            verdict=ConsentVerdict(row.verdict),
            bound_to=OperationIdentity(row.catalogue_id, row.catalogue_version),
            decided_at=row.decided_at,
        )


# ---------------------------------------------------------------------------
# Governance — the catalogue is stored; the decision is not
# ---------------------------------------------------------------------------


class OperationCatalogue(_TenantScoped):
    """The canonical operation catalogue and per-organisation entitlement.

    Satisfies :class:`~ragcore.application.ports.OperationCataloguePort`.

    **Returns catalogue data. It never decides.** The treatment decision is deterministic domain
    policy over this data; making the decision injectable is precisely how a model-supplied
    treatment would get in.
    """

    async def lookup(self, tenant: TenantContext, identity: OperationIdentity) -> Any | None:  # noqa: ANN401
        """Resolve a catalogue entry, **entitled to this organisation**.

        The join to ``tenant_entitlement`` is not an optimisation. A capability is callable only
        when registered **and** entitled; discovery never confers entitlement (spec FR-EXT-014).
        Resolving the entry without the join would return something callers could treat as a
        permission.

        Returns:
            The entry, or ``None``. **``None`` is a refusal, not a default**: an operation with no
            entry does not proceed.
        """
        catalogue = models.GOVERNANCE_RECORD
        entitlement = models.TENANT_ENTITLEMENT
        statement = (
            select(
                catalogue.c.catalogue_id,
                catalogue.c.version,
                catalogue.c.kind,
                catalogue.c.default_treatment,
                catalogue.c.accepted_roles,
                catalogue.c.is_reference_fixture,
                catalogue.c.requires_elevation,
                catalogue.c.risk_tier,
                catalogue.c.commands,
                catalogue.c.content_hash,
                catalogue.c.verification_tool,
            )
            .select_from(
                catalogue.join(entitlement, entitlement.c.catalogue_id == catalogue.c.catalogue_id)
            )
            .where(
                self._scope(tenant, entitlement),
                entitlement.c.enabled.is_(True),
                catalogue.c.catalogue_id == identity.catalogue_id,
                catalogue.c.version == identity.version,
            )
        )
        async with read_session(self._sessions) as session:
            return (await session.execute(statement)).one_or_none()

    async def is_entitled(self, tenant: TenantContext, catalogue_id: str) -> bool:
        """Whether this organisation may call this capability at all.

        **There is no global toolset.** Capabilities resolve per organisation, least-privilege, and
        the absence of a row denies.
        """
        table = models.TENANT_ENTITLEMENT
        statement = select(table.c.catalogue_id).where(
            self._scope(tenant, table),
            table.c.catalogue_id == catalogue_id,
            table.c.enabled.is_(True),
        )
        async with read_session(self._sessions) as session:
            return (await session.execute(statement)).one_or_none() is not None


class OperationRepository(_TenantScoped):
    """Proposed and executed operations.

    Satisfies :class:`~ragcore.application.ports.OperationRepositoryPort`.
    """

    async def record_outcome(
        self,
        tenant: TenantContext,
        operation_id: OperationId,
        verification: VerificationOutcome,
        detail: str,
    ) -> None:
        """Record what happened, and what the platform **actually knows** about it.

        ``verification`` and ``status`` are separate columns because they answer separate
        questions: the call succeeded, and the effect was confirmed. A ``client_attested`` outcome
        on a succeeded call is not a confirmed resolution and MUST NOT be presented as one
        (spec FR-AGENT-008).
        """
        table = models.OPERATION
        await current_session().execute(
            update(table)
            .where(self._scope(tenant, table), table.c.operation_id == operation_id.value)
            .values(
                verification=verification.value,
                status=detail,
                executed_at=func.now(),
                updated_at=func.now(),
                version=table.c.version + 1,
            )
        )


# ---------------------------------------------------------------------------
# Execution and messaging boundaries
# ---------------------------------------------------------------------------


class IdempotencyStore(_TenantScoped):
    """**Idempotency boundary 2 — protecting the external system.**

    Satisfies :class:`~ragcore.application.ports.IdempotencyStorePort`. Boundary 1 remains the
    atomic claim on the work item, which protects the platform. Both are required; neither
    substitutes for the other.
    """

    async def remember(
        self,
        tenant: TenantContext,
        key: IdempotencyKey,
        operation_id: OperationId,
        outcome: dict[str, Any],
    ) -> None:
        """Record the outcome for a key, so a repeat replays rather than acting again.

        **The one table with no ``version`` column**, and the update below is why that is right: it
        happens exactly once, on a row whose primary key has already serialised every writer that
        could reach it.
        """
        table = models.IDEMPOTENCY_RECORD
        await current_session().execute(
            update(table)
            .where(
                self._scope(tenant, table),
                table.c.idempotency_key == key.value,
                table.c.operation_id == operation_id.value,
            )
            .values(outcome=outcome, updated_at=func.now())
        )

    async def replay(self, tenant: TenantContext, key: IdempotencyKey) -> dict[str, Any] | None:
        """Return the original outcome for a key, or ``None`` when unseen.

        ``None`` also covers *claimed but not yet complete* — the window between an operation
        starting and recording its result. A caller must treat that as "do not act", not as
        "never seen", which is why the caller checks the claim rather than inferring from this.
        """
        table = models.IDEMPOTENCY_RECORD
        statement = select(table.c.outcome).where(
            self._scope(tenant, table), table.c.idempotency_key == key.value
        )
        async with read_session(self._sessions) as session:
            row = (await session.execute(statement)).one_or_none()
        if row is None:
            return None
        outcome: dict[str, Any] | None = row.outcome
        return outcome


class Outbox(_TenantScoped):
    """The transactional outbox. Satisfies :class:`~ragcore.application.ports.OutboxPort`.

    **The row is written inside the caller's transaction**, which is the entire point: durability
    before publication means a crash between the state change and the publish loses nothing and
    duplicates nothing. This class takes the caller's session rather than opening its own, and that
    parameter is the mechanism rather than a convenience.
    """

    async def enqueue(self, tenant: TenantContext, envelope: TriggerEnvelope) -> None:
        """Write an outbox row **inside the caller's transaction**.

        The payload is subject to the trigger contract: **no tenant, requester, role, action,
        target or approval state** (``contracts/triggers.md``). A consumer reads authority from the
        durable record, not from the message that woke it, which is why a forged or replayed
        trigger cannot authorize anything.
        """
        table = models.OUTBOX_MESSAGE
        await current_session().execute(
            insert(table).values(
                # Generated here rather than taken from the envelope: the envelope is the *message*
                # and carries only what a consumer may see, while this is the row's own surrogate
                # key. A caller supplying it could collide two triggers onto one row.
                outbox_id=uuid4(),
                tenant_id=tenant.tenant_id.value,
                occurred_at=func.now(),
                kind=envelope.kind.value,
                payload={
                    "workItemId": str(envelope.work_item_id),
                    "correlationId": str(envelope.correlation_id),
                },
            )
        )

    async def undispatched(self, limit: int) -> list[Any]:
        """The dispatcher's one query: the oldest unpublished rows, in sequence order.

        **The single method in this module that applies no tenant predicate, and it is deliberate.**
        The dispatcher is a platform worker publishing every organisation's triggers; a tenant
        filter here would mean either a worker per organisation or a worker that silently stopped
        publishing for the ones it was not scoped to. The row it reads carries no tenant-bearing
        content, so reading across organisations discloses nothing — the payload is opaque
        identifiers and correlation only.
        """
        table = models.OUTBOX_MESSAGE
        statement = (
            select(table.c.outbox_id, table.c.kind, table.c.payload, table.c.sequence)
            .where(table.c.dispatched_at.is_(None))
            .order_by(table.c.sequence)
            .limit(limit)
        )
        async with read_session(self._sessions) as session:
            return list((await session.execute(statement)).all())

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        """Record a successful publication. Called by the dispatcher, after the transport accepts.

        Tenant-free for the same reason as :meth:`undispatched`, and narrowed by primary key.
        """
        table = models.OUTBOX_MESSAGE
        await current_session().execute(
            update(table)
            .where(table.c.outbox_id == outbox_id)
            .values(
                dispatched_at=func.now(),
                attempts=table.c.attempts + 1,
                updated_at=func.now(),
                version=table.c.version + 1,
            )
        )


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class AuditSink(_TenantScoped):
    """Durable audit records. Satisfies :class:`~ragcore.application.ports.AuditSinkPort`.

    **Append-only, and not by convention**: the runtime principal holds ``INSERT`` and ``SELECT``
    on ``audit_event`` and neither ``UPDATE`` nor ``DELETE`` (revision ``0019``). There is
    deliberately no ``amend`` or ``delete`` method here, and adding one would fail at the database
    rather than silently rewriting history.

    Separate from telemetry, with separate retention. **Telemetry MUST NEVER answer an audit
    question** (spec FR-OPS-004) — which is why this is its own sink rather than a logger with a
    flag.
    """

    async def record(
        self,
        tenant: TenantContext,
        event_id: AuditEventId,
        correlation_id: CorrelationId,
        actor_chain: ActorChain,
        detail: AuditFacts,
        *,
        work_item_id: WorkItemId | None = None,
        retain_until: datetime | None = None,
        retention_overrides: dict[str, Any] | None = None,
    ) -> None:
        """Append one audit event.

        Written in the caller's transaction, so the record of a decision is as durable as the
        decision itself. **Denials, expiries and escalations are recorded as durably as
        permissions** (spec FR-AUDIT-003): there is no parameter here that could mark an event as
        not worth keeping, and ``ExecutionMethod.NONE`` is what a refusal records rather than an
        absence.

        **Credentials never appear.** Every value written is a stable principal identifier, a
        non-secret reference or a term from a fixed vocabulary.

        Args:
            actor_chain: Who asked, who approved, and who actually did it — plus by what means.
            detail: The governance facts: the kind of moment, the outcome, the treatment in force,
                and what verification established.
            work_item_id: The case this concerns, where it concerns one.
            retain_until: An explicit retention horizon. Omitted in normal use.
            retention_overrides: The organisation's overrides, used to resolve the horizon when
                ``retain_until`` is not given. **A missing override is the platform default, never
                unbounded retention** (spec FR-SESS-008).

        Raises:
            ValueError: When both ``retain_until`` and ``retention_overrides`` are supplied. Two
                sources for one horizon is a disagreement waiting to happen, and an audit record
                with an arguable retention is one nobody can rely on.
        """
        if retain_until is not None and retention_overrides is not None:
            raise ValueError(
                "supply `retain_until` or `retention_overrides`, not both: the retention horizon "
                "has one source."
            )

        # Stamped at write time rather than computed at read time. Shortening an organisation's
        # window must govern what is written from then on, not silently expire what is already
        # recorded.
        #
        # Derived from the database's own `now()` rather than from a Python instant, so
        # `occurred_at` and `retain_until` are the same clock reading plus a window — two replicas
        # with drifting clocks cannot produce a record that expires before it happened. The
        # duration is bound as an interval parameter, not formatted into the statement.
        window = window_for(RetentionClass.AUDIT, retention_overrides)
        horizon: Any = (
            retain_until
            if retain_until is not None
            else func.now() + literal(window.duration, Interval())
        )

        table = models.AUDIT_EVENT
        await current_session().execute(
            insert(table).values(
                audit_id=event_id.value,
                tenant_id=tenant.tenant_id.value,
                work_item_id=work_item_id.value if work_item_id is not None else None,
                occurred_at=func.now(),
                action=detail.kind.value,
                requested_by_oid=(
                    actor_chain.requested_by.value if actor_chain.requested_by is not None else None
                ),
                approved_by_oid=(
                    actor_chain.approved_by.value if actor_chain.approved_by is not None else None
                ),
                executed_by=actor_chain.executed_by,
                execution_method=actor_chain.execution_method.value,
                outcome=detail.outcome,
                verification=(
                    detail.verification.value if detail.verification is not None else None
                ),
                correlation_id=correlation_id.value,
                retain_until=horizon,
            )
        )

    async def search(
        self,
        tenant: TenantContext,
        since: datetime,
        limit: int,
        work_item_id: WorkItemId | None = None,
    ) -> list[Any]:
        """Read audit within the organisation, newest first."""
        table = models.AUDIT_EVENT
        predicates = [
            self._scope(tenant, table),
            table.c.occurred_at >= since,
            table.c.retain_until > func.now(),
        ]
        if work_item_id is not None:
            predicates.append(table.c.work_item_id == work_item_id.value)
        statement = (
            select(table).where(*predicates).order_by(table.c.occurred_at.desc()).limit(limit)
        )
        async with read_session(self._sessions) as session:
            return list((await session.execute(statement)).all())
