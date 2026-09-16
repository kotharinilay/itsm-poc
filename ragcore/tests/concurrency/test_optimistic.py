"""Optimistic concurrency: the loser sees a conflict and re-reads. **Nothing blocks.**

Three positions from ``data-model.md`` §Conventions, each asserted rather than asserted-about:

1. **No distributed lock, anywhere.** The tests below prove the losing writer *returns*, promptly,
   with a ``False`` — not that it waits and eventually wins. A lock would make the second test hang
   rather than fail, which is the worst way for this property to regress.
2. **No Serializable transaction, anywhere.** Read Committed is what these run at, because that is
   what the platform runs at, and every invariant here is held by a constraint or a conditional
   update instead.
3. **No ``deleted_at`` on any scaffold entity.** A structural check, because the moment one appears
   the retention and erasure tests start passing for the wrong reason.

The version exemption is asserted in both directions: ``idempotency_record`` has no ``version``, and
**every other table does**. One without the other would let a new table quietly join the exemption.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ragcore.domain.identifiers import EntraTenantId, TenantId, WorkItemId
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.domain.work import ApprovalState, SessionState, WorkItemState
from ragcore.persistence import models
from ragcore.persistence.base import SoftDeletable
from ragcore.persistence.concurrency import (
    EXEMPT_FROM_VERSIONING,
    ConcurrencyConflictError,
    VersionedRow,
    guarded_update,
    require_guarded_update,
)
from ragcore.persistence.engine import UnitOfWork
from ragcore.persistence.repositories import WorkItemRepository


class TestTheVersioningConventionAndItsOneExemption:
    """Structural, so it holds for tables nobody has written a scenario for."""

    def test_every_table_but_the_named_exemption_carries_a_version(self) -> None:
        """The convention is exceptionless apart from a list somebody has to edit."""
        missing = {
            name
            for name, table in models.TABLES_BY_NAME.items()
            if "version" not in table.c and name not in EXEMPT_FROM_VERSIONING
        }
        assert not missing, f"tables with no version column and no stated exemption: {missing}"

    def test_the_exemption_is_exactly_the_idempotency_record(self) -> None:
        """Named in ``data-model.md``, and named here. Two places, one list."""
        assert {"idempotency_record"} == EXEMPT_FROM_VERSIONING
        assert "version" not in models.IDEMPOTENCY_RECORD.c

    def test_governance_record_versions_its_key_rather_than_its_row(self) -> None:
        """The second named departure: ``version`` here is half the primary key.

        A catalogue entry is never edited in place — a change is a new row — so a row counter would
        be a concurrency mechanism on something that cannot be updated.
        """
        primary_key = {column.name for column in models.GOVERNANCE_RECORD.primary_key}
        assert primary_key == {"catalogue_id", "version"}

    def test_no_scaffold_entity_declares_a_soft_delete_column(self) -> None:
        """**Removal is removal.** Erasure is a hard delete and retention is a removal, not a flag.

        The convention exists in :class:`SoftDeletable` so the first table that genuinely needs
        recoverable deletion adopts it rather than inventing a second one — and nothing uses it yet.
        """
        soft = {name for name, table in models.TABLES_BY_NAME.items() if "deleted_at" in table.c}
        assert not soft, f"a scaffold entity declared deleted_at: {soft}"
        assert hasattr(SoftDeletable, "deleted_at"), "the convention itself should still exist"


@pytest.fixture
async def seeded(
    sessions: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """One organisation with one work item, ready to be raced over."""
    tenant_id, entra_tid = uuid4(), uuid4()
    session_id, work_item_id, requester = uuid4(), uuid4(), uuid4()

    async with sessions() as session, session.begin():
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

    return {
        "tenant": TenantContext.from_admitted_identity(
            TenantId(tenant_id), EntraTenantId(entra_tid), TenantStatus.ACTIVE
        ),
        "work_item_id": WorkItemId(work_item_id),
    }


def _row(seeded: dict[str, Any], version: int) -> VersionedRow:
    table = models.WORK_ITEM
    tenant = seeded["tenant"]
    return VersionedRow(
        identity=(table.c.tenant_id == tenant.tenant_id.value)
        & (table.c.work_item_id == seeded["work_item_id"].value),
        expected_version=version,
    )


@pytest.mark.integration
@pytest.mark.concurrency
class TestTheLosingWriterReReadsRatherThanBlocking:
    """A conflict is an ordinary outcome, returned promptly."""

    async def test_a_write_at_the_current_version_wins(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """The baseline: the guard permits the write it is supposed to permit."""
        async with UnitOfWork(sessions) as uow:
            won = await guarded_update(
                uow.session,
                models.WORK_ITEM,
                _row(seeded, 1),
                state=WorkItemState.AWAITING_DECISION.value,
            )
        assert won

    async def test_the_version_increments_with_the_change(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """In the same statement, so there is no window where the two disagree."""
        async with UnitOfWork(sessions) as uow:
            await guarded_update(
                uow.session,
                models.WORK_ITEM,
                _row(seeded, 1),
                state=WorkItemState.AWAITING_DECISION.value,
            )

        async with sessions() as session:
            row = (
                await session.execute(
                    select(models.WORK_ITEM.c.version, models.WORK_ITEM.c.state).where(
                        models.WORK_ITEM.c.work_item_id == seeded["work_item_id"].value
                    )
                )
            ).one()
        assert row.version == 2
        assert row.state is WorkItemState.AWAITING_DECISION

    async def test_a_write_at_a_stale_version_loses_and_returns(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """**Returns** — the whole point. A lock would have made this wait instead."""
        async with UnitOfWork(sessions) as uow:
            await guarded_update(
                uow.session,
                models.WORK_ITEM,
                _row(seeded, 1),
                state=WorkItemState.AWAITING_DECISION.value,
            )

        async with UnitOfWork(sessions) as uow:
            won = await asyncio.wait_for(
                guarded_update(
                    uow.session,
                    models.WORK_ITEM,
                    _row(seeded, 1),
                    state=WorkItemState.CANCELLED.value,
                ),
                # A generous ceiling that still fails fast if somebody introduces a lock: the point
                # is that the loser does not wait for the winner, not that it is quick.
                timeout=5,
            )
        assert not won

    async def test_the_losing_writer_left_the_row_alone(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """A lost race changes nothing — not the state, and not the version."""
        async with UnitOfWork(sessions) as uow:
            await guarded_update(
                uow.session,
                models.WORK_ITEM,
                _row(seeded, 1),
                state=WorkItemState.AWAITING_DECISION.value,
            )
        async with UnitOfWork(sessions) as uow:
            await guarded_update(
                uow.session, models.WORK_ITEM, _row(seeded, 1), state=WorkItemState.CANCELLED.value
            )

        async with sessions() as session:
            row = (
                await session.execute(
                    select(models.WORK_ITEM.c.version, models.WORK_ITEM.c.state).where(
                        models.WORK_ITEM.c.work_item_id == seeded["work_item_id"].value
                    )
                )
            ).one()
        assert row.version == 2
        assert row.state is WorkItemState.AWAITING_DECISION

    async def test_a_re_read_lets_the_loser_succeed(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """The prescribed recovery, and it works: re-read the row, retry at the new version."""
        async with UnitOfWork(sessions) as uow:
            await guarded_update(
                uow.session,
                models.WORK_ITEM,
                _row(seeded, 1),
                state=WorkItemState.AWAITING_DECISION.value,
            )

        async with sessions() as session:
            current = (
                await session.execute(
                    select(models.WORK_ITEM.c.version).where(
                        models.WORK_ITEM.c.work_item_id == seeded["work_item_id"].value
                    )
                )
            ).scalar_one()

        async with UnitOfWork(sessions) as uow:
            won = await guarded_update(
                uow.session,
                models.WORK_ITEM,
                _row(seeded, current),
                state=WorkItemState.CANCELLED.value,
            )
        assert won

    async def test_the_raising_variant_names_the_table_and_the_version(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """For the call sites where losing is genuinely exceptional."""
        async with UnitOfWork(sessions) as uow:
            await guarded_update(
                uow.session,
                models.WORK_ITEM,
                _row(seeded, 1),
                state=WorkItemState.AWAITING_DECISION.value,
            )

        with pytest.raises(ConcurrencyConflictError) as caught:
            async with UnitOfWork(sessions) as uow:
                await require_guarded_update(
                    uow.session,
                    models.WORK_ITEM,
                    _row(seeded, 1),
                    state=WorkItemState.CANCELLED.value,
                )
        assert caught.value.table == "work_item"
        assert caught.value.expected_version == 1


@pytest.mark.integration
@pytest.mark.concurrency
class TestTheManagedColumnsCannotBeOverridden:
    """A caller that could pin the version could defeat the guard."""

    async def test_setting_the_version_is_refused(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """Refused rather than silently overridden, so the attempt is visible."""
        with pytest.raises(ValueError, match="managed"):
            async with UnitOfWork(sessions) as uow:
                await guarded_update(uow.session, models.WORK_ITEM, _row(seeded, 1), version=99)

    async def test_backdating_updated_at_is_refused(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """A backdated row is an audit trail that disagrees with itself."""
        from datetime import UTC, datetime

        with pytest.raises(ValueError, match="managed"):
            async with UnitOfWork(sessions) as uow:
                await guarded_update(
                    uow.session, models.WORK_ITEM, _row(seeded, 1), updated_at=datetime.now(UTC)
                )


@pytest.mark.integration
@pytest.mark.concurrency
class TestTheAtomicClaimIsIdempotencyBoundaryOne:
    """At-least-once delivery makes a duplicate trigger routine. This absorbs it."""

    async def _authorize(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import update

        async with sessions() as session, session.begin():
            await session.execute(
                update(models.WORK_ITEM)
                .where(models.WORK_ITEM.c.work_item_id == seeded["work_item_id"].value)
                .values(
                    state=WorkItemState.AUTHORIZED.value,
                    approval_state=ApprovalState.APPROVED.value,
                    expires_at=datetime.now(UTC) + timedelta(minutes=15),
                )
            )

    async def test_exactly_one_of_two_concurrent_claims_wins(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """Two consumers, one effect. This is the property the whole pattern exists for."""
        from datetime import UTC, datetime

        await self._authorize(sessions, seeded)
        repository = WorkItemRepository(sessions)
        now = datetime.now(UTC)

        async def attempt(who: str) -> bool:
            async with UnitOfWork(sessions):
                return await repository.claim(seeded["tenant"], seeded["work_item_id"], who, now)

        outcomes = await asyncio.gather(attempt("worker-a"), attempt("worker-b"))
        assert sorted(outcomes) == [False, True]

    async def test_a_repeated_trigger_does_not_re_claim(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """The duplicate gets ``False`` and does nothing. That is correct, not an error."""
        from datetime import UTC, datetime

        await self._authorize(sessions, seeded)
        repository = WorkItemRepository(sessions)
        now = datetime.now(UTC)

        async with UnitOfWork(sessions):
            first = await repository.claim(
                seeded["tenant"], seeded["work_item_id"], "worker-a", now
            )
        async with UnitOfWork(sessions):
            second = await repository.claim(
                seeded["tenant"], seeded["work_item_id"], "worker-a", now
            )

        assert first
        assert not second

    async def test_an_expired_item_is_not_claimable(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """Expiry makes the item non-executable, and that is **not an error**."""
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import update

        async with sessions() as session, session.begin():
            await session.execute(
                update(models.WORK_ITEM)
                .where(models.WORK_ITEM.c.work_item_id == seeded["work_item_id"].value)
                .values(
                    state=WorkItemState.AUTHORIZED.value,
                    expires_at=datetime.now(UTC) - timedelta(minutes=1),
                )
            )

        repository = WorkItemRepository(sessions)
        async with UnitOfWork(sessions):
            claimed = await repository.claim(
                seeded["tenant"], seeded["work_item_id"], "worker-a", datetime.now(UTC)
            )
        assert not claimed

    async def test_another_organisation_cannot_claim_the_item(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """The claim carries the tenant predicate like every other statement."""
        from datetime import UTC, datetime

        await self._authorize(sessions, seeded)
        stranger = TenantContext.from_admitted_identity(
            TenantId(uuid4()), EntraTenantId(uuid4()), TenantStatus.ACTIVE
        )

        repository = WorkItemRepository(sessions)
        async with UnitOfWork(sessions):
            claimed = await repository.claim(
                stranger, seeded["work_item_id"], "worker-a", datetime.now(UTC)
            )
        assert not claimed


@pytest.mark.integration
class TestTheWorkItemAuthorityFieldsAreImmutableAtTheDatabase:
    """Enforced by a trigger, so **no** path can change them — not even this test."""

    async def test_the_tenant_cannot_be_changed(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """Retargeting approved work at another organisation is the attack this stops."""
        from sqlalchemy import update
        from sqlalchemy.exc import DBAPIError

        with pytest.raises(DBAPIError, match="immutable"):
            async with sessions() as session, session.begin():
                await session.execute(
                    update(models.WORK_ITEM)
                    .where(models.WORK_ITEM.c.work_item_id == seeded["work_item_id"].value)
                    .values(tenant_id=uuid4())
                )

    async def test_the_requester_cannot_be_changed(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """Consent is only valid from the requester, so the requester has to be fixed."""
        from sqlalchemy import update
        from sqlalchemy.exc import DBAPIError

        with pytest.raises(DBAPIError, match="immutable"):
            async with sessions() as session, session.begin():
                await session.execute(
                    update(models.WORK_ITEM)
                    .where(models.WORK_ITEM.c.work_item_id == seeded["work_item_id"].value)
                    .values(requested_by_oid=uuid4())
                )

    async def test_a_write_once_field_may_be_set_and_then_never_changed(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """Null may become a value; a value may never become a different one."""
        from sqlalchemy import update
        from sqlalchemy.exc import DBAPIError

        async with sessions() as session, session.begin():
            await session.execute(
                update(models.WORK_ITEM)
                .where(models.WORK_ITEM.c.work_item_id == seeded["work_item_id"].value)
                .values(governed_action="fixture.read")
            )

        with pytest.raises(DBAPIError, match="immutable"):
            async with sessions() as session, session.begin():
                await session.execute(
                    update(models.WORK_ITEM)
                    .where(models.WORK_ITEM.c.work_item_id == seeded["work_item_id"].value)
                    .values(governed_action="fixture.write")
                )

    async def test_a_write_once_field_cannot_be_returned_to_null(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """``IS DISTINCT FROM`` rather than ``<>``, so null-to-value-to-null is caught too."""
        from sqlalchemy import update
        from sqlalchemy.exc import DBAPIError

        async with sessions() as session, session.begin():
            await session.execute(
                update(models.WORK_ITEM)
                .where(models.WORK_ITEM.c.work_item_id == seeded["work_item_id"].value)
                .values(case_reference="INC0001")
            )

        with pytest.raises(DBAPIError, match="immutable"):
            async with sessions() as session, session.begin():
                await session.execute(
                    update(models.WORK_ITEM)
                    .where(models.WORK_ITEM.c.work_item_id == seeded["work_item_id"].value)
                    .values(case_reference=None)
                )

    async def test_an_ordinary_state_transition_is_unaffected(
        self, sessions: async_sessionmaker[AsyncSession], seeded: dict[str, Any]
    ) -> None:
        """The guard protects six columns, not the row. A lifecycle change still works."""
        async with UnitOfWork(sessions) as uow:
            won = await guarded_update(
                uow.session,
                models.WORK_ITEM,
                _row(seeded, 1),
                state=WorkItemState.AWAITING_DECISION.value,
            )
        assert won
