"""The governance record this service appends (T326, `FR-INTEG-024`).

**Audit does not fork.** These assert the row goes to `platform.audit_event` — the platform's one
audit store — and that it records this service as the **executing** principal.

The refusals are enforced by PostgreSQL, not here:
`ragcore/tests/security/test_integration_grants.py` proves the principal may `INSERT` and may not
`SELECT`, `UPDATE` or `DELETE`. What this file covers is what the statement *says*.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from integrations.domain.execution import ExecutionOutcome, ExecutionRecord, VerificationOutcome
from integrations.persistence.audit import AUDIT_ACTION, EXECUTED_BY, AuditWriter

pytestmark = pytest.mark.governance

_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_WORK_ITEM = UUID("22222222-2222-2222-2222-222222222222")
_CORRELATION = "0f9a5f4c-1111-4000-8000-000000000002"


class _Session:
    """Records the statement and bound parameters it was handed."""

    def __init__(self) -> None:
        self.statements: list[str] = []
        self.parameters: list[dict[str, Any]] = []

    async def execute(self, statement: Any, parameters: Any = None) -> None:
        self.statements.append(str(statement))
        self.parameters.append(dict(parameters or {}))


def _execution(
    *,
    outcome: ExecutionOutcome = ExecutionOutcome.SUCCEEDED,
    verification: VerificationOutcome = VerificationOutcome.CLIENT_ATTESTED,
) -> ExecutionRecord:
    return ExecutionRecord(
        job_id=uuid4(),
        tenant_id=_TENANT,
        connector_id="servicenow",
        catalogue_id="reference.inert_read",
        catalogue_version=1,
        idempotency_key="a" * 64,
        outcome=outcome,
        verification=verification,
        correlation_id=_CORRELATION,
        attempted_at=datetime.now(UTC),
        external_reference="INC0010001",
        normalized_result=None,
        completed_at=datetime.now(UTC),
    )


async def _record(execution: ExecutionRecord) -> tuple[_Session, UUID]:
    session = _Session()
    audit_id = await AuditWriter().record(
        session,
        execution,
        work_item_id=_WORK_ITEM,
        occurred_at=execution.attempted_at,
    )
    return session, audit_id


async def test_the_record_goes_to_the_one_platform_audit_store() -> None:
    """Not to this service's own schema.

    **One store, or there are two answers to what happened.**
    """
    session, _ = await _record(_execution())

    statement = session.statements[0]

    assert len(session.statements) == 1
    assert "INSERT INTO platform.audit_event" in statement
    # And NOT into this service's own schema. `integration.` is where the execution record goes;
    # an audit row written there would be a second audit store that nobody reconciles.
    assert "INSERT INTO integration." not in statement


async def test_it_records_this_service_as_the_executing_principal() -> None:
    """The clause `FR-INTEG-024` names, and the one thing this writer can state authoritatively.

    `executed_by` is the **database role name**, not a display string: it is the identifier an
    operator can correlate with a role assignment, a Key Vault audit entry and a PostgreSQL log
    line. A friendly name would be one more mapping to keep current.
    """
    session, _ = await _record(_execution())
    bound = session.parameters[0]

    assert bound["executed_by"] == EXECUTED_BY == "synthia_integrations"
    assert bound["execution_method"] == "workload"
    assert bound["action"] == AUDIT_ACTION


async def test_the_organisation_comes_from_the_recovered_execution_record() -> None:
    """Recovered from durable state, never from the message that triggered the work.

    The audit row's `tenant_id` is the one the executor read from the job row — so a forged or
    malformed command cannot cause an audit record attributed to another organisation.
    """
    execution = _execution()
    session, _ = await _record(execution)

    assert session.parameters[0]["tenant_id"] == execution.tenant_id == _TENANT
    assert session.parameters[0]["work_item_id"] == _WORK_ITEM


async def test_the_actor_chain_is_written_null_and_cannot_be_supplied_by_a_caller() -> None:
    """**The stated residual, asserted so it cannot be filled in carelessly** (T327).

    `requested_by_oid` and `approved_by_oid` live on `work_item` and `approval`, which this
    principal cannot read and must not be granted. They are literal `NULL`s in the statement rather
    than bound parameters, so there is no argument through which a caller could supply them — and a
    parameter that only ever receives `None` is one somebody eventually fills from an untrusted
    source.
    """
    session, _ = await _record(_execution())

    statement, bound = session.statements[0], session.parameters[0]

    assert "NULL, NULL" in statement
    assert "requested_by_oid" not in bound
    assert "approved_by_oid" not in bound

    import inspect

    supplied = set(inspect.signature(AuditWriter.record).parameters)
    assert not {"requested_by", "approved_by", "requested_by_oid", "approved_by_oid"} & supplied


@pytest.mark.parametrize(
    ("outcome", "verification"),
    [
        (ExecutionOutcome.SUCCEEDED, VerificationOutcome.SERVER_CONFIRMED),
        (ExecutionOutcome.FAILED, VerificationOutcome.CLIENT_ATTESTED),
        (ExecutionOutcome.REFUSED_UNENTITLED, VerificationOutcome.CLIENT_ATTESTED),
        (ExecutionOutcome.UNREACHABLE, VerificationOutcome.CLIENT_ATTESTED),
    ],
)
async def test_a_refusal_is_recorded_as_durably_as_a_success(
    outcome: ExecutionOutcome, verification: VerificationOutcome
) -> None:
    """Spec §28. **The action is the same for every outcome; the outcome column carries which.**

    An action string that differed per outcome would make "how many executions did we attempt" a
    query over a set of strings nobody maintains — and a refusal that produced no audit row at all
    would make the governance store record only the cases that worked.
    """
    session, _ = await _record(_execution(outcome=outcome, verification=verification))
    bound = session.parameters[0]

    assert bound["action"] == AUDIT_ACTION
    assert bound["outcome"] == outcome.value
    assert bound["verification"] == verification.value


async def test_the_correlation_identifier_travels_onto_the_audit_record() -> None:
    """One identifier across the gateway hop, both queues and the audit store (`FR-INTEG-024`).

    It is what lets a user quoting an error be followed through an asynchronous, suspendable flow.
    """
    session, _ = await _record(_execution())

    assert session.parameters[0]["correlation_id"] == _CORRELATION


async def test_the_retention_horizon_comes_from_the_database_clock() -> None:
    """`now() + interval` in the statement, not a timestamp computed in this process.

    A horizon computed from a process clock drifts between replicas, so two records written seconds
    apart could be retained for materially different periods.
    """
    session, _ = await _record(_execution())

    assert "now() + interval '7 years'" in session.statements[0]
    assert "retain_until" not in session.parameters[0]


async def test_the_writer_returns_the_audit_identifier_it_generated() -> None:
    """Returned so the caller can correlate in telemetry **without re-reading a table it holds no
    `SELECT` on.**"""
    session, audit_id = await _record(_execution())

    assert isinstance(audit_id, UUID)
    assert session.parameters[0]["audit_id"] == audit_id


async def test_the_writer_opens_no_transaction_of_its_own() -> None:
    """It joins the caller's, so the audit record, the execution record, the result columns and the
    outbox row are durable together or not at all.

    An audit record that committed separately could survive a rolled-back execution — asserting in
    the governance store that an effect happened when it did not. Asserted on the fake: a session
    that was asked to commit or begin would have failed with `AttributeError`, because `_Session`
    implements neither.
    """
    session, _ = await _record(_execution())

    assert not hasattr(session, "commit")
    assert not hasattr(session, "begin")
    assert len(session.statements) == 1
