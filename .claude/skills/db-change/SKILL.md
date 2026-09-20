---
name: "db-change"
description: "Run the mandatory ordered procedure for any change that requires a schema or database change: detect before touching application code, stop, describe the full DB impact, obtain explicit human approval, implement and validate the database first, and only then continue application implementation."
argument-hint: "The change being requested"
user-invocable: true
disable-model-invocation: false
---

# Database change procedure

Governing rule: `.claude/rules/50-database.md`. The rule says **what must be true**; this skill is
**how to do it, in order**. The order is the governance — a step performed out of order is a
governance failure even if every individual step is done well.

Invoke this skill the moment a database change is suspected, before writing application code.

---

## Step A — DETECT

Answer, before any application-code edit: does the requested work change, or require a change to,
any of the following?

- tables
- columns (including type, default, nullability)
- constraints, including invariant-enforcing triggers
- indexes
- views, including published/read views
- migrations — an Alembic revision, the revision graph, or `alembic.ini`
- persistence models that map to the schema (`ragcore/src/ragcore/persistence/**`)
- database roles, principals or grants
- graph checkpoint persistence

How to check rather than guess:

1. Read the models the feature touches: `ragcore/src/ragcore/persistence/models.py` and its
   neighbours.
2. Look for the column, constraint or view the feature assumes. If it is not there, the feature needs
   a schema change.
3. `ls ragcore/migrations/versions/` for the current revision sequence and the head.
4. If the feature stores something new, persists something longer, reads something by a new key, or
   enforces a new invariant — assume yes until the schema proves otherwise.

If the answer is **no** to all of the above: say so in one line and continue with ordinary
implementation. Do not run the rest of this skill.

If the answer is **yes**, or is uncertain: go to Step B. Uncertainty resolves toward yes.

## Step B — STOP

- Stop application implementation now. Do not write "just the interface first".
- If application edits were already made that depend on the unresolved schema change, say plainly
  that the ordering was broken, name the files, and set those edits aside until the DB change is
  approved, implemented and validated.
- Do not work around the missing schema. The prohibited workarounds are listed in
  `.claude/rules/50-database.md` §50.2; if you find yourself designing one, that is the signal that
  this step applies.

## Step C — DESCRIBE

Produce a change-impact record. Keep it concise, but every field appears; "not applicable" is a
value, omission is not.

```markdown
### DB change impact

- Tables:                 <added / changed / removed>
- Columns:                <name, type, default, nullability>
- Constraints:            <PK/FK/unique/check/trigger>
- Indexes:                <added / changed / removed>
- Views:                  <added / changed / removed>
- Migration/revision:     <new revision id>, down_revision <id>, single head: yes/no
- Existing data impact:   <which rows, how>
- Backfill:               <what, by what, online-safe?>
- Nullability transitions:<each NOT NULL added/removed, how existing rows satisfy it>
- Compatibility:          <backward-compatible with the deployed revision? migrations run before
                           revision activation>
- Downgrade/rollback:     <downgrade() behavior; if none or lossy, say what is lost>
- Identity-bearing fields:<which A1 §12.2 fields are touched, or none>
- DB permission changes:  <roles/principals/grants, or none>
- Checkpoint persistence: <impact, or none>
```

Then state the two conclusions the human needs:

- **Security conclusion** — does this change the database-level authorization boundary in any way?
- **Escalation conclusion** — does Step H apply?

## Step D — APPROVAL

- Present the record and ask for explicit approval to proceed with the database change.
- **Wait.** Do not implement while waiting, and do not implement an adjacent piece of application
  code "in the meantime" that depends on the new schema.
- Approval is explicit human assent in this session about this change. Do not infer it from the task
  description, an accepted plan that did not enumerate the schema change, a prior approval for
  another change, silence, the permission mode, or a satisfied hook.
- **This skill never approves the change.** Neither does the hook.
- If approval is refused or the human changes the shape of the change, return to Step C.

## Step E — DB-FIRST IMPLEMENTATION

Only after approval, and only the database:

1. Create the Alembic revision under `ragcore/migrations/versions/`, numbered in sequence, with
   `down_revision` pointing at the current head.
2. Write `upgrade()` and a real `downgrade()`.
3. Update the persistence models so that models match DDL.
4. Do **not** touch application code in this step.

Constraints that hold without exception:

- One head. Do not create a second head and merge it later.
- No DDL at application startup. Migrations run as a gated job before revision activation.
- Do not change the migration mechanism — no EF Core migrations, no second migration tool, no second
  migration directory.

## Step F — VALIDATE THE DATABASE

Run the existing suites, from `ragcore/`:

```bash
uv run pytest -q -m integration        # migrations, persistence, upgrade/downgrade, models-vs-DDL
uv run pytest -q -m "not integration"  # everything that reads the models
```

The revision is validated when: single head holds, upgrade from base succeeds, every downgrade
succeeds, models match DDL, and the existing suites pass.

If something fails, fix the migration. **Never weaken a test to make a migration pass** — no
deletion, no `skip`/`xfail`, no loosened assertion, no narrowed fixture. A failing invariant test
means either the migration is wrong or an invariant is deliberately changing, and the second is a
governance decision that returns to Step C.

## Step G — CONTINUE APPLICATION IMPLEMENTATION

Only after Step F succeeds:

- Resume the application work, including any edits set aside in Step B.
- Re-run the relevant application tests.
- If the application work reveals a second schema gap, restart at Step A. Do not amend the approved
  migration to cover something that was never described and approved.

## Step H — ESCALATION

Route to architecture/ADR governance, rather than proceeding, when the change affects:

- **identity-bearing immutability** — which work-item fields are immutable, how immutability is
  enforced, or how strongly (A1 §12.2);
- **DB authorization or permission boundaries** — roles, principals, grants, or moving an invariant
  out of the database into application code;
- **graph checkpoint persistence** — in which case `.claude/rules/30-langgraph.md` also applies, and
  the database ordering still wins: DB detected, described, approved, implemented and validated
  before any graph code changes;
- **any other architecture boundary** — a new store, a changed residency or classification, a changed
  ownership boundary between the three architecture documents.

For these, explicit approval is not sufficient: an ADR in MADR format under `docs/adr/`, sequentially
numbered with a status field, must exist and be accepted **before** implementation. Do not write the
ADR and then proceed as though it were accepted.

## What this skill must never do

- Approve the change. Human approval is mandatory and is never inferred.
- Implement application code before the database change is approved and validated.
- Hide an unresolved schema change behind application code.
- Weaken, skip or delete a test.
- Change the migration mechanism.
- Fix an architecture-vs-implementation deviation it happens to notice. Report it instead.
