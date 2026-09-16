"""A duplicate trigger produces **exactly one execution and one effect**.

At-least-once delivery means duplicates are routine traffic, not an incident. This is the Stage 8
gate: the platform must absorb them without a second effect and without an error.

**Two boundaries, and this proves both do their own job:**

1. The **atomic claim** stops a second execution *attempt*. The loser is told it lost and stops —
   promptly, with no lock and no wait.
2. The **idempotency key** stops a second *effect* in the case the claim cannot cover: an attempt
   that acted, reached the far side, and then died before recording. The claim is gone by then;
   the key is not.

The second is the one a naive test misses, because it only appears when the claim is *released* or
re-taken. It is exercised explicitly below rather than left to the first case to imply.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ragcore.domain.governance import CapabilityKind, ExecutionTreatment, RiskTier
from ragcore.domain.identifiers import EntraTenantId, OperationId, PrincipalId, TenantId, WorkItemId
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.domain.work import ApprovalState, SessionState, WorkItemState
from ragcore.execution.idempotency import derive_key
from ragcore.messaging.sample_flow import SAMPLE_OPERATION_ID, execute_sample_flow
from ragcore.persistence import models
from ragcore.persistence.engine import UnitOfWork
from ragcore.persistence.repositories import IdempotencyStore, WorkItemRepository

pytestmark = pytest.mark.integration


class RecordingNotifier:
    """Counts deliveries. A notification is a leaf, so this only ever observes."""

    def __init__(self) -> None:
        self.delivered: list[str] = []

    async def notify_user(self, principal_id: Any, envelope: Any) -> None:
        self.delivered.append(envelope.kind.value)


@pytest.fixture(name="work")
async def work_fixture(sessions: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
    """One organisation with one unclaimed work item, ready to be triggered."""
    tenant_id, entra_tid = uuid4(), uuid4()
    session_id, work_item_id, requester = uuid4(), uuid4(), uuid4()
    operation_id = uuid4()

    tenant = TenantContext.from_admitted_identity(
        TenantId(tenant_id), EntraTenantId(entra_tid), TenantStatus.ACTIVE
    )
    key = derive_key(tenant, WorkItemId(work_item_id), OperationId(operation_id))

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
                # Inside its window. The claim predicate requires this, and rightly: work past
                # its expiry is not claimable, and that is a `False` reported as an expiry rather
                # than an error (spec FR-EXEC-001).
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            )
        )

        # The inert reference fixture in the catalogue. `is_reference_fixture=True` and
        # `requires_elevation=False` are the two flags that keep it inert; `AUTO` treatment means
        # no human decision is involved, which is what makes a sample flow safe to run in a
        # scaffold where the approval handlers are deliberately unbuilt.
        await session.execute(
            insert(models.GOVERNANCE_RECORD).values(
                catalogue_id=SAMPLE_OPERATION_ID,
                version=1,
                kind=CapabilityKind.READ.value,
                default_treatment=ExecutionTreatment.AUTO.value,
                accepted_roles=[],
                is_reference_fixture=True,
                requires_elevation=False,
                risk_tier=RiskTier.INFORMATIONAL.value,
            )
        )
        # The operation and its RESERVED idempotency row, as the catalogue write would create
        # them. `IdempotencyStore.remember` updates this row rather than inserting one, and that
        # is deliberate: the window between "started" and "finished" is a row with a null outcome,
        # which `replay` reports as None meaning *do not act* rather than *never seen*.
        await session.execute(
            insert(models.OPERATION).values(
                operation_id=operation_id,
                work_item_id=work_item_id,
                tenant_id=tenant_id,
                catalogue_id=SAMPLE_OPERATION_ID,
                catalogue_version=1,
                treatment=ExecutionTreatment.AUTO.value,
                parameters={},
                idempotency_key=key.value,
                status="authorized",
            )
        )
        await session.execute(
            insert(models.IDEMPOTENCY_RECORD).values(
                idempotency_key=key.value,
                operation_id=operation_id,
                tenant_id=tenant_id,
                outcome=None,
            )
        )

    return {
        "tenant": TenantContext.from_admitted_identity(
            TenantId(tenant_id), EntraTenantId(entra_tid), TenantStatus.ACTIVE
        ),
        "work_item_id": WorkItemId(work_item_id),
        "operation_id": OperationId(operation_id),
        "requester": PrincipalId(requester),
    }


async def _consume(
    sessions: async_sessionmaker[AsyncSession], work: dict[str, Any], notifier: Any
) -> Any:
    """Consume one delivery of the trigger, as the resume worker would."""
    async with UnitOfWork(sessions):
        return await execute_sample_flow(
            work_items=WorkItemRepository(sessions),
            idempotency=IdempotencyStore(sessions),
            notifications=notifier,
            tenant=work["tenant"],
            work_item_id=work["work_item_id"],
            operation_id=work["operation_id"],
            requester=work["requester"],
            correlation_id="corr-duplicate-1",
            now=datetime.now(UTC),
        )


class TestTheClaimAbsorbsTheDuplicate:
    """Boundary 1 — protecting the platform."""

    async def test_two_deliveries_produce_exactly_one_execution(
        self, sessions: async_sessionmaker[AsyncSession], work: dict[str, Any]
    ) -> None:
        notifier = RecordingNotifier()

        first = await _consume(sessions, work, notifier)
        second = await _consume(sessions, work, notifier)

        assert first.claim_won is True
        assert first.had_effect is True

        assert second.claim_won is False
        assert second.executed is False
        assert second.had_effect is False

    async def test_losing_the_claim_is_not_an_error(
        self, sessions: async_sessionmaker[AsyncSession], work: dict[str, Any]
    ) -> None:
        """It is routine traffic.

        Raising here would turn at-least-once delivery into a stream of alerts nobody can act on,
        and an alert channel nobody trusts is one that hides the alert that mattered.
        """
        notifier = RecordingNotifier()
        await _consume(sessions, work, notifier)

        second = await _consume(sessions, work, notifier)  # must not raise
        assert second.claim_won is False

    async def test_exactly_one_notification_is_delivered(
        self, sessions: async_sessionmaker[AsyncSession], work: dict[str, Any]
    ) -> None:
        """The duplicate must not produce a second push either."""
        notifier = RecordingNotifier()

        await _consume(sessions, work, notifier)
        await _consume(sessions, work, notifier)

        assert notifier.delivered == ["work.completed"]


class TestTheIdempotencyKeyAbsorbsWhatTheClaimCannot:
    """Boundary 2 — protecting the external system.

    The case the claim cannot cover: an attempt acted, and then the claim was released — by an
    operator, or by a recovery path — before the outcome was recorded elsewhere.
    """

    async def test_a_second_attempt_after_the_claim_is_released_replays(
        self, sessions: async_sessionmaker[AsyncSession], work: dict[str, Any]
    ) -> None:
        notifier = RecordingNotifier()
        first = await _consume(sessions, work, notifier)
        assert first.had_effect is True

        # Fully release the claim — `claimed_at` AND the state, because the claim predicate
        # requires both. This is the recovery path a human would drive after an execution that
        # reached the far side and then failed before recording. Boundary 1 can no longer help;
        # boundary 2 must.
        async with sessions() as session, session.begin():
            await session.execute(
                update(models.WORK_ITEM)
                .where(models.WORK_ITEM.c.work_item_id == work["work_item_id"].value)
                .values(
                    claimed_at=None,
                    claimed_by=None,
                    state=WorkItemState.AUTHORIZED.value,
                )
            )

        second = await _consume(sessions, work, notifier)

        assert second.claim_won is True, "the claim was released, so this attempt wins it"
        assert second.replayed is True, "but the idempotency key must stop a second effect"
        assert second.had_effect is False

    async def test_exactly_one_idempotency_record_exists(
        self, sessions: async_sessionmaker[AsyncSession], work: dict[str, Any]
    ) -> None:
        """One key, one row, however many deliveries arrive."""
        notifier = RecordingNotifier()
        await _consume(sessions, work, notifier)
        await _consume(sessions, work, notifier)

        async with sessions() as session:
            count = (
                await session.execute(select(func.count()).select_from(models.IDEMPOTENCY_RECORD))
            ).scalar_one()

        assert count == 1

    async def test_the_key_is_derived_and_therefore_stable_across_attempts(
        self, work: dict[str, Any]
    ) -> None:
        """A random key would be a new key each attempt — which is the one thing it must not be.

        The far side recognises a repeat only because the key repeats.
        """
        first = derive_key(work["tenant"], work["work_item_id"], work["operation_id"])
        second = derive_key(work["tenant"], work["work_item_id"], work["operation_id"])
        assert first == second

    async def test_a_different_organisation_derives_a_different_key(
        self, work: dict[str, Any]
    ) -> None:
        """So two organisations cannot collide even if identifiers were ever reused."""
        other = TenantContext.from_admitted_identity(
            TenantId(uuid4()), EntraTenantId(uuid4()), TenantStatus.ACTIVE
        )
        assert derive_key(work["tenant"], work["work_item_id"], work["operation_id"]) != derive_key(
            other, work["work_item_id"], work["operation_id"]
        )
