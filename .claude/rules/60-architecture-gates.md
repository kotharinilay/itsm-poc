# 60 — Architecture gates, conformance and cross-gate ordering

**Scope: repository-wide.**

Four gates already exist, each defined in exactly one file. **This file defines none of them.** It
owns the two things that sit *between* them and belong to no single gate:

1. **Ordering** when more than one gate fires on the same change (§60.3).
2. **Conformance findings** — what to do when the implementation and an authoritative architecture
   document disagree (§60.4).

Duplicating a gate's rules here would create a second, drifting statement of it. Where this file
needs a gate's content, it names the file and section and stops.

---

## 60.1 The gates

| Gate | Fires when | Rule | Skill | Hook |
|---|---|---|---|---|
| **Database** | the change needs a schema/database change | `.claude/rules/50-database.md` | `db-change` | H2 `db_migration_guard.py` |
| **LangGraph** | the change touches nodes, edges, routing, topology, state, interrupts, resume, execution ordering, termination, checkpoint persistence or side-effect boundaries | `.claude/rules/30-langgraph.md` | `langgraph-change` | H3 `langgraph_change_guard.py` |
| **ADR** | the change alters architecture, identity/authority, or an engineering-baseline rule | `.claude/rules/70-adr.md` | `adr-author` | H5 `adr_structure_guard.py` |
| **Functional record** | verified behavior changed | `.claude/rules/90-functional-knowledge.md` | `functional-update` | none, deliberately |

Every one of them shares the same shape, and the shape is the point:

```text
DETECT (before implementation)  →  STOP  →  DESCRIBE  →  human APPROVAL / ACCEPTANCE
                                →  IMPLEMENT  →  TEST  →  VERIFY
```

**Detection happens before implementation, not during it.** A gate discovered halfway through
writing code is a governance failure even when the resulting change is correct. If it is discovered
late: stop there, set aside the edits that depend on it, say plainly that the ordering was broken,
and restart at DETECT.

## 60.2 Approval is never inferred

`.claude/rules/00-authority.md` §00.10 states the non-inference rule once, for all gates. It is not
restated here. Two consequences worth naming at the gate level:

- **Satisfying a hook is not approval.** H2, H3 and H5 fire deterministically on a path. They make a
  gate *visible*; they do not judge whether the change is safe, correct or approved, and they never
  modify a file.
- **Writing an ADR is not accepting it.** Claude writes the record with status `Proposed`. A human
  accepts. Those are two events and the second is not Claude's.

## 60.3 Ordering when gates overlap

There is **exactly one** ordering for each pairing. If a future rule appears to state a different
one, that is a conflict to report (`.claude/rules/00-authority.md` §00.6), not a choice to make.

### Database + ADR
When a DB change turns out to be an architecture change (`.claude/rules/50-database.md` §50.5):

```text
DB: detect → stop → describe DB impact
  → identify the architecture change
  → ADR: describe, write, HUMAN ACCEPTANCE
  → DB implementation and validation   (database first, always)
  → application continuation
```

### LangGraph + ADR
When `.claude/rules/30-langgraph.md` §30.4 classifies the change as architecture-altering:

```text
LangGraph: detect → stop → describe → classify
  → ADR: write, HUMAN ACCEPTANCE
  → implement → test → verify
```

### Database + LangGraph
A change that alters graph behavior *and* checkpoint persistence
(`.claude/rules/50-database.md` §50.6, `.claude/rules/30-langgraph.md` §30.8):

```text
DB ORDERING WINS.
DB detect → describe → (ADR where the DB change is architectural) → acceptance
  → DB implemented and validated
  → then the LangGraph implementation, tested at the graph level
```

**Graph code is not changed first merely because the graph change was the original request.**

### All three
```text
DB detect → describe → ADR → human acceptance
  → DB implemented and validated
  → LangGraph implementation, tested at the graph level
  → verify
  → functional record updated last
```

### The functional record is always last
`.claude/rules/90-functional-knowledge.md` §90.10 — functional documentation is downstream of every
gate and overrides none of them:

```text
DB / LangGraph / ADR governance  →  implementation  →  tests / verification  →  functional-update
```

**Updating `docs/functional/implemented.md` is never a substitute for a gate, and never evidence
that one was satisfied.**

## 60.4 Conformance findings — report, never reconcile

A conformance finding is a place where the implementation differs from A1, A2 or A3.

```text
RECORD what the implementation does, and the observable evidence.
NAME the affected area.
STATE that it is a deferred conformance finding.
DO NOT modify the architecture document.
DO NOT modify application code to match it.
DO NOT decide which side is correct.
```

Resolving one is a separate, human-directed act, and where it changes architecture it is an ADR
under `.claude/rules/70-adr.md` §70.2 A. The wording and placement of a finding in the functional
record are owned by `.claude/rules/90-functional-knowledge.md` §90.7.

**Known findings already recorded, and not to be "corrected" under any current phase:**

| Finding | Recorded in |
|---|---|
| The implemented graph state vocabulary and node names do not match A3 §6.2 name for name (`tenant_id`/`session_id`/`correlation_id`/`governance.treatment`/`decision`/`execution`/`verification` against A3's `tid`/`user_id`/`request_id`/`execution_treatment`/`approval`/`consent`/`action_result`; `GOVERN`/`AWAIT_APPROVAL`/`EXECUTE`/`VERIFY`/`CLOSE` against A3's node names) | `.claude/rules/30-langgraph.md` §30.7 |
| The .NET side uses EF Core for data access while Alembic owns all schema, with no single mechanical check tying the two together | `.claude/rules/50-database.md` §50.7 |

The governed *areas* are unaffected by the naming gap; it is recorded for a later conformance phase.

## 60.5 Baseline deviations are not conformance findings

The two are different and are handled differently.

| | Conformance finding | Baseline deviation |
|---|---|---|
| Implementation differs from | A1/A2/A3 (architecture) | the engineering baseline (`.claude/rules/`) |
| Recorded in | `docs/functional/implemented.md` (§90.7) | `docs/governance/open-items.md` §1 |
| Resolved by | a human decision; an ADR where architecture changes | a human decision; an ADR where the *baseline* changes (§70.2 B) |

Handling for both is the same in the one respect that matters: **record it, preserve the
authoritative source, change nothing on your own initiative**
(`.claude/rules/00-authority.md` §00.7).

## 60.6 The architecture-test surface (evidence, not authority)

These suites are how several architecture and baseline rules are actually enforced. Listed so a
change knows what it must keep green. **They are evidence of what is enforced, never authority for
what should be**, and none of them may be weakened (`.claude/rules/40-testing.md` §40.1).

| Surface | Holds |
|---|---|
| `dotnet/tests/Synthia.ArchitectureTests/` | module isolation, boundary ownership, composition root, service resolution, banned APIs, data-access discipline, identity discipline, edge trust policy, no-write-endpoint, no-migration, no-RagCore-dependency, APIM routing |
| `ragcore/tests/` | graph, checkpoint, governance, idempotency, authorization, isolation, architecture, migration and integration suites |
| `integrations/tests/architecture/` | layering; the ban on importing `ragcore` |
| `build/scripts/check-boundaries.sh` | the cross-deployable boundary, failing CI independently of the test suites |
| `.claude/hooks/test_guards.py` | the governance machinery itself, including the worktree-aware enforcement paths |

A single invariant deliberately has more than one check — the `ragcore` import ban is stated in
`integrations/pyproject.toml`, in `integrations/tests/architecture/test_layering.py` and in
`build/scripts/check-boundaries.sh`. That redundancy is intentional and is not duplication to
consolidate.

## 60.7 What this file does not do

- It does not define any gate. Rules 30, 50, 70 and 90 do.
- It does not create a fifth gate, and it does not extend, narrow or reorder an existing one.
- It does not resolve a conformance finding or a deviation.
- It does not make an architecture test authoritative for architecture.
