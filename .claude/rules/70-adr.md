# 70 — Architecture Decision Records and change governance

**Category 8 of the Phase 2 authority model** (`docs/migration/phase-2-authority-model.md` §2.2, §6,
§11). Procedure: `.claude/skills/adr-author/SKILL.md`. Deterministic guard:
`.claude/hooks/adr_structure_guard.py` (H5).

Architecture authority for this file:

- `docs/architecture/identity-plane-final.md` (A1) — the principal, tenant-binding and authority
  rules; the work item's identity-bearing fields and their immutability.
- `docs/architecture/Synthia-OverallArchitecture-final.md` (A2) — platform topology, zones, trust
  boundaries, the stores and their classification, residency and lifecycle.
- `docs/architecture/RagAgent-Architecture-final.md` (A3) — graph topology and state, node contracts,
  the execution authority boundary as RagCore observes it, retrieval architecture, the evaluation
  harness and release gates, and ADR-001…ADR-012 inline.

No other repository document is architecture authority. `docs/architecture/integrations-service-delta.md`
and `docs/architecture/ragcore-langgraph-flow.md` sit in the architecture directory and carry **no**
authority. Neither does `README.md`, `Synthia-Platform-Specification.md`,
`.serena/**`, `docs/current-implementation/**`, or the retired Spec Kit constitution. Existing
implementation is evidence of what **is**, never authority for what **should be**.

Engineering-baseline authority for this file is the migrated `.claude/rules/` baseline itself,
together with the baseline inputs it was migrated from. An ADR is the only instrument that changes
it.

---

## 70.1 What an ADR is, and what it is not

An ADR **records a deliberate decision** to change something that a normative source owns, at the
moment the change is decided, with its context, its alternatives and its consequences.

An ADR is **not** the source of truth for architecture, and it is **not** the source of truth for the
engineering baseline.

| Domain | Normative source | What the ADR does |
|---|---|---|
| Architecture, identity, authority, topology, stores, graph architecture | A1, A2, A3 | Records the decision to change them, and why |
| Engineering / coding baseline | the migrated `.claude/rules/` baseline | Records the decision to change a rule, and why |
| LangGraph workflow architecture | A3, via `.claude/rules/30-langgraph.md` | Records the decision; the rule stays the procedure |
| Database authorization boundary | A1 §12.2 and A2 §8.1, via `.claude/rules/50-database.md` | Records the decision; the rule stays the procedure |

Consequences of that split, all of them binding:

- An accepted ADR does **not** silently amend an architecture document. If the owning document must
  change, that is a separate, explicit edit by a human, and it is outside any Claude-run
  implementation unless the human asks for it directly.
- An ADR never becomes authority by being written, by being long, or by being cited. Only human
  acceptance gives it force, and even then it governs the decision it records, nothing wider.
- `docs/adr/0001`…`0009` are **historical records**. Per
  `docs/migration/phase-2-authority-model.md` §11.4 and `<repository_document_policy>`, their
  *contents* are not a source for reconstructing current architecture or the current baseline. Read
  them for structure and for history; never cite one as the reason a rule now says something.
- An ADR that is *inline in A3* (ADR-001…ADR-012 in `RagAgent-Architecture-final.md` §4) is part of
  an authoritative document and is authoritative. It is a different thing from `docs/adr/NNNN`, and
  the two numbering spaces must never be conflated. Whether that reading is confirmed is **OQ-5** in
  the Phase 2 authority model, still open.

## 70.2 When an ADR is mandatory

An ADR is mandatory — **before implementation** — in each of the following cases. This list is the
union of the Phase 2 gates (§6.2, §6.3, §9.5, §10.4, §1.3) and is not extended here by invention.

### A. Architecture change

The requested work cannot be implemented without changing architecture. Concretely, when it:

1. introduces a new component, service or zone;
2. changes a trust boundary;
3. changes a tenant boundary, or anything about how tenancy is established or enforced;
4. changes identity or authority semantics — who a principal is, what a principal may do, where a
   verdict may come from, what an approval authorizes;
5. changes platform topology — what is deployed, what talks to what, over which hop;
6. introduces a new persistent store, or persists something where architecture does not currently
   permit it, or changes a store's classification, residency or lifecycle;
7. changes architectural ownership between A1, A2 and A3;
8. resolves a **genuine contradiction** between two authoritative architecture documents. Report it,
   stop, require the ADR — never pick a winner silently
   (`docs/migration/phase-2-authority-model.md` §1.3). A cross-reference or filename mismatch is an
   editorial defect, not a contradiction, and needs a human editorial decision rather than an ADR.

### B. Engineering-baseline change

The requested implementation cannot be done without changing an engineering rule. Concretely, when it:

1. relaxes an analyzer severity, or disables an analyzer or rule set;
2. adds to Ruff `ignore` or `per-file-ignores`;
3. adds a `# noqa` without the justification the baseline requires, or a blanket one;
4. adds `#pragma warning disable`, or suppresses a compiler/analyzer warning, without the required
   justification;
5. sets `TreatWarningsAsErrors=false`, overrides `Nullable`, or otherwise weakens nullability or
   warning treatment on a project;
6. changes a mandatory engineering convention — layout, naming, dependency direction, test
   placement, commit or versioning convention;
7. contradicts any migrated baseline rule.

**Observed implementation behavior is not permission to change the baseline.** That an existing file
already carries a suppression, that a rule is already violated somewhere, that CI currently passes
with the violation in place — none of these is authority. They are deviations to report, never a
precedent to extend.

The alternative to bending the baseline is changing the implementation. Reach for the ADR only when
the baseline is genuinely the thing that should change.

### C. LangGraph architecture change

A LangGraph change requires an ADR when it alters architecture or an architectural rule. The concrete
list lives in **`.claude/rules/30-langgraph.md` §30.4** — seventeen named triggers, from execution
authority and side-effect boundaries through approval semantics, signed/idempotent execution, typed
resolution, the two-index retrieval architecture, memory architecture, mandatory tenant filtering and
the evaluation release gates.

That list is not restated here and must not be duplicated, extended or narrowed anywhere else. This
rule adds one thing to it: **every item on §30.4 is an ADR trigger under this rule too**, and the
acceptance requirement in §70.3 applies to it unchanged. Likewise the execution-authority protections
in §30.3 — a change that weakens any of them is architecture-altering by definition.

### D. Database architecture / authorization-boundary change

A database change requires an ADR when it changes:

1. **identity-bearing immutability** — which work-item fields are immutable after creation, how that
   immutability is enforced, or how strongly (A1 §12.2);
2. **database permission boundaries** — roles, principals, grants, row or column privileges;
3. the placement of an invariant — in particular, moving one out of the database into application
   code, which A1 §12.2 specifically forbids;
4. the **stated ownership of checkpoint persistence** — a second durable checkpoint store, a foreign
   key across the work-item/checkpoint boundary, or checkpoint DDL moved to application startup;
5. any other DB boundary that is architectural — a new store, a changed residency or classification,
   a changed ownership boundary between the architecture documents.

The full DB procedure stays in **`.claude/rules/50-database.md`** and is not duplicated here.

## 70.3 Ordering — non-negotiable

```text
1. DETECT     Identify that the requested work requires an architecture or
              baseline decision, BEFORE implementation.
2. STOP       Stop implementation of the affected change.
3. DESCRIBE   State the decision, the owning authority, the alternatives and the
              consequences.
4. ADR        Write the ADR — next sequential number, MADR structure, status
              Proposed.
5. ACCEPT     A human reviews and explicitly accepts it. This is a separate
              event, performed by a person.
6. IMPLEMENT  Only then implement the architecture/baseline change.
7. VALIDATE   Run the applicable tests and gates.
```

The ADR precedes the implementation. It is not retrospective, it is not written alongside the code,
and it is not written and then treated as accepted.

**Writing an ADR is not approval of it.** Claude writes the record; a human accepts the decision.
Those are two events and the second one is not Claude's.

Claude must never treat any of the following as acceptance of a new architecture or baseline
decision:

- the user's original feature request, however specific;
- an existing ticket, issue, task id or backlog entry;
- a plan — including a plan the user approved — that did not enumerate this decision;
- silence, or an unanswered question;
- a satisfied hook, including H5 (§70.9);
- an architecture document mentioning the change as possible, future, or under consideration;
- a previous ADR that decided something adjacent, or that anticipated this one;
- an existing implementation that already behaves the proposed way;
- the permission mode in force, or the fact that the session is running unattended.

Explicit human acceptance, in this session, about this decision, is required before the decision is
implemented. This is the same non-inference rule as `.claude/rules/50-database.md` §50.2 and
`.claude/rules/30-langgraph.md` §30.5, and it applies here unchanged.

If acceptance does not arrive: the ADR stays `Proposed`, the implementation does not start, and
Claude completes whatever part of the requested work does **not** depend on the decision, saying
plainly what was left undone and why.

## 70.4 Classification

Classify every proposed ADR as one or more of:

| Class | Applies when |
|---|---|
| **Architecture** | §70.2 A — component, zone, trust boundary, topology, store, A1/A2/A3 ownership |
| **Identity / Authority** | §70.2 A(3)(4) — tenancy, principal, authority, approval or verdict semantics |
| **Engineering Baseline** | §70.2 B — an engineering rule is what changes |
| **LangGraph Architecture** | §70.2 C — a `.claude/rules/30-langgraph.md` §30.4 trigger |
| **Database Authorization Boundary** | §70.2 D — A1 §12.2 immutability, DB permissions, checkpoint ownership |
| **Cross-domain Architecture** | more than one of the above, or a genuine A1/A2/A3 contradiction |

More than one class may apply; say so. Do **not** invent further classes — a new class would be a new
authority, and authority is set by the Phase 2 model, not by an ADR.

## 70.5 Required structure

New ADRs use **MADR** structure, in `docs/adr/`, four-digit sequential numbering, with a status field.

Minimum, in this order:

```markdown
# ADR-0010: <decision title>

- Status: Proposed
- Date: <YYYY-MM-DD>

## Context

## Decision

## Consequences
```

The repository's existing records use the equivalent MADR dialect — `# 0009. <title>`,
`- **Status:** Accepted`, `## Context and Problem Statement`, `## Decision Outcome`,
`## Consequences`. Either dialect is acceptable and both satisfy H5; matching the neighbouring
records is preferred, because an index that reads consistently is easier to trust. What is not
optional is: a heading carrying the ADR's own number, a status field, and the three sections.

Optional sections, used **when they carry something** and omitted when they do not — an ADR padded
with empty headings is harder to read, not more governed:

- Decision Drivers
- Considered Options / Alternatives Considered / Rejected Alternatives
- Security / Authority Implications
- Operational Implications
- Migration / Rollout
- Unresolved
- More Information

Whatever else it contains, every ADR **names the authority it affects**: the document and section
(A1/A2/A3 §x.y), or the `.claude/rules/` file and rule, or the §30.4 / §50.5 item.

### Status

A status field is mandatory. The vocabulary is small and human-readable:

| Status | Meaning |
|---|---|
| `Proposed` | Written, not yet accepted. **Nothing may be implemented on it.** |
| `Accepted` | A human accepted the decision. Implementation may proceed. |
| `Superseded by NNNN` | A later record replaces it. |
| `Deprecated` | No longer applies; not replaced. |

Do not invent a wider lifecycle, and do not add review states, owners-in-status, or dates-in-status
beyond the `Date:` field.

**Claude writes `Proposed`.** Claude does not write `Accepted` on an ADR it authored, does not change
a status from `Proposed` to `Accepted`, and does not treat an ADR as accepted because the session
continued. Moving a status to `Accepted` is a human act, or the recording of an acceptance a human
has explicitly given in this session.

## 70.6 Numbering and the existing history

- Existing sequence: `0001` … `0012`. The next new record is **`0013`**, then `0014`, `0015`, …
  `0010` and `0011` were written in Phases 12 and 14 and are `Accepted`; `0012` was written in
  Phase 16 and is `Proposed` — an unaccepted record still consumes its number.
- Filename: `docs/adr/NNNN-<short-kebab-case-title>.md` — four digits, a hyphen, then lower-case
  words separated by single hyphens.
- A number is **never reused**, including the number of a superseded or deprecated record.
- Do not renumber, merge, replace, reword or "correct" `0001`…`0009`. Do not change their status
  retroactively to match newer governance. Their historical integrity is the point of keeping them.
- Amending an existing record is a human-directed act. If a new decision changes an old one, the
  normal instrument is a **new** record that says what it supersedes or amends — that is how `0007`,
  `0008` and `0009` relate to their predecessors.
- Update `docs/adr/README.md` in the same change as a new record. A record that is not indexed is a
  record nobody finds. Updating the index is not editing history.
- **If the next number is ambiguous** — a gap in the sequence, two records claiming one number, an
  uncommitted record elsewhere — stop and report it. Do not guess, and do not "reserve" a number by
  writing a placeholder.

## 70.7 Interaction with the DB and LangGraph gates

The ADR gate does not replace those procedures and does not reorder them.

**Database.** When a DB change turns out to be an architecture change (`.claude/rules/50-database.md`
§50.5, Step H of the `db-change` skill):

```text
DB gate: detect -> stop -> describe DB impact
      -> identify the architecture change
      -> ADR gate: describe, write, HUMAN ACCEPTANCE
      -> DB implementation and validation (database first, always)
      -> application continuation
```

**LangGraph.** When `.claude/rules/30-langgraph.md` §30.4 classifies a change as
architecture-altering:

```text
LangGraph gate: detect -> stop -> describe -> classify
      -> ADR gate: write, HUMAN ACCEPTANCE
      -> implement -> test -> verify
```

**Both at once** — a change that alters graph behavior *and* checkpoint persistence:

```text
DB ordering wins (rule 50.6 / rule 30.8).
DB detect -> describe -> ADR where the DB change is architectural -> acceptance
          -> DB implemented and validated
          -> then the LangGraph implementation, tested at the graph level
```

There is exactly one ADR gate and exactly one ordering for each pairing. If a future rule appears to
state a different ordering, that is a conflict to report, not a choice to make.

## 70.8 Testing obligations

- An ADR changes nothing mechanically; the change it authorizes still runs every applicable gate. An
  accepted ADR is never a reason to skip a test.
- **Never weaken a test because an ADR authorized the change.** If a test encodes the rule the ADR
  deliberately changes, the test is updated as part of the accepted implementation and the ADR says
  so in its Consequences. If the ADR did not say so, the test is not touched — return to §70.3
  step 3.
- No deletion, no `skip`/`xfail`, no loosened assertion, no narrowed fixture, in either case.
- Validate the ADR governance artifacts themselves with `python3 .claude/hooks/test_guards.py`.

## 70.9 What the H5 hook does and does not do

`.claude/hooks/adr_structure_guard.py` fires deterministically on writes to `docs/adr/*.md`. It
checks **structure only**: the four-digit filename and its kebab-case title, that the number is not a
duplicate, that it continues the sequence, that a status field exists, and that `Context`, `Decision`
and `Consequences` are present. It also notices a write to an existing record and says so, because
history is preserved by default.

It does **not** decide whether an ADR is conceptually required, whether the decision is correct,
whether it is sufficiently reasoned, whether a consequence is missing, or whether a person should
accept it. It never marks an ADR accepted, never modifies an ADR, an architecture document, or any
application code.

**A structurally valid ADR can still be the wrong decision, an unaccepted one, or an under-reasoned
one.** Those are human and governance concerns. Satisfying H5 is not acceptance, and silence from H5
is not agreement.
