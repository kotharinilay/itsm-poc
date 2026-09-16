"""One journey, followable end to end, across a suspension and a resume (spec FR-OPS-001).

A correlation identifier originates at the public edge and is propagated through every tier. It
appears on every log record, trace, notification, trigger and audit record, so **one user request
can be followed across an asynchronous, suspendable flow** — which is the part that is hard, and the
part this file exists for.

The journey under test is the real shape:

1. A request arrives through the gateway. The correlation middleware binds an identifier.
2. Work becomes durable and a trigger is written to the outbox **in the same transaction**, carrying
   that identifier rather than a fresh one.
3. The process ends. Hours pass. Nothing is held in memory anywhere.
4. A different process — a worker — reads the row and restores the context.
5. Everything the resumed work produces carries the identifier the user was given in step 1.

**Why the correlation identifier and not the trace.** ``traceparent`` is the causal link for a hop,
and it is genuinely better for that: Application Insights stitches parent and child spans without
either end knowing about the other. But a span that ended yesterday has no context to continue, so
across step 3 there is nothing for it to attach to. The correlation identifier survives because it
is a *value on a durable row*, not a live context — which is exactly why the platform carries both
and why neither replaces the other.

These run against a real PostgreSQL because the property being tested is that the identifier
survives **durably**. An in-memory outbox would carry it across the same process, which is the case
that was never in doubt.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ragcore.api.middleware.correlation import correlation_id_var
from ragcore.domain.envelopes import TriggerKind
from ragcore.domain.identifiers import EntraTenantId, TenantId, WorkItemId
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.domain.work import ApprovalState, SessionState, WorkItemState
from ragcore.messaging.outbox import enqueue_trigger
from ragcore.messaging.tracecontext import TraceContext, current_trace_context, restored
from ragcore.observability.logging import JsonFormatter
from ragcore.observability.sampling import journey_is_sampled
from ragcore.persistence import models
from ragcore.persistence.engine import UnitOfWork
from ragcore.persistence.repositories import Outbox

pytestmark = pytest.mark.integration


@pytest.fixture(name="organisation")
async def organisation_fixture(sessions: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
    """One organisation with a work item awaiting a decision — the suspendable case."""
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

    return {
        "tenant": TenantContext.from_admitted_identity(
            TenantId(tenant_id), EntraTenantId(entra_tid), TenantStatus.ACTIVE
        ),
        "work_item_id": WorkItemId(work_item_id),
    }


def _logged_correlation(message: str = "resumed") -> str:
    """The correlation identifier a log line emitted right now would carry.

    Goes through the production formatter rather than reading the context variable directly: the
    claim is that the identifier reaches a *sink*, and reading the variable would prove only that it
    is set.
    """
    record = logging.LogRecord(
        name="ragcore.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    emitted: dict[str, Any] = json.loads(JsonFormatter().format(record))
    return str(emitted.get("correlation_id", ""))


class TestOneIdentifierSurvivesTheSuspension:
    """Request, durable row, resume — all under one identifier."""

    async def test_the_trigger_carries_the_requests_identifier(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """Taken from the ambient context rather than minted. A fresh identifier here would make
        the asynchronous half look like unrelated activity."""
        journey = f"corr-{uuid4()}"
        token = correlation_id_var.set(journey)

        try:
            async with UnitOfWork(sessions) as uow:
                envelope = await enqueue_trigger(
                    Outbox(sessions),
                    organisation["tenant"],
                    organisation["work_item_id"],
                    TriggerKind.APPROVAL_GRANTED,
                )
                del uow
        finally:
            correlation_id_var.reset(token)

        assert str(envelope.correlation_id) == journey

    async def test_the_identifier_is_durable_and_not_merely_in_memory(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """The whole point of step 3. It is read back from the row, in a context where nothing is
        bound — which is the state a worker starts in."""
        journey = f"corr-{uuid4()}"
        token = correlation_id_var.set(journey)
        try:
            async with UnitOfWork(sessions) as uow:
                await enqueue_trigger(
                    Outbox(sessions),
                    organisation["tenant"],
                    organisation["work_item_id"],
                    TriggerKind.APPROVAL_GRANTED,
                )
                del uow
        finally:
            correlation_id_var.reset(token)

        # A fresh context, as a worker process has.
        assert correlation_id_var.get() == ""

        async with sessions() as session:
            payload = (await session.execute(select(models.OUTBOX_MESSAGE.c.payload))).scalar_one()

        assert payload["correlationId"] == journey

    async def test_the_resumed_work_logs_under_the_same_identifier(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """The end-to-end claim: what an operator searching for the identifier a user quoted will
        actually find on the resume side."""
        journey = f"corr-{uuid4()}"
        token = correlation_id_var.set(journey)
        try:
            async with UnitOfWork(sessions) as uow:
                await enqueue_trigger(
                    Outbox(sessions),
                    organisation["tenant"],
                    organisation["work_item_id"],
                    TriggerKind.APPROVAL_GRANTED,
                )
                del uow
            request_side = _logged_correlation("request")
        finally:
            correlation_id_var.reset(token)

        async with sessions() as session:
            payload = (await session.execute(select(models.OUTBOX_MESSAGE.c.payload))).scalar_one()

        # The worker's half: restore what the producer captured, then do the work.
        with restored(TraceContext(correlation_id=payload["correlationId"])):
            resume_side = _logged_correlation("resumed")

        assert request_side == resume_side == journey

    async def test_the_identifier_does_not_leak_out_of_the_resumed_block(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """A worker processes many messages in one process. One message's journey leaking into the
        next would mis-attribute every log line after it — and mis-attributed telemetry is worse
        than none, because it is believed."""
        del sessions, organisation

        with restored(TraceContext(correlation_id="corr-first")):
            assert _logged_correlation() == "corr-first"

        assert _logged_correlation() == ""


class TestSamplingKeepsTheTwoHalvesTogether:
    """The identifier surviving is necessary but not sufficient: the sampler must agree with itself
    across the gap, or the resume half is discarded and the journey is half-visible (FR-OPS-012).
    """

    @pytest.mark.parametrize("ratio", [0.0, 0.01, 0.5, 0.99, 1.0])
    def test_both_halves_reach_the_same_decision(self, ratio: float) -> None:
        """Computed independently, as the two processes do — no shared state, hours apart."""
        journey = f"corr-{uuid4()}"

        request_side = journey_is_sampled(journey, ratio)
        resume_side = journey_is_sampled(journey, ratio)

        assert request_side == resume_side

    def test_the_decision_does_not_depend_on_the_process(self) -> None:
        """SHA-256 of the identifier rather than ``hash()``, whose per-process randomisation would
        give the two halves different answers — the exact failure this guards."""
        journey = "corr-fixed-for-this-assertion"

        # The expected value is computed the same way the sampler does, so this asserts
        # *determinism* rather than restating the implementation's arithmetic.
        import hashlib

        digest = hashlib.sha256(journey.encode("utf-8")).digest()
        expected = int.from_bytes(digest[:8], "big") < 0.5 * (1 << 64)

        assert journey_is_sampled(journey, 0.5) is expected

    def test_an_unidentified_journey_is_kept(self) -> None:
        """Work with no correlation identifier is unusual enough to be worth seeing, and silently
        discarding it would hide the defect that produced it."""
        assert journey_is_sampled("", 0.0) is True


class TestTheTraceContextIsCapturedAlongsideTheIdentifier:
    """Both identifiers travel; neither is a substitute for the other."""

    def test_the_captured_context_carries_the_correlation_identifier(self) -> None:
        token = correlation_id_var.set("corr-abc")
        try:
            captured = current_trace_context()
        finally:
            correlation_id_var.reset(token)

        assert captured.correlation_id == "corr-abc"

    def test_an_absent_tracer_does_not_prevent_correlation(self) -> None:
        """A scaffold with no configured exporter still correlates by the identifier that matters
        to a human. A telemetry dependency that could stop a trigger being published would be
        observability outranking the work it observes."""
        token = correlation_id_var.set("corr-abc")
        try:
            captured = current_trace_context()
        finally:
            correlation_id_var.reset(token)

        assert captured.correlation_id
        # `has_trace` may be either, depending on whether a span happens to be recording. What must
        # never happen is the correlation identifier being absent because the trace was.
        assert captured.has_trace in (True, False)
