# 50 — Database engineering and database-change control

**Category 7 of the Phase 2 authority model** (`docs/migration/phase-2-authority-model.md` §2.2, §9).
Procedure: `.claude/skills/db-change/SKILL.md`. Deterministic guard: `.claude/hooks/db_migration_guard.py` (H2).

Architecture authority for this file:

- `docs/architecture/identity-plane-final.md` (A1) — §4.5, §12.2: the work item's identity-bearing
  fields, their immutability, and the requirement that immutability is enforced **at the database
  permission boundary, not only in application code**.
- `docs/architecture/Synthia-OverallArchitecture-final.md` (A2) — §8.1: which stores exist and what
  Azure Postgres holds (tenant mapping, chat sessions, work items, approvals and consent, governance
  and script config, **graph checkpoints**, audit log), with classification, residency and lifecycle.
- `docs/architecture/RagAgent-Architecture-final.md` (A3) — §6.2: the work item is the authoritative
  record; graph state holds *copies of* trusted context, never its source.

No other repository document is authority for this file. Existing implementation is evidence of what
**is**, never authority for what **should be**.

---

## 50.1 Why the database is a governance surface, not a persistence detail

In this architecture the database is part of the **authorization boundary**. A1 §12.2 requires that
the workload principal cannot change identity-bearing authorization fields on an existing work item,
and requires that protection to hold at the database permission boundary. A schema change can
therefore silently weaken a security invariant that no application test is looking at.

That is the whole reason the DB gate is ordered **before** application code.

---

## 50.2 The mandatory ordering (non-negotiable)

```text
1. DETECT    Identify that the requested change requires a schema/database change
             BEFORE changing application code.
2. STOP      Stop application implementation.
3. DESCRIBE  Produce the full change-impact record (§50.4).
4. APPROVE   Obtain explicit human approval.
5. IMPLEMENT Implement and validate the DB change FIRST.
   + VALIDATE
6. CONTINUE  Only then continue application implementation.
```

Claude **must**:

- **Identify the DB change before any application-code correction.** Step 1 is the step that is
  usually got wrong. A schema change discovered halfway through writing application code is a
  governance failure, even when the resulting migration is correct.
- **Not quietly discover the schema change mid-implementation.** If it is discovered late, stop at
  that point, set aside the application edits that depend on it, say plainly that the ordering was
  broken, and restart at step 1.
- **Require explicit human approval.** Approval means a human said so, in this session, about this
  change.
- **Never infer approval.** None of the following is approval: the task description implying a schema
  change; a prior approval for a different change; the change being "obviously needed"; an existing
  migration that already did something similar; silence; an accepted plan that did not enumerate the
  schema change; the permission mode in force; the fact that a hook was satisfied.
- **Never use application code to hide an unresolved schema change.** A shim, a computed property, a
  JSON blob column reused as a bag of fields, a nullable-everything model, a side table outside the
  migration set, an in-memory cache standing in for a missing column, a string-encoded composite
  value — all prohibited when used to avoid raising the schema change. So is "leave a TODO and
  proceed".
- **Surface DB-level authorization and security implications** (§50.5) in the description every time,
  including when the answer is "none".

## 50.3 What counts as a database change

Any change to, or any change that requires a change to:

- tables, columns, data types, defaults
- constraints (PK, FK, unique, check), including triggers that enforce an invariant
- indexes
- views, including published/read views
- enumerations persisted in the schema
- Alembic revisions, the revision graph, or `alembic.ini`
- ORM persistence models that map to the schema (`ragcore/src/ragcore/persistence/**`)
- database roles, principals, grants, row/column privileges
- graph checkpoint persistence (§50.6)
- retention, erasure or residency behavior realised in the database

If the requested feature cannot work against the schema as it stands today, that is a database
change — regardless of whether a migration file has been opened yet.

## 50.4 Mandatory content of the step-3 description

The change-impact record must state all of the following. "Not applicable" is an acceptable value;
omission is not.

1. **Tables** added/changed/removed.
2. **Columns** added/changed/removed, with types and defaults.
3. **Constraints** added/changed/removed, including invariant-enforcing triggers.
4. **Indexes** added/changed/removed.
5. **Views** added/changed/removed.
6. **Migration/revision**: the new Alembic revision id, its `down_revision`, and confirmation that
   `ragcore/migrations/` still has a **single head**.
7. **Existing data impact**: which rows are affected and how.
8. **Backfill requirements**: what must be backfilled, by what, and whether it is online-safe.
9. **Nullability transitions**: every NOT NULL added or removed, and how existing rows satisfy it.
10. **Compatibility impact**: whether the change is backward-compatible with the currently deployed
    application revision, since migrations run as a gated job **before** revision activation.
11. **Downgrade/rollback path**: the `downgrade()` behavior. If there is none, or it is lossy, say so
    explicitly and say what is lost.
12. **Identity-bearing fields affected** (A1 §12.2 — see §50.5).
13. **Database permission changes**: any change to principals, roles or grants.
14. **Checkpoint persistence impact**, when applicable (§50.6).

## 50.5 Identity-bearing fields and the DB permission boundary

A1 §12.2 names the fields that are conceptually immutable after creation on a work item:

```text
tenant_id, requested_by_oid, requester_role, requested action, target,
approval requirement, approved_by_oid (once recorded), approved_at (once recorded)
```

The workload may update only execution-owned fields: `status`, lease/execution state, `outcome`,
`executed_by`, execution mechanism metadata, execution timestamps.

Rules:

- A change that alters **which** fields are immutable, **how** immutability is enforced, or the
  **strength** of that enforcement, is an **architecture change** under A1 §12.2. Stop and require an
  ADR before implementing (Phase 2 §6.2, §9.5). Approval alone is not sufficient.
- A change to **database permission boundaries** — roles, principals, grants — or moving an invariant
  out of the database into application code is likewise an architecture change requiring an ADR. A1
  §12.2 requires the database-level control specifically.
- Adding a new identity-bearing or authority-bearing field means the immutability question is
  answered in the description, not deferred.

## 50.6 Checkpoint persistence and the LangGraph interaction

Graph checkpoints live in Azure Postgres (A2 §8.1). In this repository the checkpoint tables live in
their own `langgraph` schema, versioned by the checkpoint library's own `setup()`, which Alembic
excludes from autogenerate; Alembic owns `platform`.

When a change touches **both** graph behavior and checkpoint persistence:

```text
DB governance takes ordering precedence.
Detect DB change -> stop -> describe DB impact -> obtain approval
                 -> implement and validate DB -> then continue LangGraph implementation.
```

Graph code is not changed first merely because the graph change was the original request. See
`.claude/rules/30-langgraph.md` §30.8.

A change that would introduce a **second durable checkpoint store**, add a foreign key across the
work-item/checkpoint boundary, or move checkpoint DDL to application startup contradicts the stated
architecture and requires an ADR, not merely approval.

## 50.7 The repository's migration facts (evidence, preserved as-is)

Observed facts about the repository as it stands. This phase governs around them; it does not change
them.

| Fact | Where it is visible |
|---|---|
| Alembic, under Python/RagCore, is the schema migration mechanism | `ragcore/alembic.ini`, `ragcore/migrations/` |
| There is a **single migration ownership model** across the separate Python deployables | `ragcore/migrations/versions/` holds revisions `0001`-`0025`; `integrations/` has no migrations directory |
| Revisions `0020`-`0025` are the **integrations schema**, owned through RagCore migrations | `0020_integration_schema` ... `0025_integrations_recovery_views` |
| The .NET side owns **no** migrations | `dotnet/tests/Synthia.ArchitectureTests/NoMigrationTests.cs` |
| Work-item immutability is enforced by a database trigger, not a convention | `ragcore/migrations/versions/0017_work_item_immutability.py` |
| Database principals are separated - the migration job holds DDL, the runtime holds DML/SELECT | `ragcore/migrations/versions/0019_database_principals.py` |
| Migration validation already exists in CI: single head, upgrade from base, models-match-DDL, every downgrade | `.github/workflows/migrations.yml`, `ragcore/tests/migrations/` |
| Migrations run as a gated job **before** revision activation, never at application startup | `.github/workflows/migrations.yml`; `ragcore/src/ragcore/graph/checkpointer.py` |

**Do not change the migration mechanism under this rule.** Do not introduce EF Core migrations, a
second migration tool, a second migration directory, or startup-time DDL.

**Recorded deviation, not corrected here:** the .NET side uses EF Core for data access
(`dotnet/Directory.Packages.props` and the module `.csproj` files) while Alembic owns all schema. The
split is deliberate and is enforced by `NoMigrationTests`, but it means an EF model change can drift
from the Alembic-owned schema with no single mechanical check tying the two together. Recorded for a
later conformance phase. **Do not "correct" it under this phase.**

## 50.8 Testing obligations

- Preserve and run the existing migration and persistence tests - `ragcore/tests/migrations/` and
  `ragcore/tests/integration/`, i.e. `uv run pytest -q -m integration` from `ragcore/`.
- A new revision must keep `ragcore/migrations/` at a **single head**.
- Every revision must have a working `downgrade()`, or an explicit, approved statement that it does
  not and why.
- **Never weaken a test to make a migration pass.** Do not delete a test, mark it `skip`/`xfail`,
  loosen an assertion, or narrow a fixture to get a schema change green. If a test now fails, either
  the migration is wrong or the test encoded an invariant that is deliberately changing - and the
  second of those is a governance decision, not an edit.

## 50.9 What the H2 hook does and does not do

`.claude/hooks/db_migration_guard.py` fires deterministically on writes to migration-owned paths. It
exists so that a migration change cannot be silently treated as an ordinary application change. It
does **not** judge whether the change is safe, correct or approved, and it does not modify files.
Satisfying the hook is not approval: the hook is the reminder, this rule is the requirement.
