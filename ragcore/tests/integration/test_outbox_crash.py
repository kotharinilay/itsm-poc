"""A crash between commit and publish **loses nothing and duplicates nothing** (quickstart V16).

The transactional outbox exists for exactly one reason, and it is this test. There is no instant at
which publishing around a transaction is safe:

- Publish *before* commit, and a rolled-back transaction has already told the world something
  happened. The consumer wakes, finds no work item, and dead-letters.
- Publish *after* commit, and a process that dies in between has changed state and told nobody. The
  work is authorized and nothing will ever execute it — approved-but-not-executed, which is a
  governance failure rather than a lost message.

The outbox makes the second case recoverable, because the row is already durable. The cost is
duplicates, and duplicates are the cheap failure: the atomic claim absorbs them.

**Both crash points are exercised below**, because they fail differently and only one of them is
obvious:

1. Crash after commit, before publish — the row survives and a later pass publishes it.
2. Crash after publish, before ``mark_dispatched`` — the row is published *again* on the next pass.
   This is the duplicate the design accepts, and the test asserts it happens rather than pretending
   it does not.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from workers.outbox_dispatch import dispatch_once, envelope_from_row

from ragcore.domain.envelopes import TriggerKind
from ragcore.domain.identifiers import EntraTenantId, TenantId, WorkItemId
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.domain.work import ApprovalState, SessionState, WorkItemState
from ragcore.messaging.outbox import enqueue_trigger
from ragcore.persistence import models
from ragcore.persistence.engine import UnitOfWork
from ragcore.persistence.repositories import Outbox

pytestmark = pytest.mark.integration


class RecordingPublisher:
    """Captures what was published, and can be told to fail."""

    def __init__(self, *, fail: bool = False) -> None:
        self.published: list[str] = []
        self.fail = fail

    async def publish(self, envelope: Any) -> None:
        if self.fail:
            raise RuntimeError("the transport is unreachable")
        self.published.append(str(envelope.work_item_id))


class CrashingPublisher(RecordingPublisher):
    """Publishes successfully, then the process 'dies' before the row is marked dispatched."""

    async def publish(self, envelope: Any) -> None:
        self.published.append(str(envelope.work_item_id))
        raise SystemExit("process died after the transport accepted the message")


@pytest.fixture(name="organisation")
async def organisation_fixture(sessions: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
    """One organisation with a work item ready to have a trigger written for it."""
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
                state=WorkItemState.AUTHORIZED.value,
                approval_state=ApprovalState.NONE.value,
            )
        )

    return {
        "tenant": TenantContext.from_admitted_identity(
            TenantId(tenant_id), EntraTenantId(entra_tid), TenantStatus.ACTIVE
        ),
        "work_item_id": WorkItemId(work_item_id),
    }


async def _count_outbox(session: AsyncSession) -> int:
    return int(
        (
            await session.execute(select(func.count()).select_from(models.OUTBOX_MESSAGE))
        ).scalar_one()
    )


class TestTheStateChangeAndItsMessageAreDurableTogether:
    """The property the outbox exists for."""

    async def test_a_rolled_back_transaction_writes_no_outbox_row(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """Nothing is announced for a state change that did not happen.

        The first of the two unsafe orderings: publishing before commit would have told the world
        about work that then rolled back.
        """
        with pytest.raises(RuntimeError):
            async with UnitOfWork(sessions):
                await enqueue_trigger(
                    Outbox(sessions),
                    organisation["tenant"],
                    organisation["work_item_id"],
                    TriggerKind.SAMPLE_FLOW,
                )
                raise RuntimeError("the handler failed after writing the outbox row")

        async with sessions() as session:
            assert await _count_outbox(session) == 0

    async def test_a_committed_transaction_leaves_the_row_durable(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """And undispatched, so a dispatcher picks it up whenever it next runs — even after a
        restart. That is what makes the crash-after-commit case recoverable rather than lost.
        """
        async with UnitOfWork(sessions):
            await enqueue_trigger(
                Outbox(sessions),
                organisation["tenant"],
                organisation["work_item_id"],
                TriggerKind.SAMPLE_FLOW,
            )

        async with sessions() as session:
            assert await _count_outbox(session) == 1

        async with UnitOfWork(sessions):
            pending = await Outbox(sessions).undispatched(10)
        assert len(pending) == 1


class TestCrashAfterCommitBeforePublish:
    """Nothing is lost. The row outlives the process that wrote it."""

    async def test_a_later_pass_publishes_what_the_crash_left_behind(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        async with UnitOfWork(sessions):
            await enqueue_trigger(
                Outbox(sessions),
                organisation["tenant"],
                organisation["work_item_id"],
                TriggerKind.SAMPLE_FLOW,
            )
        # ... and the process dies here, before any dispatcher runs.

        publisher = RecordingPublisher()
        async with UnitOfWork(sessions):
            result = await dispatch_once(Outbox(sessions), publisher, batch_size=10)

        assert result.published == 1
        assert publisher.published == [str(organisation["work_item_id"])]

    async def test_a_published_row_is_not_published_twice(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """The ordinary case: marked dispatched, so the next pass skips it."""
        async with UnitOfWork(sessions):
            await enqueue_trigger(
                Outbox(sessions),
                organisation["tenant"],
                organisation["work_item_id"],
                TriggerKind.SAMPLE_FLOW,
            )

        publisher = RecordingPublisher()
        async with UnitOfWork(sessions):
            await dispatch_once(Outbox(sessions), publisher, batch_size=10)
        async with UnitOfWork(sessions):
            second = await dispatch_once(Outbox(sessions), publisher, batch_size=10)

        assert second.published == 0
        assert len(publisher.published) == 1


class TestCrashAfterPublishBeforeMarking:
    """A duplicate, and the design says so out loud."""

    async def test_the_row_is_published_again_and_the_claim_absorbs_it(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """**This is the accepted cost of never losing a message.**

        The alternative ordering — mark dispatched, then send — would lose the message entirely on
        the same crash. Duplicating is recoverable downstream by the atomic claim; losing an
        approved trigger is not recoverable at all.
        """
        async with UnitOfWork(sessions):
            await enqueue_trigger(
                Outbox(sessions),
                organisation["tenant"],
                organisation["work_item_id"],
                TriggerKind.SAMPLE_FLOW,
            )

        crashing = CrashingPublisher()
        with pytest.raises(SystemExit):
            async with UnitOfWork(sessions):
                await dispatch_once(Outbox(sessions), crashing, batch_size=10)

        assert crashing.published == [str(organisation["work_item_id"])]

        # The row was never marked, so the next pass publishes it again.
        recovered = RecordingPublisher()
        async with UnitOfWork(sessions):
            result = await dispatch_once(Outbox(sessions), recovered, batch_size=10)

        assert result.published == 1
        assert recovered.published == [str(organisation["work_item_id"])]


class TestAFailingTransportDoesNotLoseTheRow:
    """Bounded attempts, then undispatchable — never silently dropped."""

    async def test_a_publish_failure_leaves_the_row_for_the_next_pass(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        async with UnitOfWork(sessions):
            await enqueue_trigger(
                Outbox(sessions),
                organisation["tenant"],
                organisation["work_item_id"],
                TriggerKind.SAMPLE_FLOW,
            )

        async with UnitOfWork(sessions):
            result = await dispatch_once(
                Outbox(sessions), RecordingPublisher(fail=True), batch_size=10
            )

        assert result.failed == 1
        assert result.published == 0

        async with UnitOfWork(sessions):
            still_pending = await Outbox(sessions).undispatched(10)
        assert len(still_pending) == 1, "a row that failed to publish is never dropped"

    async def test_the_envelope_rebuilt_from_the_row_carries_only_the_contract_fields(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """The durable row must not smuggle authority the message may not carry."""
        async with UnitOfWork(sessions):
            await enqueue_trigger(
                Outbox(sessions),
                organisation["tenant"],
                organisation["work_item_id"],
                TriggerKind.SAMPLE_FLOW,
            )

        # Read in a *separate* unit of work. `undispatched` opens its own read session, so it
        # cannot see an uncommitted row — which is the correct behaviour and worth stating: the
        # dispatcher must only ever publish what has actually committed.
        async with UnitOfWork(sessions):
            rows = await Outbox(sessions).undispatched(10)

        assert set(rows[0].payload) == {"workItemId", "correlationId"}
        envelope = envelope_from_row(rows[0])
        assert envelope.work_item_id == organisation["work_item_id"]
        assert envelope.kind is TriggerKind.SAMPLE_FLOW
