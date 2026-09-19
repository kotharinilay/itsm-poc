"""The Integrations principal's privileges, enforced by PostgreSQL (T283, X5).

`FR-INTEG-020`, ADR-0007, migrations 0021–0023.

**Until this file existed, no test anywhere referenced `synthia_integrations`.** The grants were
written, the migrations applied, and the column-scoped `GRANT UPDATE` was described in three
documents as the control behind `FR-INTEG-020` — but nothing had ever *attempted* a forbidden write
and observed it refused. The claim rested on reading DDL.

That is the distinction this module exists to close, and the constitution names it: a protection
named as a hard failure must have a test that fails when the protection is removed. Reading a
`GRANT` statement proves somebody typed it. Only a refused statement proves the database agrees.

**Every refusal is asserted on PostgreSQL's SQLSTATE `42501`, never on application code.** No
repository, no port, no ORM. The statements are raw SQL executed against a real PostgreSQL, so what
is being tested is the database's own answer — the only answer that still holds when the application
is bypassed, rewritten or compromised.

Matching the SQLSTATE rather than an exception class matters more than it looks, and running this
proved it: the asyncpg dialect reports a privilege refusal, a missing table and a wrong column name
as the same `ProgrammingError`. The first version of the audit test below failed on `42703`
(undefined column) and the SQLSTATE check is what refused to let it pass — a refusal test that
"passes" because the column does not exist reports the grant as enforced while checking nothing.

**`SET ROLE` rather than a second connection**, because the role is created `NOLOGIN` (migration
0021) and authenticates as a managed identity in every deployed environment, so it has no password
to connect with and nothing in the repository could hold one. `SET ROLE` drops to that role's
privileges for the remainder of the transaction and PostgreSQL enforces its grants exactly as it
would for a direct connection. :func:`test_set_role_actually_drops_privilege` proves the mechanism
before anything relies on it — a `SET ROLE` that silently failed would make every test below pass
while checking nothing.

**The audit assertion here was inverted by T326.** It used to record that the principal could
not write `platform.audit_event` — a known gap, not a satisfied requirement. Migration 0024 grants
`INSERT` and only `INSERT`, so the tests now assert the append is permitted while the read, the
amendment and the deletion are all still refused.

**Why this lives in RagCore's suite rather than the Integrations Service's.** T283 named
`integrations/tests/security/test_job_grants.py`. These grants are **DDL**, created by RagCore's
migrations, and RagCore owns every migration (ADR-0003, one Alembic chain). Applying them from the
Integrations suite would mean that suite reaching into `ragcore/` for `alembic.ini` and the
revision files — the cross-tree test coupling ADR-0001 and ADR-0007 exist to prevent, and the same
coupling rejected for the identity enforcer in T325. Worse, without it the test would **skip**, and
a skipping grant test is the unexercised control this task exists to remove. The path deviation is
recorded in `tasks.md` against T283.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from uuid import uuid4

import pytest
from sqlalchemy import text

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.security, pytest.mark.integration, pytest.mark.isolation]

INTEGRATIONS_ROLE: Final = "synthia_integrations"
RAGCORE_ROLE: Final = "synthia_ragcore"

RESULT_COLUMNS: Final = (
    "result_status",
    "result_verification",
    "result_execution_id",
    "result_recorded_at",
)
"""The four the Integrations Service may write. Restated here deliberately rather than imported
from the migration: a test that imported the list would pass automatically if somebody widened it.
The duplication is the point — these two lists disagreeing is a failure worth seeing."""

INSTRUCTION_COLUMNS: Final = (
    "catalogue_id",
    "catalogue_version",
    "parameters",
    "tenant_id",
)
"""The instruction. **The Integrations Service cannot rewrite what it was told to do** — it cannot
change the organisation, the capability, its version or its arguments, then execute the result and
record a plausible outcome. Each is asserted individually because each is a separate `GRANT`
omission and a single combined statement would pass if only one were wrongly granted."""

INSUFFICIENT_PRIVILEGE: Final = "42501"
"""PostgreSQL's SQLSTATE for `insufficient_privilege`.

**Matched on the SQLSTATE, not on an exception class name**, and the difference was found by running
this. SQLAlchemy's asyncpg dialect translates every asyncpg error into its own DBAPI shim, so
`type(error.orig).__name__` is `ProgrammingError` for a privilege refusal, a missing table and a
syntax error alike. Asserting on that name would have made this whole module pass on a typo'd table
name — a refusal test that "passes" because the table does not exist is the worst possible outcome
here, because it reports the grant as enforced when nothing was checked.

The dialect does preserve `sqlstate` on the translated error, which is the database's own
unambiguous answer.
"""


async def _insufficient_privilege(engine: AsyncEngine, statement: str) -> str:
    """Run one statement as the Integrations principal and require PostgreSQL to refuse it.

    Args:
        engine: An engine against the migrated database.
        statement: The SQL to attempt.

    Returns:
        The refusal message, so a caller can assert on what the database said.

    Raises:
        AssertionError: When the statement was **permitted**. That is the finding: the grant is
            wider than the architecture says, and the boundary rests on application code.
    """
    from sqlalchemy.exc import DBAPIError

    async with engine.begin() as connection:
        await connection.execute(text(f"SET LOCAL ROLE {INTEGRATIONS_ROLE}"))
        try:
            await connection.execute(text(statement))
        except DBAPIError as error:
            sqlstate = getattr(error.orig, "sqlstate", None)
            assert sqlstate == INSUFFICIENT_PRIVILEGE, (
                f"the statement failed, but on SQLSTATE {sqlstate} rather than "
                f"{INSUFFICIENT_PRIVILEGE}: {error.orig}. A missing table, a constraint or a type "
                "error would otherwise make this test pass for entirely the wrong reason."
            )
            return str(error.orig)

    pytest.fail(
        f"PostgreSQL PERMITTED this statement as {INTEGRATIONS_ROLE}:\n  {statement}\n"
        "The grant is wider than ADR-0007 states, and the boundary now rests on application code."
    )


async def _seed_job(engine: AsyncEngine) -> str:
    """Insert one job row **as the owner**, so there is something to attempt a write against.

    Seeded as the owning role deliberately: the subject under test is what the *Integrations*
    principal may do to an existing instruction, and it cannot create one (asserted below). A
    fixture that could not insert the row would be testing the wrong privilege.

    The chain is `tenant_mapping` → `chat_session` → `work_item` → `integration_job`, because
    `integration_job.work_item_id` carries a foreign key and the row would otherwise be rejected on
    referential integrity rather than reaching any grant.

    Returns:
        The job identifier, as a string.
    """
    tenant_id, entra_tid = str(uuid4()), str(uuid4())
    session_id, work_item_id, requester = str(uuid4()), str(uuid4()), str(uuid4())
    job_id = str(uuid4())

    async with engine.begin() as connection:
        await connection.execute(
            text("""
                INSERT INTO platform.tenant_mapping
                    (tenant_id, entra_tid, display_name, status)
                VALUES (:tenant_id, :entra_tid, 'Grant fixture', 'active')
            """),
            {"tenant_id": tenant_id, "entra_tid": entra_tid},
        )
        await connection.execute(
            text("""
                INSERT INTO platform.chat_session
                    (session_id, tenant_id, requester_oid, state)
                VALUES (:session_id, :tenant_id, :requester, 'conversational')
            """),
            {"session_id": session_id, "tenant_id": tenant_id, "requester": requester},
        )
        await connection.execute(
            text("""
                INSERT INTO platform.work_item
                    (work_item_id, tenant_id, session_id, requested_by_oid, state, approval_state)
                VALUES (:work_item_id, :tenant_id, :session_id, :requester, 'authorized', 'none')
            """),
            {
                "work_item_id": work_item_id,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "requester": requester,
            },
        )
        await connection.execute(
            text("""
                INSERT INTO platform.integration_job (
                    job_id, work_item_id, operation_id, tenant_id,
                    catalogue_id, catalogue_version, parameters, expires_at
                ) VALUES (
                    :job_id, :work_item_id, :operation_id, :tenant_id,
                    'reference.inert_read', 1, '{}'::jsonb, now() + interval '15 minutes'
                )
            """),
            {
                "job_id": job_id,
                "work_item_id": work_item_id,
                "operation_id": str(uuid4()),
                "tenant_id": tenant_id,
            },
        )

    return job_id


# ---------------------------------------------------------------------------
# The mechanism, before anything relies on it
# ---------------------------------------------------------------------------


async def test_the_role_exists_and_cannot_log_in(engine: AsyncEngine) -> None:
    """Created by migration 0021, `NOLOGIN`, and holding no password.

    `NOLOGIN` is the reason these tests use `SET ROLE`. It is also a control in its own right:
    there is no connection string anywhere that could authenticate as this principal, because the
    principal authenticates as a managed identity.
    """
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT rolcanlogin, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :name"
                ),
                {"name": INTEGRATIONS_ROLE},
            )
        ).one_or_none()

    assert row is not None, f"{INTEGRATIONS_ROLE} does not exist; migration 0021 did not apply"
    assert row.rolcanlogin is False
    assert row.rolsuper is False
    assert row.rolbypassrls is False, (
        "the principal can bypass row-level security, which would make every tenant-isolation "
        "guarantee in this platform unenforceable for the one service that reaches customer systems"
    )


async def test_set_role_actually_drops_privilege(engine: AsyncEngine) -> None:
    """**The test that stops every test below passing for the wrong reason.**

    If `SET ROLE` silently failed — a typo in the role name, a connection pooled with a reset
    behaviour, a future driver change — every refusal assertion would run as the owner, be
    permitted, and the suite would report the grants as broken. Or worse, an *absence* assertion
    would pass while nothing was actually restricted.

    So this proves the mechanism twice over: the session reports the role it switched to, and a
    statement the owner can run is observed to fail under it.
    """
    async with engine.begin() as connection:
        before = (await connection.execute(text("SELECT current_user"))).scalar_one()
        await connection.execute(text(f"SET LOCAL ROLE {INTEGRATIONS_ROLE}"))
        after = (await connection.execute(text("SELECT current_user"))).scalar_one()

    assert before != after
    assert after == INTEGRATIONS_ROLE

    # And a real loss of privilege, not merely a changed label: the owner may read this table and
    # the Integrations principal may not.
    await _insufficient_privilege(engine, "SELECT 1 FROM platform.audit_event LIMIT 1")


# ---------------------------------------------------------------------------
# integration_job — the column-scoped grant that is FR-INTEG-020
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("column", INSTRUCTION_COLUMNS)
async def test_writing_an_instruction_column_is_refused_by_postgresql(
    engine: AsyncEngine, column: str
) -> None:
    """**The control behind `FR-INTEG-020`, attempted rather than read.**

    The Integrations Service holds `GRANT UPDATE (result_status, result_verification,
    result_execution_id, result_recorded_at)` and nothing more. An UPDATE touching any other column
    is refused by the database, with a permission error, **before the statement runs**.

    Why it matters that this is the database's answer: a service that could rewrite
    `catalogue_id` or `tenant_id` could change what it was told to do, execute that instead, and
    then record a result that looks entirely consistent with the instruction. No downstream reader
    could detect it, because the instruction and the outcome would agree.
    """
    values = {
        "catalogue_id": "'attacker.capability'",
        "catalogue_version": "999",
        "parameters": "'{\"escalate\": true}'::jsonb",
        "tenant_id": "gen_random_uuid()",
    }[column]

    message = await _insufficient_privilege(
        engine,
        f"UPDATE platform.integration_job SET {column} = {values}",  # noqa: S608 — fixed literals
    )

    assert column in message or "permission" in message.lower()


@pytest.mark.parametrize("column", RESULT_COLUMNS)
async def test_writing_a_result_column_is_permitted(engine: AsyncEngine, column: str) -> None:
    """**The positive half, and it is not a formality.**

    A grant test that only proved refusals would pass just as well against a role granted nothing
    at all — and a principal that could write no result would leave every dispatched job pending
    for ever, which presents as an integration that silently never completes.

    Asserted per column because `GRANT UPDATE (a, b, c, d)` is four privileges, and a typo in the
    migration's column list would remove exactly one of them.
    """
    job_id = await _seed_job(engine)

    # `ck_integration_job_result_is_whole` requires `result_status` and `result_recorded_at` to be
    # set together or not at all, so the two are assigned NULL here — which still requires
    # UPDATE privilege on that column while leaving the constraint satisfied. Assigning a value to
    # one of them alone would fail on the CHECK, and this test would then report a privilege the
    # role does hold as one it does not.
    value = {
        "result_status": "NULL",
        "result_recorded_at": "NULL",
        "result_verification": "'client_attested'::platform.verification_outcome",
        "result_execution_id": "gen_random_uuid()",
    }[column]

    async with engine.begin() as connection:
        await connection.execute(text(f"SET LOCAL ROLE {INTEGRATIONS_ROLE}"))
        result = await connection.execute(
            text(f"UPDATE platform.integration_job SET {column} = {value} WHERE job_id = :job"),  # noqa: S608
            {"job": job_id},
        )
        assert result.rowcount == 1


async def test_the_whole_result_write_the_executor_actually_performs_is_permitted(
    engine: AsyncEngine,
) -> None:
    """**The realistic write**, all four columns at once, as the execution leg performs it.

    The per-column tests above prove each privilege individually; this proves the statement that
    actually ships. A result is recorded **whole or not at all**
    (`ck_integration_job_result_is_whole`), because a status without a timestamp is a half-written
    result — and the reader of that result decides whether a user is told their issue is resolved.
    """
    job_id = await _seed_job(engine)

    async with engine.begin() as connection:
        await connection.execute(text(f"SET LOCAL ROLE {INTEGRATIONS_ROLE}"))
        result = await connection.execute(
            text("""
                UPDATE platform.integration_job
                   SET result_status = 'executed'::platform.integration_result_status,
                       result_verification = 'client_attested'::platform.verification_outcome,
                       result_execution_id = gen_random_uuid(),
                       result_recorded_at = now()
                 WHERE job_id = :job
            """),
            {"job": job_id},
        )

    assert result.rowcount == 1


async def test_an_update_mixing_a_result_and_an_instruction_column_is_refused(
    engine: AsyncEngine,
) -> None:
    """**The realistic attempt**, and the one a column-blind grant would miss.

    Nobody writes `UPDATE ... SET catalogue_id = ...` alone. The shape that would actually appear is
    a legitimate result write with one extra column smuggled alongside it — which is exactly what
    column-level privileges refuse: the statement is rejected as a whole, so the permitted part does
    not land either.
    """
    await _insufficient_privilege(
        engine,
        "UPDATE platform.integration_job "
        "SET result_status = 'executed'::platform.integration_result_status, "
        "    catalogue_id = 'attacker.capability'",
    )


async def test_the_integrations_principal_cannot_create_an_instruction_for_itself(
    engine: AsyncEngine,
) -> None:
    """No `INSERT`. Every execution traces to a row RagCore wrote.

    A principal that could insert its own job row could manufacture authorized work, execute it,
    and produce a complete and internally consistent audit trail for something no human approved.
    """
    await _insufficient_privilege(
        engine,
        "INSERT INTO platform.integration_job ("
        "job_id, work_item_id, operation_id, tenant_id, catalogue_id, catalogue_version, "
        "parameters, expires_at) VALUES ("
        "gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), "
        "'attacker.capability', 1, '{}'::jsonb, now() + interval '1 hour')",
    )


async def test_the_integrations_principal_cannot_remove_the_evidence(engine: AsyncEngine) -> None:
    """No `DELETE`. It cannot remove the record of an instruction it was given."""
    await _insufficient_privilege(engine, "DELETE FROM platform.integration_job")


async def test_the_integrations_principal_may_read_the_instruction(engine: AsyncEngine) -> None:
    """`SELECT` **is** granted, and must be: the executor recovers the organisation, the capability
    and the window from this row and from nothing else (`FR-INTEG-018`)."""
    job_id = await _seed_job(engine)

    async with engine.begin() as connection:
        await connection.execute(text(f"SET LOCAL ROLE {INTEGRATIONS_ROLE}"))
        row = (
            await connection.execute(
                text(
                    "SELECT tenant_id, catalogue_id, catalogue_version, expires_at "
                    "FROM platform.integration_job WHERE job_id = :job"
                ),
                {"job": job_id},
            )
        ).one()

    assert row.catalogue_id == "reference.inert_read"


# ---------------------------------------------------------------------------
# The rest of the read contract, and what is outside it
# ---------------------------------------------------------------------------


READABLE_VIEWS: Final = (
    # Migration 0021: the access check and the credential lookup.
    "vw_tenant_entitlement_v1",
    "vw_connector_credential_ref_v1",
    # Migration 0025: organisation recovery and the execution-time re-check (FR-INTEG-018/019).
    "vw_session_summary_v1",
    "vw_work_item_v1",
    "vw_tenant_v1",
    "vw_governance_catalogue_v1",
)
"""Every view the Integrations Service's own queries select from. Restated rather than imported
from the migrations, for the same reason as :data:`RESULT_COLUMNS`."""

UNREADABLE_VIEWS: Final = (
    "vw_session_message_v1",
    "vw_session_step_v1",
    "vw_message_feedback_v1",
    "vw_audit_event_v1",
    "vw_approval_queue_v1",
    "vw_approval_unexecuted_v1",
    "vw_dashboard_rollup_v1",
)
"""Views carrying transcripts, the actor chain or cross-work aggregates. The service needs none of
them, and a component holding connector credentials must not be able to read them (revision 0021).
"""


@pytest.mark.parametrize("view", READABLE_VIEWS)
async def test_the_views_the_service_queries_are_readable(engine: AsyncEngine, view: str) -> None:
    """Every view the service's code selects from is granted (migrations 0021 and 0025).

    A grant narrower than the code is not least privilege, it is an outage: the catalogue read, the
    organisation recovery and the job load all failed with `42501` before revision 0025.
    """
    async with engine.begin() as connection:
        await connection.execute(text(f"SET LOCAL ROLE {INTEGRATIONS_ROLE}"))
        await connection.execute(text(f"SELECT 1 FROM platform.{view} LIMIT 1"))  # noqa: S608


@pytest.mark.parametrize("view", UNREADABLE_VIEWS)
async def test_content_and_audit_views_stay_unreadable(engine: AsyncEngine, view: str) -> None:
    """Widening to the recovery views did not widen to the content-bearing ones."""
    await _insufficient_privilege(engine, f"SELECT 1 FROM platform.{view} LIMIT 1")  # noqa: S608


@pytest.mark.parametrize(
    "table",
    ["tenant_entitlement", "work_item", "approval", "audit_event", "operation", "chat_session"],
)
async def test_no_base_table_in_the_platform_schema_is_readable(
    engine: AsyncEngine, table: str
) -> None:
    """**The views are the contract, and a base table is not part of it.**

    `tenant_entitlement` is the one that matters most: `vw_tenant_entitlement_v1` deliberately omits
    `credential_reference`, and the credential view is separately granted. Reading the base table
    would collapse that split and hand the entitlement reader the credential reference it was
    designed not to see.
    """
    await _insufficient_privilege(engine, f"SELECT 1 FROM platform.{table} LIMIT 1")  # noqa: S608


async def test_the_integrations_principal_may_append_to_the_one_audit_store(
    engine: AsyncEngine,
) -> None:
    """**Audit does not fork** (`FR-INTEG-024`, migration 0024, T326).

    It appends to `platform.audit_event` — the platform's single audit store, the same table RagCore
    writes — rather than to its own schema. A second audit store would mean two answers to "what
    happened", and the reconciliation between them would be a report nobody runs.

    This assertion was **inverted** by T326. It previously recorded the refusal as a known gap: the
    principal held no grant on this table at all, so `FR-INTEG-024` had no path to satisfy and T307
    was blocked on a migration no task named (analysis finding X8).
    """
    async with engine.begin() as connection:
        await connection.execute(text(f"SET LOCAL ROLE {INTEGRATIONS_ROLE}"))
        result = await connection.execute(
            text("""
                INSERT INTO platform.audit_event (
                    audit_id, tenant_id, occurred_at, action, executed_by, execution_method,
                    outcome, correlation_id, retain_until
                ) VALUES (
                    gen_random_uuid(), gen_random_uuid(), now(), 'integration.executed',
                    'synthia_integrations', 'workload', 'succeeded', 'c',
                    now() + interval '7 years'
                )
            """)
        )

    assert result.rowcount == 1


async def test_the_integrations_principal_cannot_read_the_audit_store(engine: AsyncEngine) -> None:
    """**INSERT without SELECT, which is narrower than RagCore's own grant on this table.**

    Revision 0019 gives RagCore `SELECT, INSERT`; revision 0024 gives this principal `INSERT`
    alone. Reading audit would expose records belonging to other actors and other organisations —
    the table carries no tenant predicate of its own, so the only thing restricting such a query
    would be review. This service has no question that requires reading audit, and it is the
    deployable with an egress path to every customer system, so read access here has the worst
    blast radius on the platform.
    """
    await _insufficient_privilege(engine, "SELECT 1 FROM platform.audit_event LIMIT 1")


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE platform.audit_event SET outcome = 'rewritten'",
        "DELETE FROM platform.audit_event",
    ],
    ids=["update", "delete"],
)
async def test_the_audit_store_stays_append_only(engine: AsyncEngine, statement: str) -> None:
    """The two statements that could rewrite history, and **no principal holds either**.

    Append-only has been this table's rule since revision 0013. Granting `INSERT` in 0024 did not
    weaken it: a service that could amend its own audit record could execute an effect and then
    describe it as something else, which is worse than not recording it at all.
    """
    await _insufficient_privilege(engine, statement)


# ---------------------------------------------------------------------------
# Its own schema: full DML, no DDL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("table", ["execution_record", "outbox_message"])
async def test_it_owns_its_own_schemas_tables(engine: AsyncEngine, table: str) -> None:
    """Full DML on `integration.*` — it writes its own execution records and outbox rows."""
    async with engine.begin() as connection:
        await connection.execute(text(f"SET LOCAL ROLE {INTEGRATIONS_ROLE}"))
        await connection.execute(text(f"SELECT 1 FROM integration.{table} LIMIT 1"))  # noqa: S608
        await connection.execute(text(f"DELETE FROM integration.{table} WHERE false"))  # noqa: S608


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE integration.smuggled (id INT)",
        "ALTER TABLE integration.execution_record ADD COLUMN smuggled INT",
        "DROP TABLE integration.outbox_message",
    ],
    ids=["create", "alter", "drop"],
)
async def test_it_holds_no_ddl_on_its_own_schema(engine: AsyncEngine, statement: str) -> None:
    """**No DDL, even where it owns the data** (ADR-0003, one Alembic chain).

    A process that could migrate at startup would apply schema changes at whatever moment a replica
    happened to boot — during a rolling deploy that is two schema versions serving traffic at once.
    The migration job is the only DDL path, and this is what makes that structural.
    """
    await _insufficient_privilege(engine, statement)


async def test_ragcore_holds_no_access_to_the_integration_schema(engine: AsyncEngine) -> None:
    """The reverse direction, and it completes the split.

    RagCore learns an outcome from the four result columns on **its own** row. It never reads the
    Integrations Service's schema, so the coupling between the two stays one directed edge plus a
    queue rather than a shared table (migration 0023 grants it nothing here).
    """
    from sqlalchemy.exc import DBAPIError

    async with engine.begin() as connection:
        await connection.execute(text(f"SET LOCAL ROLE {RAGCORE_ROLE}"))
        with pytest.raises(DBAPIError) as raised:
            await connection.execute(text("SELECT 1 FROM integration.execution_record LIMIT 1"))

    assert getattr(raised.value.orig, "sqlstate", None) == INSUFFICIENT_PRIVILEGE
