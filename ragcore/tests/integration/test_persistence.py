"""The persistence foundation against a real PostgreSQL.

Transactions, the outbox, idempotency and recorded decisions.

Everything here needs the actual database, because the properties are the database's: an outbox row
committing atomically with the change it describes, a unique constraint deciding which of two
approvers wins, an ``INSERT ... SELECT`` that checks the requester against the durable row in the
same statement that writes the consent.

**Nothing in this file exercises a business use case.** It exercises the store. There is no triage,
no proposal, no execution — those are use cases the specification has not defined yet, and inventing
one to test the persistence layer would be inventing product (10-principles.md P-8, H-1).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from workers.ingestion_run import close_run, open_run

from ragcore.domain.audit import ActorChain, AuditEventKind, AuditFacts
from ragcore.domain.envelopes import TriggerEnvelope, TriggerKind
from ragcore.domain.governance import (
    ExecutionMethod,
    ExecutionTreatment,
    VerificationOutcome,
)
from ragcore.domain.identifiers import (
    ApprovalId,
    AuditEventId,
    ConsentId,
    CorrelationId,
    EntraTenantId,
    IdempotencyKey,
    OperationId,
    PrincipalId,
    TenantId,
    WorkItemId,
)
from ragcore.domain.ingestion import IngestionRunState
from ragcore.domain.roles import RoleSet, StaffRole
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.domain.work import (
    ApprovalState,
    ApprovalVerdict,
    ConsentVerdict,
    OperationStatus,
    SessionState,
    WorkItemState,
)
from ragcore.persistence import models
from ragcore.persistence.engine import UnitOfWork, current_session
from ragcore.persistence.erasure import UNERASED_BY_DESIGN, erase_tenant
from ragcore.persistence.repositories import (
    ApprovalRepository,
    AuditSink,
    ConsentRepository,
    IdempotencyStore,
    Outbox,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def fixture(sessions: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
    """One organisation, one session, one work item, one proposed operation."""
    tenant_id, entra_tid = uuid4(), uuid4()
    session_id, work_item_id, requester = uuid4(), uuid4(), uuid4()
    operation_id, approval_id = uuid4(), uuid4()
    catalogue_id = "fixture.read_only"

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
                state=SessionState.AWAITING_APPROVAL.value,
            )
        )
        await session.execute(
            insert(models.WORK_ITEM).values(
                work_item_id=work_item_id,
                tenant_id=tenant_id,
                session_id=session_id,
                requested_by_oid=requester,
                state=WorkItemState.AWAITING_DECISION.value,
                approval_state=ApprovalState.PENDING.value,
            )
        )
        await session.execute(
            insert(models.GOVERNANCE_RECORD).values(
                catalogue_id=catalogue_id,
                version=1,
                kind="read",
                default_treatment=ExecutionTreatment.STAFF_APPROVAL.value,
                accepted_roles=["technician"],
                is_reference_fixture=True,
                requires_elevation=False,
                risk_tier="informational",
                commands={"steps": ["read"]},
            )
        )
        await session.execute(
            insert(models.OPERATION).values(
                operation_id=operation_id,
                tenant_id=tenant_id,
                work_item_id=work_item_id,
                catalogue_id=catalogue_id,
                catalogue_version=1,
                treatment=ExecutionTreatment.STAFF_APPROVAL.value,
                parameters={"device": "LAPTOP-1"},
                status=OperationStatus.GATED.value,
            )
        )
        await session.execute(
            insert(models.APPROVAL).values(
                approval_id=approval_id,
                tenant_id=tenant_id,
                work_item_id=work_item_id,
                requested_at=datetime.now(UTC),
            )
        )

    return {
        "tenant": TenantContext.from_admitted_identity(
            TenantId(tenant_id), EntraTenantId(entra_tid), TenantStatus.ACTIVE
        ),
        "session_id": session_id,
        "work_item_id": WorkItemId(work_item_id),
        "operation_id": OperationId(operation_id),
        "approval_id": ApprovalId(approval_id),
        "requester": PrincipalId(requester),
        "catalogue_id": catalogue_id,
    }


class TestTheUnitOfWorkIsTheTransactionBoundary:
    """A write outside one is refused, not autocommitted."""

    async def test_a_write_without_a_unit_of_work_is_refused(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """**The outbox depends on this.**

        A repository that opened its own transaction would break it silently.
        """
        outbox = Outbox(sessions)
        envelope = TriggerEnvelope(
            work_item_id=fixture["work_item_id"],
            correlation_id=CorrelationId("corr-1"),
            kind=TriggerKind.APPROVAL_GRANTED,
        )
        with pytest.raises(RuntimeError, match="no unit of work"):
            await outbox.enqueue(fixture["tenant"], envelope)

    async def test_a_failed_unit_of_work_rolls_everything_back(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """Partial durability is the failure mode the boundary exists to prevent."""
        outbox = Outbox(sessions)
        envelope = TriggerEnvelope(
            work_item_id=fixture["work_item_id"],
            correlation_id=CorrelationId("corr-1"),
            kind=TriggerKind.APPROVAL_GRANTED,
        )

        with pytest.raises(RuntimeError, match="deliberate"):
            async with UnitOfWork(sessions):
                await outbox.enqueue(fixture["tenant"], envelope)
                raise RuntimeError("deliberate")

        async with sessions() as session:
            count = (
                await session.execute(select(func.count()).select_from(models.OUTBOX_MESSAGE))
            ).scalar_one()
        assert count == 0

    async def test_the_current_session_is_released_afterwards(
        self, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        """A leaked session would hand the next request a closed transaction."""
        async with UnitOfWork(sessions):
            assert current_session() is not None
        with pytest.raises(RuntimeError, match="no unit of work"):
            current_session()


class TestTheTransactionalOutbox:
    """Durability before publication. At-least-once by construction."""

    async def test_the_outbox_row_commits_with_the_change_it_describes(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """One transaction, two writes, both durable or neither."""
        approvals = ApprovalRepository(sessions)
        outbox = Outbox(sessions)

        async with UnitOfWork(sessions):
            decided = await approvals.record_verdict(
                fixture["tenant"],
                fixture["approval_id"],
                PrincipalId(uuid4()),
                RoleSet.of(StaffRole.TECHNICIAN),
                ApprovalVerdict.APPROVED,
                datetime.now(UTC) + timedelta(minutes=15),
            )
            assert decided
            await outbox.enqueue(
                fixture["tenant"],
                TriggerEnvelope(
                    work_item_id=fixture["work_item_id"],
                    correlation_id=CorrelationId("corr-1"),
                    kind=TriggerKind.APPROVAL_GRANTED,
                ),
            )

        async with sessions() as session:
            verdicts = (await session.execute(select(models.APPROVAL.c.verdict))).scalar_one()
            rows = (await session.execute(select(models.OUTBOX_MESSAGE))).all()

        assert verdicts is ApprovalVerdict.APPROVED
        assert len(rows) == 1

    async def test_the_payload_carries_no_authority(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """**No tenant, requester, role, action, target or approval state** (contracts/triggers).

        A consumer reads authority from the durable record, not from the message that woke it —
        which is why a forged or replayed trigger cannot authorize anything.
        """
        outbox = Outbox(sessions)
        async with UnitOfWork(sessions):
            await outbox.enqueue(
                fixture["tenant"],
                TriggerEnvelope(
                    work_item_id=fixture["work_item_id"],
                    correlation_id=CorrelationId("corr-1"),
                    kind=TriggerKind.APPROVAL_GRANTED,
                ),
            )

        async with sessions() as session:
            payload = (await session.execute(select(models.OUTBOX_MESSAGE.c.payload))).scalar_one()

        assert set(payload) == {"workItemId", "correlationId"}
        forbidden = {"tenant", "tenantId", "requester", "roles", "action", "target", "approval"}
        assert not forbidden & set(payload)

    async def test_the_dispatcher_reads_undispatched_rows_in_sequence_order(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """``sequence`` carries the ordering; ``occurred_at`` cannot, because it ties."""
        outbox = Outbox(sessions)
        async with UnitOfWork(sessions):
            for kind in (TriggerKind.APPROVAL_GRANTED, TriggerKind.CONSENT_GRANTED):
                await outbox.enqueue(
                    fixture["tenant"],
                    TriggerEnvelope(
                        work_item_id=fixture["work_item_id"],
                        correlation_id=CorrelationId("corr-1"),
                        kind=kind,
                    ),
                )

        pending = await outbox.undispatched(limit=10)
        assert [row.kind for row in pending] == [
            TriggerKind.APPROVAL_GRANTED.value,
            TriggerKind.CONSENT_GRANTED.value,
        ]
        assert pending[0].sequence < pending[1].sequence

    async def test_a_dispatched_row_leaves_the_queue(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """And its attempt is counted, so a row retried forever becomes visible."""
        outbox = Outbox(sessions)
        async with UnitOfWork(sessions):
            await outbox.enqueue(
                fixture["tenant"],
                TriggerEnvelope(
                    work_item_id=fixture["work_item_id"],
                    correlation_id=CorrelationId("corr-1"),
                    kind=TriggerKind.APPROVAL_GRANTED,
                ),
            )

        [pending] = await outbox.undispatched(limit=10)
        async with UnitOfWork(sessions):
            await outbox.mark_dispatched(pending.outbox_id)

        assert await outbox.undispatched(limit=10) == []
        async with sessions() as session:
            attempts = (
                await session.execute(select(models.OUTBOX_MESSAGE.c.attempts))
            ).scalar_one()
        assert attempts == 1


class TestFirstValidVerdictWins:
    """Settled by a unique constraint, not by whichever request commits last."""

    async def test_a_second_verdict_does_not_change_the_outcome(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """Spec FR-INTR-010. The second decider loses the write, not the row."""
        approvals = ApprovalRepository(sessions)
        first_decider, second_decider = PrincipalId(uuid4()), PrincipalId(uuid4())
        expiry = datetime.now(UTC) + timedelta(minutes=15)

        async with UnitOfWork(sessions):
            assert await approvals.record_verdict(
                fixture["tenant"],
                fixture["approval_id"],
                first_decider,
                RoleSet.of(StaffRole.TECHNICIAN),
                ApprovalVerdict.APPROVED,
                expiry,
            )
        async with UnitOfWork(sessions):
            assert not await approvals.record_verdict(
                fixture["tenant"],
                fixture["approval_id"],
                second_decider,
                RoleSet.of(StaffRole.TECHNICIAN),
                ApprovalVerdict.REJECTED,
                expiry,
            )

        standing = await approvals.decision_for(fixture["tenant"], fixture["work_item_id"])
        assert standing is not None
        assert standing.verdict is ApprovalVerdict.APPROVED
        assert standing.decided_by == first_decider

    async def test_the_roles_held_at_decision_time_are_captured(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """A role removed afterwards must not change what the record says was authorized."""
        approvals = ApprovalRepository(sessions)
        async with UnitOfWork(sessions):
            await approvals.record_verdict(
                fixture["tenant"],
                fixture["approval_id"],
                PrincipalId(uuid4()),
                RoleSet.of(StaffRole.TECHNICIAN),
                ApprovalVerdict.APPROVED,
                datetime.now(UTC) + timedelta(minutes=15),
            )

        standing = await approvals.decision_for(fixture["tenant"], fixture["work_item_id"])
        assert standing is not None
        assert standing.roles_held.contains(StaffRole.TECHNICIAN)

    async def test_the_verdict_is_bound_to_the_catalogue_version_it_was_granted_against(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """A catalogue edit between approval and execution cannot change what was agreed."""
        approvals = ApprovalRepository(sessions)
        async with UnitOfWork(sessions):
            await approvals.record_verdict(
                fixture["tenant"],
                fixture["approval_id"],
                PrincipalId(uuid4()),
                RoleSet.of(StaffRole.TECHNICIAN),
                ApprovalVerdict.APPROVED,
                datetime.now(UTC) + timedelta(minutes=15),
            )

        standing = await approvals.decision_for(fixture["tenant"], fixture["work_item_id"])
        assert standing is not None
        assert standing.bound_to.catalogue_id == fixture["catalogue_id"]
        assert standing.bound_to.version == 1

    async def test_an_undecided_approval_reads_as_none_not_approved(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """**``None`` means undecided, never approved.**"""
        approvals = ApprovalRepository(sessions)
        assert await approvals.decision_for(fixture["tenant"], fixture["work_item_id"]) is None

    async def test_another_organisation_reads_no_decision(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """Authority is read through the tenant filter like everything else."""
        approvals = ApprovalRepository(sessions)
        async with UnitOfWork(sessions):
            await approvals.record_verdict(
                fixture["tenant"],
                fixture["approval_id"],
                PrincipalId(uuid4()),
                RoleSet.of(StaffRole.TECHNICIAN),
                ApprovalVerdict.APPROVED,
                datetime.now(UTC) + timedelta(minutes=15),
            )

        stranger = TenantContext.from_admitted_identity(
            TenantId(uuid4()), EntraTenantId(uuid4()), TenantStatus.ACTIVE
        )
        assert await approvals.decision_for(stranger, fixture["work_item_id"]) is None


class TestConsentIsCheckedAgainstTheDurableRequester:
    """And never against anything the request asserted."""

    async def test_the_work_items_own_requester_may_consent(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """The baseline. The ``INSERT ... SELECT`` finds the row and writes."""
        consents = ConsentRepository(sessions)
        async with UnitOfWork(sessions):
            recorded = await consents.record(
                fixture["tenant"],
                ConsentId(uuid4()),
                fixture["work_item_id"],
                fixture["requester"],
                ConsentVerdict.GRANTED,
            )
        assert recorded

    async def test_somebody_else_cannot_consent_on_the_requesters_behalf(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """Checked in the same statement as the write, so there is no window between them."""
        consents = ConsentRepository(sessions)
        async with UnitOfWork(sessions):
            recorded = await consents.record(
                fixture["tenant"],
                ConsentId(uuid4()),
                fixture["work_item_id"],
                PrincipalId(uuid4()),
                ConsentVerdict.GRANTED,
            )
        assert not recorded

        async with sessions() as session:
            count = (
                await session.execute(select(func.count()).select_from(models.CONSENT))
            ).scalar_one()
        assert count == 0

    async def test_a_consent_never_appears_as_an_approval(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """**Consent never satisfies a ``STAFF_APPROVAL`` requirement** (spec FR-INTR-007).

        Separate tables is the mechanism: there is no ``WHERE kind = ...`` that could conflate them.
        """
        consents = ConsentRepository(sessions)
        approvals = ApprovalRepository(sessions)

        async with UnitOfWork(sessions):
            await consents.record(
                fixture["tenant"],
                ConsentId(uuid4()),
                fixture["work_item_id"],
                fixture["requester"],
                ConsentVerdict.GRANTED,
            )

        assert await consents.decision_for(fixture["tenant"], fixture["work_item_id"]) is not None
        assert await approvals.decision_for(fixture["tenant"], fixture["work_item_id"]) is None


class TestIdempotencyBoundaryTwo:
    """Protecting the external system. Boundary 1 is the claim, and protects the platform."""

    async def _claim_key(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any], key: str
    ) -> None:
        async with sessions() as session, session.begin():
            await session.execute(
                insert(models.IDEMPOTENCY_RECORD).values(
                    idempotency_key=key,
                    tenant_id=fixture["tenant"].tenant_id.value,
                    operation_id=fixture["operation_id"].value,
                )
            )

    async def test_an_unseen_key_replays_nothing(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """No record, no replay — and no permission to treat that as "never happened"."""
        store = IdempotencyStore(sessions)
        assert await store.replay(fixture["tenant"], IdempotencyKey("k-1")) is None

    async def test_a_recorded_outcome_replays_instead_of_acting_again(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """The point of the whole boundary."""
        store = IdempotencyStore(sessions)
        await self._claim_key(sessions, fixture, "k-1")

        async with UnitOfWork(sessions):
            await store.remember(
                fixture["tenant"],
                IdempotencyKey("k-1"),
                fixture["operation_id"],
                {"status": "succeeded"},
            )

        assert await store.replay(fixture["tenant"], IdempotencyKey("k-1")) == {
            "status": "succeeded"
        }

    async def test_a_claimed_but_incomplete_key_replays_nothing_yet(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """The window between claim and completion is a *wait*, not a *go*."""
        store = IdempotencyStore(sessions)
        await self._claim_key(sessions, fixture, "k-1")
        assert await store.replay(fixture["tenant"], IdempotencyKey("k-1")) is None

    async def test_the_key_is_unique_so_a_second_claim_fails(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """**The primary key is what serialises writers**, which is why the row needs no version."""
        from sqlalchemy.exc import IntegrityError

        await self._claim_key(sessions, fixture, "k-1")
        with pytest.raises(IntegrityError):
            await self._claim_key(sessions, fixture, "k-1")

    async def test_another_organisation_cannot_replay_the_outcome(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """Even a globally unique key is read through the tenant filter."""
        store = IdempotencyStore(sessions)
        await self._claim_key(sessions, fixture, "k-1")
        async with UnitOfWork(sessions):
            await store.remember(
                fixture["tenant"], IdempotencyKey("k-1"), fixture["operation_id"], {"ok": True}
            )

        stranger = TenantContext.from_admitted_identity(
            TenantId(uuid4()), EntraTenantId(uuid4()), TenantStatus.ACTIVE
        )
        assert await store.replay(stranger, IdempotencyKey("k-1")) is None


class TestAuditIsAppendOnlyAndSeparatelyRetained:
    """A sink with no amend and no delete, by construction and by grant."""

    async def test_an_event_records_the_whole_actor_chain(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """Who asked, who approved, who did it, and by what means."""
        sink = AuditSink(sessions)
        approver = PrincipalId(uuid4())

        async with UnitOfWork(sessions):
            await sink.record(
                fixture["tenant"],
                AuditEventId(uuid4()),
                CorrelationId("corr-1"),
                ActorChain(
                    executed_by="workload",
                    execution_method=ExecutionMethod.WORKLOAD,
                    requested_by=fixture["requester"],
                    approved_by=approver,
                ),
                AuditFacts(
                    kind=AuditEventKind.EXECUTION_RECORDED,
                    outcome="succeeded",
                    verification=VerificationOutcome.SERVER_CONFIRMED,
                ),
                work_item_id=fixture["work_item_id"],
            )

        async with sessions() as session:
            row = (await session.execute(select(models.AUDIT_EVENT))).one()

        assert row.requested_by_oid == fixture["requester"].value
        assert row.approved_by_oid == approver.value
        assert row.executed_by == "workload"
        assert row.execution_method is ExecutionMethod.WORKLOAD
        assert row.verification is VerificationOutcome.SERVER_CONFIRMED

    async def test_a_refusal_is_recorded_as_durably_as_a_permission(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """Spec FR-AUDIT-003. ``ExecutionMethod.NONE`` is what a refusal records."""
        sink = AuditSink(sessions)
        async with UnitOfWork(sessions):
            await sink.record(
                fixture["tenant"],
                AuditEventId(uuid4()),
                CorrelationId("corr-1"),
                ActorChain(executed_by="platform", execution_method=ExecutionMethod.NONE),
                AuditFacts(kind=AuditEventKind.GATE_REFUSED, outcome="refused"),
            )

        async with sessions() as session:
            row = (await session.execute(select(models.AUDIT_EVENT))).one()
        assert row.action == AuditEventKind.GATE_REFUSED.value
        assert row.execution_method is ExecutionMethod.NONE

    async def test_the_retention_horizon_defaults_to_seven_years(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """Stamped at write time, from the database's own clock."""
        sink = AuditSink(sessions)
        async with UnitOfWork(sessions):
            await sink.record(
                fixture["tenant"],
                AuditEventId(uuid4()),
                CorrelationId("corr-1"),
                ActorChain(executed_by="platform", execution_method=ExecutionMethod.NONE),
                AuditFacts(kind=AuditEventKind.TENANT_ADMITTED, outcome="admitted"),
            )

        async with sessions() as session:
            row = (await session.execute(select(models.AUDIT_EVENT))).one()

        assert row.retain_until - row.occurred_at == timedelta(days=365 * 7)

    async def test_two_sources_for_the_horizon_are_refused(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """An audit record with an arguable retention is one nobody can rely on."""
        sink = AuditSink(sessions)
        with pytest.raises(ValueError, match="one source"):
            async with UnitOfWork(sessions):
                await sink.record(
                    fixture["tenant"],
                    AuditEventId(uuid4()),
                    CorrelationId("corr-1"),
                    ActorChain(executed_by="platform", execution_method=ExecutionMethod.NONE),
                    AuditFacts(kind=AuditEventKind.TENANT_ADMITTED, outcome="admitted"),
                    retain_until=datetime.now(UTC),
                    retention_overrides={"audit": 1},
                )

    def test_the_sink_offers_no_way_to_amend_or_remove(self) -> None:
        """Structural. The grant enforces it; the absence of a method makes it legible."""
        public = {name for name in vars(AuditSink) if not name.startswith("_")}
        assert not public & {"amend", "update", "delete", "remove", "purge"}


class TestTheCatalogueRefusesWhatAlphaDoesNotPermit:
    """Constraints, so the rule is a property of the store rather than of the loader."""

    async def test_an_entry_requiring_elevation_is_rejected(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """**Alpha permits no elevation** (ADR-0004), enforced by a CHECK constraint."""
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError, match="alpha_permits_no_elevation"):
            async with sessions() as session, session.begin():
                await session.execute(
                    insert(models.GOVERNANCE_RECORD).values(
                        catalogue_id="fixture.elevated",
                        version=1,
                        kind="action",
                        default_treatment=ExecutionTreatment.STAFF_APPROVAL.value,
                        accepted_roles=["technician"],
                        is_reference_fixture=True,
                        requires_elevation=True,
                        risk_tier="low_impact",
                    )
                )

    async def test_an_agent_message_cannot_name_a_principal(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """No principal authored it, so writing a synthetic one is refused at the database."""
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError, match="agent_messages_carry_no_principal"):
            async with sessions() as session, session.begin():
                await session.execute(
                    insert(models.MESSAGE).values(
                        message_id=uuid4(),
                        session_id=fixture["session_id"],
                        tenant_id=fixture["tenant"].tenant_id.value,
                        sender_kind="agent",
                        sender_oid=uuid4(),
                        body="I did this.",
                    )
                )


class TestTheIngestionRunRecord:
    """The run record, and nothing else — no acquisition, chunking or embedding."""

    async def test_a_run_opens_and_closes_with_its_watermark(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """The watermark is written with the terminal state, in one statement."""
        async with UnitOfWork(sessions) as uow:
            run_id = await open_run(uow.session, fixture["tenant"], "sharepoint", None)

        async with UnitOfWork(sessions) as uow:
            closed = await close_run(
                uow.session,
                fixture["tenant"],
                run_id,
                IngestionRunState.COMPLETED,
                watermark="2026-09-16T00:00:00Z",
                document_count=12,
                expected_version=1,
            )
        assert closed

        async with sessions() as session:
            row = (await session.execute(select(models.INGESTION_RUN))).one()
        assert row.state is IngestionRunState.COMPLETED
        assert row.watermark == "2026-09-16T00:00:00Z"
        assert row.document_count == 12

    async def test_a_run_cannot_close_as_running(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """There is no ``partial``, and ``running`` is not a place to stop."""
        async with UnitOfWork(sessions) as uow:
            run_id = await open_run(uow.session, fixture["tenant"], "sharepoint", None)

        with pytest.raises(ValueError, match="terminal"):
            async with UnitOfWork(sessions) as uow:
                await close_run(
                    uow.session,
                    fixture["tenant"],
                    run_id,
                    IngestionRunState.RUNNING,
                    watermark=None,
                    document_count=0,
                    expected_version=1,
                )

    def test_the_run_record_references_no_authority(self) -> None:
        """**Ingestion never writes authority**, and the table gives it nowhere to."""
        targets = {key.target_fullname for key in models.INGESTION_RUN.foreign_keys}
        assert targets == {"platform.tenant_mapping.tenant_id"}


class TestErasureIsAHardDelete:
    """Spec FR-AUDIT-006. A flag would satisfy a query filter and nothing else."""

    async def test_every_platform_row_for_the_organisation_is_removed(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """Rows, not flags — and the counts come back as the evidence it happened."""
        async with sessions() as session, session.begin():
            removed = await erase_tenant(session, fixture["tenant"])

        assert removed["work_item"] == 1
        assert removed["chat_session"] == 1
        assert removed["tenant_mapping"] == 1

        async with sessions() as session:
            for table in (models.WORK_ITEM, models.CHAT_SESSION, models.TENANT_MAPPING):
                count = (
                    await session.execute(select(func.count()).select_from(table))
                ).scalar_one()
                assert count == 0

    async def test_another_organisation_is_untouched(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """Erasure is per organisation, as narrowly as every other statement."""
        stranger = TenantContext.from_admitted_identity(
            TenantId(uuid4()), EntraTenantId(uuid4()), TenantStatus.ACTIVE
        )
        async with sessions() as session, session.begin():
            removed = await erase_tenant(session, stranger)

        assert sum(removed.values()) == 0
        async with sessions() as session:
            count = (
                await session.execute(select(func.count()).select_from(models.WORK_ITEM))
            ).scalar_one()
        assert count == 1

    async def test_audit_is_deliberately_left_behind(
        self, sessions: async_sessionmaker[AsyncSession], fixture: dict[str, Any]
    ) -> None:
        """**Named, not forgotten.** The runtime holds no ``DELETE`` on ``audit_event``.

        Erasing the record of what was authorized has legal weight; it belongs to a privileged,
        separately-audited job rather than to a repository helper.
        """
        sink = AuditSink(sessions)
        async with UnitOfWork(sessions):
            await sink.record(
                fixture["tenant"],
                AuditEventId(uuid4()),
                CorrelationId("corr-1"),
                ActorChain(executed_by="platform", execution_method=ExecutionMethod.NONE),
                AuditFacts(kind=AuditEventKind.TENANT_REFUSED, outcome="refused"),
            )

        async with sessions() as session, session.begin():
            removed = await erase_tenant(session, fixture["tenant"])

        assert "audit_event" not in removed
        assert {"audit_event"} == UNERASED_BY_DESIGN

        async with sessions() as session:
            count = (
                await session.execute(select(func.count()).select_from(models.AUDIT_EVENT))
            ).scalar_one()
        assert count == 1
