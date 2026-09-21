"""Message disposition and authority recovery. **Retry policy, and where the tenant comes from.**

Two things this covers that nothing else does:

* the consumer's three dispositions, which **are** the retry and dead-letter policy;
* `JobInstruction.is_executable_at`, which is where authority is re-verified against durable state
  rather than inherited from a caller.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from integrations.domain.catalogue import CapabilityIdentity
from integrations.domain.execution import (
    ExecutionOutcome,
    ExecutionRecord,
    VerificationOutcome,
)
from integrations.execution.executor import ExecutionReport
from integrations.messaging.consumer import CommandConsumer, Disposition
from integrations.persistence.jobs import JobInstruction

pytestmark = pytest.mark.idempotency

_JOB = UUID("77777777-7777-7777-7777-777777777777")
_CORRELATION = "0123abcd-4567-89ef-0123-456789abcdef"
_NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


def _command(**overrides: object) -> str:
    payload: dict[str, object] = {
        "jobId": str(_JOB),
        "correlationId": _CORRELATION,
        "kind": "integration.execute",
    }
    payload.update(overrides)
    return json.dumps(payload)


class _Leg:
    """An execution leg with a fixed verdict."""

    def __init__(self, report: ExecutionReport | None = None, *, raises: bool = False) -> None:
        self._report = report or ExecutionReport(executed=True, outcome=ExecutionOutcome.SUCCEEDED)
        self._raises = raises
        self.calls = 0

    async def run(self, job_id: UUID, correlation_id: str) -> ExecutionReport:
        del job_id, correlation_id
        self.calls += 1
        if self._raises:
            raise RuntimeError("the database went away")
        return self._report


def _instruction(**overrides: object) -> JobInstruction:
    defaults: dict[str, object] = {
        "job_id": _JOB,
        "work_item_id": uuid4(),
        "operation_id": uuid4(),
        "tenant_id": uuid4(),
        "identity": CapabilityIdentity("reference.inert_action", 1),
        "parameters": {},
        "expires_at": _NOW + timedelta(minutes=10),
        "work_state": "authorized",
        "approval_state": "approved",
        "tenant_status": "active",
    }
    defaults.update(overrides)
    return JobInstruction(**defaults)  # type: ignore[arg-type]


# --------------------------------------------------------- disposition: the retry policy


async def test_a_handled_command_completes() -> None:
    """**Positive.** Executed means handled, and the message leaves the queue."""
    handled = await CommandConsumer(_Leg()).handle(_command())  # type: ignore[arg-type]

    assert handled.disposition is Disposition.COMPLETE


async def test_a_refusal_completes_rather_than_dead_lettering() -> None:
    """A refusal is the durable answer, and RagCore has already been told.

    Redelivering would produce the same refusal for ever — a queue that never drains while nothing
    is actually wrong.
    """
    leg = _Leg(ExecutionReport(executed=True, outcome=ExecutionOutcome.REFUSED_UNENTITLED))

    handled = await CommandConsumer(leg).handle(_command())  # type: ignore[arg-type]

    assert handled.disposition is Disposition.COMPLETE


async def test_a_suppressed_duplicate_completes() -> None:
    """A duplicate is a **success of idempotency boundary 2**, not a failure.

    The first delivery already executed and announced; there is nothing left to do.
    """
    leg = _Leg(ExecutionReport(executed=False, outcome=None))

    handled = await CommandConsumer(leg).handle(_command())  # type: ignore[arg-type]

    assert handled.disposition is Disposition.COMPLETE


async def test_an_out_of_contract_field_dead_letters_and_never_executes() -> None:
    """**The negative that matters most.**

    A command carrying an organisation is dead-lettered with a reason, and the execution leg is
    **never reached** — asserted by call count, because "it was refused eventually" is a weaker
    guarantee than "it was refused before anything could happen".
    """
    leg = _Leg()

    handled = await CommandConsumer(leg).handle(_command(tenantId=str(uuid4())))  # type: ignore[arg-type]

    assert handled.disposition is Disposition.DEAD_LETTER
    assert handled.reason == "envelope-contract"
    assert leg.calls == 0


async def test_a_result_kind_on_the_command_queue_dead_letters() -> None:
    """A misconfigured publisher is something a human should see, not something to absorb."""
    leg = _Leg()

    handled = await CommandConsumer(leg).handle(_command(kind="integration.completed"))  # type: ignore[arg-type]

    assert handled.disposition is Disposition.DEAD_LETTER
    assert leg.calls == 0


async def test_an_unknown_job_dead_letters() -> None:
    """A command naming nothing has outlived its data or come from somewhere it should not have."""
    leg = _Leg(ExecutionReport(executed=False, outcome=None, dead_letter=True))

    handled = await CommandConsumer(leg).handle(_command())  # type: ignore[arg-type]

    assert handled.disposition is Disposition.DEAD_LETTER


async def test_a_transient_failure_abandons_for_redelivery() -> None:
    """Abandon, not dead-letter: the failure is the machinery's, before any effect.

    The derived key protects the far side if the effect somehow did land.
    """
    handled = await CommandConsumer(_Leg(raises=True)).handle(_command())  # type: ignore[arg-type]

    assert handled.disposition is Disposition.ABANDON


# --------------------------------------------------- authority recovered from durable state


def test_an_authorized_unexpired_job_is_executable() -> None:
    """**Positive.** Active organisation, approved, inside the window."""
    assert _instruction().is_executable_at(_NOW) is True


def test_an_expired_window_is_not_executable() -> None:
    """Expiry is a normal outcome and produces no execution (spec §29.5, FR-EXEC-001).

    Time passes between a proposal and its execution; this is ordinary, not exceptional.
    """
    instruction = _instruction(expires_at=_NOW - timedelta(seconds=1))

    assert instruction.is_executable_at(_NOW) is False


def test_a_suspended_organisation_is_not_executable() -> None:
    """Approved work MUST NOT execute if the organisation is no longer active (FR-EXEC-003).

    A suspension between proposal and execution is ordinary, and the check is at the point of
    effect precisely because of that.
    """
    assert _instruction(tenant_status="suspended").is_executable_at(_NOW) is False


def test_cancelled_work_is_not_executable() -> None:
    """Cancellation before the claim is a server-side transition that stops execution."""
    assert _instruction(work_state="cancelled").is_executable_at(_NOW) is False


def test_unapproved_work_is_not_executable() -> None:
    """The approval is the authority. Without it there is nothing to spend."""
    assert _instruction(approval_state="pending").is_executable_at(_NOW) is False


# ------------------------------------------------------------------ the honesty constraint


def test_a_refusal_cannot_claim_a_server_confirmed_outcome() -> None:
    """Nothing was attempted, so there was nothing to confirm.

    `server_confirmed` is the single value that may be reported to a user as resolved (ADR-0004),
    and a refusal claiming it would be the platform claiming to know more than it does — a
    hard failure (`.claude/rules/80-security-ops.md` §80.3). The database carries the same
    constraint; this catches it at the
    call site, where the message can name the caller.
    """
    with pytest.raises(ValueError, match="nothing to confirm"):
        ExecutionRecord(
            job_id=_JOB,
            tenant_id=uuid4(),
            connector_id="none",
            catalogue_id="reference.inert_action",
            catalogue_version=1,
            idempotency_key="k" * 64,
            outcome=ExecutionOutcome.REFUSED_UNENTITLED,
            verification=VerificationOutcome.SERVER_CONFIRMED,
            correlation_id=_CORRELATION,
            attempted_at=_NOW,
        )


def test_a_successful_execution_is_attested_not_confirmed_by_default() -> None:
    """The execution leg reports what it observed; RagCore concludes.

    Nobody has read the real state — the call said it worked. Reporting a confirmation here is the
    relabelling ADR-0004 forbids.
    """
    record = ExecutionRecord(
        job_id=_JOB,
        tenant_id=uuid4(),
        connector_id="reference",
        catalogue_id="reference.inert_action",
        catalogue_version=1,
        idempotency_key="k" * 64,
        outcome=ExecutionOutcome.SUCCEEDED,
        verification=VerificationOutcome.CLIENT_ATTESTED,
        correlation_id=_CORRELATION,
        attempted_at=_NOW,
    )

    assert record.verification is VerificationOutcome.CLIENT_ATTESTED
