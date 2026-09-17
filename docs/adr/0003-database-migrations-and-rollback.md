# 0003. Database migrations: Alembic, CI-gated execution, and the rollback policy

- **Status:** Accepted — **extended by [0007](0007-integration-service-boundary.md)**
- **Date:** 2026-09-15 | **Amended:** 2026-09-18
- **Deciders:** Platform architecture owner
- **Related:** [0001 — RagCore owns orchestration and execution](0001-ragcore-owns-orchestration-dotnet-owns-read.md), [0002 — Approval API placement and graph resume path](0002-approval-api-placement-and-graph-resume.md), [0007 — The Integrations Service boundary](0007-integration-service-boundary.md)

> **Extension, not exception — 2026-09-18.** ADR-0007 adds a **second schema owner**. Every rule in
> this record stands: one Alembic project, one gated job, never at application startup,
> expand/contract rather than rollback, views versioned and never altered in place.
>
> What changes is the scope of "the platform schema": the same single Alembic project now applies
> **two** schemas — `platform`, written by RagCore, and `integration`, written by the Integrations
> Service. There is **no second Alembic project and no second migration job**, deliberately: two
> histories against one database would need an ordering discipline nothing enforces.
>
> The Integrations Service is additionally a **third consumer** of published views, which this record
> assumed was the monolith alone. Extending the view contract to a third reader is a real change to
> its scope, not a free reuse, and `contracts/read-views.md` records it.

## Context and Problem Statement

ADR-0001 makes PostgreSQL the shared surface between the two deployables and states that RagCore
owns the migrations for every table it writes, with the .NET monolith reading through views it does
not own. That left three things undefined:

1. What tool manages the Python-side schema, and how it coexists with the LangGraph PostgreSQL
   checkpointer, which creates and versions its own tables.
2. Where migrations execute — at application startup, or as a deliberate step.
3. What "revert" actually means for a schema change that has already run in production.

Constitution Principle IV makes PostgreSQL the single authoritative durable store, so a bad
migration is a platform-wide incident, not a service-local one.

## Decision Drivers

- RagCore is async Python 3.12; the migration tool must work with an async driver.
- Two deployables read one database, so schema drift is a cross-team failure, not a local one.
- Container Apps runs multiple replicas and scales to zero. Anything that runs at startup runs
  concurrently, repeatedly, and at unpredictable times.
- Least privilege (constitution Principle VI, `principles.yaml` P17): a long-running application
  process should not hold DDL rights.
- The platform commits to RPO of 15 minutes or less (constitution Section 2).
- A revert path must exist and must be proven, not assumed.

## Decision Outcome

### 1. Tooling

**Alembic**, bootstrapped from its async template (`alembic init -t async`) against asyncpg, is the
single migration tool for the platform schema — **and, since ADR-0007, for the `integration` schema
too, from the same project and the same history**. `env.py` uses `async_engine_from_config` with
`NullPool` and drives migrations through `connection.run_sync`.

**The .NET monolith runs no migrations at all.** EF Core is used read-only: `Database.Migrate()`,
`EnsureCreated()` and EF Core migration files are prohibited in the monolith, and this is enforced by
an architecture test. The monolith is a consumer of the schema, never its author.

Views that the monolith reads are created and versioned by RagCore's Alembic history, using
`alembic_utils` so that PostgreSQL views are autogeneratable entities rather than hand-written
`op.execute` strings. A view is a **published contract**: changing one is a breaking change and
requires sign-off from the monolith side.

### 2. Two migration systems, disjoint schemas

The LangGraph PostgreSQL checkpointer owns and versions its own tables through its `setup()` routine.
We do not fight it and we do not wrap it.

- The checkpointer is confined to its own PostgreSQL schema (`langgraph`), which it owns entirely.
- Alembic owns the platform schema and **excludes** the `langgraph` schema from autogenerate via
  `include_schemas` / `include_object` in `env.py`, so it never proposes dropping tables it did not
  create.
- No foreign key crosses the boundary. The work item is the authority record; the checkpoint is
  working state (specification §15.6), and the two are joined by identifier in application code, not
  by referential integrity.

### 3. Execution: a gated deploy step, never at startup

Migrations run as a **dedicated Azure Container Apps job** in the release pipeline, before the new
application revision is activated. Running migrations at application startup is prohibited.

Reasons, all of which are disqualifying on their own: replicas race each other at startup;
scale-to-zero makes the timing unpredictable; and a process that migrates at boot must hold DDL
rights for its entire life.

**Database principals are separated accordingly:**

| Principal | Rights |
|---|---|
| Migration job | DDL on the platform schema |
| RagCore runtime | DML and SELECT. No DDL |
| .NET monolith runtime | SELECT on its published views only. No DML, no DDL |

Credentials come from Key Vault via managed identity (constitution Principle IV). The migration job
takes a PostgreSQL advisory lock for its duration, so a retried or overlapping pipeline run cannot
execute two migrations concurrently.

PostgreSQL has transactional DDL, so each migration runs in a transaction and rolls itself back on
failure. The exceptions — `CREATE INDEX CONCURRENTLY`, `ALTER TYPE ... ADD VALUE` — must be wrapped
in `op.get_context().autocommit_block()`, and a migration that does so is explicitly flagged in
review as non-atomic.

### 4. CI gates

Every migration passes these before merge:

| Gate | Enforces |
|---|---|
| `pytest-alembic` `test_single_head_revision` | One head. Catches the diverged history that a merge conflict silently produces |
| `pytest-alembic` `test_upgrade` | Base to head runs clean |
| `pytest-alembic` `test_model_definitions_match_ddl` | `revision --autogenerate` produces an empty diff — models and migrations agree |
| `pytest-alembic` `test_up_down_consistency` | **Every downgrade succeeds** |
| Migration linting (`squawk` or equivalent) | No unqualified `ALTER TABLE`, no non-concurrent index build, nothing that takes a long exclusive lock |
| Human review | Autogenerate is a draft, never a merge. It misses views, triggers, server defaults and enum changes |

### 5. Rollback policy — three layers, in order

This is the part most easily got wrong, so it is stated plainly.

**Layer 1 — every migration is reversible, and that is tested.** Every revision implements
`downgrade()`, and `test_up_down_consistency` proves in CI that the whole history reverses. A
revision without a working downgrade does not merge.

**Layer 2 — expand/contract, so production rollback never needs Layer 1.** Schema changes are
forward-only and backward-compatible in production, applied as a parallel change:

```text
1. Expand   — add the new column/table/view. The currently deployed app ignores it.
2. Deploy   — ship the app version that writes and reads the new shape.
3. Backfill — migrate data, online, in batches.
4. Contract — drop the old column, in a LATER release, once no deployed version references it.
```

Because each step leaves the previous application version working, **rolling back the application is
always a deployment rollback with no schema change at all**. A destructive change and the code that
depends on it never ship in the same release.

**Layer 3 — point-in-time restore, as the last resort.** `downgrade()` is honest about structure but
cannot be honest about data: dropping a column and re-adding it does not bring the values back. For a
migration that has already destroyed data, the recovery mechanism is PostgreSQL point-in-time restore
within the committed RPO of 15 minutes — not `alembic downgrade`.

The contract step is the only routinely destructive one, which is exactly why it is deferred to a
later release than the change that makes it safe.

## Consequences

**Positive.** Schema state is versioned, linear and testable. The revert path exists and is proven on
every commit rather than discovered during an incident. Runtime processes hold no DDL rights.
Expand/contract means an application rollback is never blocked on a database decision.

**Negative / accepted.**

- Expand/contract makes a column removal a two-release operation. This is deliberate and is not to be
  shortcut under delivery pressure.
- Two migration systems exist in one database. They are safe only because their schemas are disjoint,
  and the `env.py` exclusion is load-bearing — a test asserts that autogenerate never proposes a
  change inside the `langgraph` schema.
- The release pipeline gains a job that must complete before the app revision activates, adding a
  step to every deploy that touches the schema.
- The .NET team cannot change the shape it reads without a RagCore-side migration. This is the
  intended cost of the published-view contract from ADR-0001.

## Resolved since acceptance

### Backfills are an operational task, never a migration

A backfill MUST NOT run inside the migration job, because the job gates every deploy and a long
backfill would hold the release. Backfills run as a separate, restartable operational task:

- Batched, with a bounded batch size and a throttle between batches, so the table stays writable.
- **Idempotent and resumable** — it records its own progress and can be stopped and restarted without
  double-applying.
- Runs against the expanded schema while both the old and new shapes are valid, which is exactly the
  window expand/contract creates for it.
- The contract step that drops the old column MUST NOT ship until the backfill has verifiably
  completed.

### Checkpoint retention: 30 days after thread completion

Checkpoints are transient working state, never an authority record (§15.6), so pruning them loses
nothing of record — the work item and the audit trail persist independently. Completed and expired
threads are pruned **30 days after completion**: long enough to reconstruct an incident, short enough
to bound table growth.

Pruning is a scheduled job that **we** own, deleting by thread identifier within the `langgraph`
schema. It deliberately does not depend on the checkpointer library's own deletion surface, which
varies across versions; the pinned version's primitive is used where it exists and owned SQL is the
fallback. Data classification is *transient* under §24.2, and if per-tenant retention configuration
later lands (inherited open item OQ-08), this window becomes that configuration's default rather than
a separate policy.

### View contract sign-off: not required

Superseded by ADR-0001's versioned-view decision. Views are added as `_v2` alongside `_v1` and
dropped a release later, so no per-view owner or sign-off gate exists to define.

## Unresolved

- Nothing outstanding for this decision.

## More Information

- Constitution Section 2 (.NET and Python standards), Principles IV, VI and X.
- Alembic async cookbook: `alembic init -t async`, `async_engine_from_config`, `autocommit_block()`.
- `pytest-alembic` built-in tests; `alembic_utils` for PostgreSQL view entities.
- `Synthia-Platform-Specification.md` §15.6 (checkpoint state is not an authority record), §24.1.
