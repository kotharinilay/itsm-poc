---
name: "adr-author"
description: "Run the ordered procedure for a change that requires an architecture, identity/authority, engineering-baseline, LangGraph-architecture or DB-authorization-boundary decision: detect why an ADR is required, stop implementation, gather context from the authoritative sources only, classify the trigger, draft the next sequential MADR record with status Proposed, self-check it, stop for explicit human acceptance, and only then implement and validate."
argument-hint: "The change being requested"
user-invocable: true
disable-model-invocation: false
---

# ADR authoring procedure

Governing rule: `.claude/rules/70-adr.md`. The rule says **what must be true** — which changes
require an ADR, what an ADR is and is not, the numbering, the structure, the non-inference of
acceptance. This skill is **how to get there, in order**. The order is the governance: an ADR written
after the code is not an ADR, it is a justification.

Invoke this skill the moment an architecture or baseline decision is suspected, before implementing
the part of the work that depends on it.

Related procedures, not restated here: `.claude/skills/db-change/SKILL.md` (Step H escalates to this
skill), `.claude/skills/langgraph-change/SKILL.md` (Step 6 escalates to this skill).

---

## Step 1 — DETECT

Answer one question: **why would this work require a decision that a normative source owns?**

Walk the four trigger families in `.claude/rules/70-adr.md` §70.2 and name the one that fires:

- **A — Architecture.** Does the work need a new component or zone, a changed trust or tenant
  boundary, changed identity/authority semantics, a changed topology, a new persistent store, a
  changed ownership boundary between A1/A2/A3, or the resolution of a genuine contradiction between
  two architecture documents?
- **B — Engineering baseline.** Can the implementation be done without relaxing an analyzer, adding a
  Ruff ignore or a `# noqa`, suppressing a warning, weakening nullability or warning treatment, or
  contradicting a migrated baseline rule? If it cannot, B fires.
- **C — LangGraph architecture.** Does the change hit any item in `.claude/rules/30-langgraph.md`
  §30.4, or weaken any protection in §30.3?
- **D — Database authorization boundary.** Does the change hit `.claude/rules/50-database.md` §50.5 —
  identity-bearing immutability, DB permission boundaries, an invariant moving out of the database,
  or the ownership of checkpoint persistence?

Record, concretely and by name:

| Field | What to state |
|---|---|
| Trigger | which of A / B / C / D, and the numbered item within it |
| Architecture domain | identity/authority, platform topology, graph architecture, data — or none |
| Affected authoritative document | A1 / A2 / A3 by filename, or "none — baseline only" |
| Affected section | §x.y in that document |
| Affected engineering rule | the `.claude/rules/` file and the rule, if B applies |
| Affected DB / LangGraph governance | the §50.5 or §30.4 item, if D or C applies |

If **no** trigger fires: say so in one line and continue with ordinary implementation. Do not run the
rest of this skill, and do not write a defensive ADR — an ADR for a change that needed none dilutes
the ones that did.

If a trigger fires, or it is genuinely unclear whether one does: go to Step 2. Uncertainty resolves
toward yes, and the cost of resolving it is one paragraph and a question, not an ADR.

## Step 2 — STOP

- Stop implementing the affected change. Not "the interface first", not "a scaffold", not "behind a
  flag".
- If edits were already made that depend on the undecided change, say plainly that the ordering was
  broken, name the files, and set those edits aside until the ADR is accepted.
- Continue any part of the requested work that does **not** depend on the decision, and say which
  parts those are. Stopping the decision is not stopping the task.
- Do not work around the decision. A shim, a parallel code path, a config flag that quietly
  implements both sides, a "temporary" second store, a comment saying the boundary will be sorted out
  later — each of these is the decision, taken without the record.

## Step 3 — GATHER CONTEXT

Authoritative sources only:

- `docs/architecture/identity-plane-final.md` (A1)
- `docs/architecture/Synthia-OverallArchitecture-final.md` (A2)
- `docs/architecture/RagAgent-Architecture-final.md` (A3)
- `.claude/rules/**`, for an engineering decision

For an architecture decision, establish four things and quote or cite each:

1. **The owning document.** Use the ownership map in `.claude/rules/70-adr.md` and the precedence
   rule in `.claude/rules/00-authority.md` §00.5. If they genuinely contradict, that contradiction
   *is* the decision to record (§00.6).
2. **The applicable section.** §x.y, not "somewhere in A2".
3. **The currently documented decision or boundary.** What the document says today, in its own words.
4. **The requested change.** What would have to become true instead.

For an engineering-baseline decision, establish the same four things against the rule file: which
rule, what it currently requires, what the implementation would require instead, and what else in the
repository currently depends on the rule as written.

Not sources, and not substitutes:

- existing ADRs `0001`…`0009` — read them for structure and history, never to reconstruct what
  architecture currently says;
- `docs/architecture/integrations-service-delta.md`, `docs/architecture/ragcore-langgraph-flow.md`;
- `README.md`, `Synthia-Platform-Specification.md`, `.serena/**`,
  `docs/current-implementation/**`;
- the code. The implementation is evidence of what is, never authority for what should be. If the
  code already behaves the proposed way, that is a deviation to report inside the ADR's Context, not
  a reason the decision is already made.

## Step 4 — CLASSIFY

Classify against `.claude/rules/70-adr.md` §70.4: Architecture, Identity / Authority, Engineering
Baseline, LangGraph Architecture, Database Authorization Boundary, Cross-domain Architecture. More
than one may apply. Do not invent a further class.

Then state the ordering this decision sits inside, so the human can see the whole path:

- DB change that turned out to be architectural → §70.7, database implemented and validated **after**
  acceptance and **before** application work.
- LangGraph §30.4 change → §70.7, ADR accepted before any graph code.
- Both, i.e. checkpoint persistence → the DB ordering wins (rule 50.6 / 30.8).

## Step 5 — DRAFT

Determine the number mechanically:

```bash
ls docs/adr/ | grep -E '^[0-9]{4}-' | sort | tail -3
```

The next number is the highest existing number plus one, four digits, zero-padded. Never reuse a
number, including a superseded one. **If the sequence is ambiguous — a gap, a duplicate, a record
that exists uncommitted — stop and report it rather than guessing.**

Write `docs/adr/NNNN-<short-kebab-case-title>.md` in MADR structure
(`.claude/rules/70-adr.md` §70.5), matching the dialect of the neighbouring records:

```markdown
# NNNN. <decision title>

- **Status:** Proposed
- **Date:** <YYYY-MM-DD>
- **Deciders:** <who must accept this>
- **Related:** <earlier records this touches, if any>

## Context and Problem Statement

What forces the decision. Name the owning authority — document and section, or rule file and rule —
and state what it currently says. State what the requested work needs instead, and why the work
cannot proceed without it.

## Decision Drivers

Only if there is more than one, and only the ones that actually bear on the choice.

## Considered Options

Each real alternative, including "do not change it and change the implementation instead", which is
almost always a real option and is frequently the right one.

## Decision Outcome

The decision, stated so that someone implementing it cannot reasonably do something else. If the
decision is the human's to make and has not been made, this section says which options are on the
table and that it is pending — it does not pick one. See §Step 6.

## Consequences

What becomes true, what becomes false, what gets harder, what is now allowed that was not, and what
must change elsewhere — tests, rules, documents, code. Say the negative consequences plainly; an ADR
with only benefits has not been thought through.

## Security / Authority Implications

Mandatory whenever the class is Identity / Authority, Database Authorization Boundary, or a §30.3
protection is anywhere near the change. State explicitly whether any authority boundary moves.

## Unresolved

What this record does not close, and where it will be met.
```

Status is **`Proposed`**. Always, without exception, on a record Claude writes.

Update `docs/adr/README.md` in the same change — add the row to the index and, if the record leaves
something open, the open-items table. Updating the index is not editing history.

Write **only** the ADR and the index. No architecture document, no rule file, no application code, no
migration, no test — none of that is authorized yet.

## Step 6 — SELF-CHECK

Before presenting the draft, verify each of these and say so:

**Structural** (the same things H5 checks, checked before the hook has to):

- [ ] number is unique against everything in `docs/adr/`;
- [ ] number continues the sequence — highest plus one;
- [ ] filename is `NNNN-<short-kebab-case-title>.md`, lower case, single hyphens;
- [ ] a status field exists, and it reads `Proposed`;
- [ ] `Context`, `Decision` and `Consequences` sections are present and non-empty;
- [ ] `docs/adr/README.md` has the new row.

Run it rather than eyeball it:

```bash
python3 .claude/hooks/adr_structure_guard.py --check docs/adr/NNNN-<title>.md
```

**Substantive** (H5 cannot check any of these, which is why they are here):

- [ ] the context is intelligible to someone who was not in this session;
- [ ] the decision is explicit, not a summary of the discussion;
- [ ] the consequences include the costs, not only the benefits;
- [ ] the affected authority is named — document and section, or rule file and rule;
- [ ] no architecture document, rule file or test has been altered anywhere in this change;
- [ ] no application code has been written on the strength of the undecided change;
- [ ] where the decision belongs to a human, the record says so instead of choosing.

## Step 7 — STOP FOR HUMAN ACCEPTANCE

Present the ADR and ask, explicitly, whether it is accepted.

Then **wait**. While waiting:

- do not implement the decision, nor any adjacent code that assumes it;
- do not change the status;
- do not treat continued conversation, a next instruction on another topic, or the absence of an
  objection as acceptance.

None of the following is acceptance — `.claude/rules/70-adr.md` §70.3 lists them and the list is
binding: the original feature request, a ticket, an approved plan that did not enumerate this
decision, silence, a satisfied hook, an architecture document mentioning the change as future or
possible, an earlier ADR, an implementation that already behaves this way, or the permission mode in
force.

If acceptance is refused, or the human reshapes the decision: return to Step 3, and leave the
superseded draft's number alone if it was already committed — a new record supersedes; numbers are
not recycled.

If acceptance does not come at all: the record stays `Proposed`, the dependent work stays undone, and
the final report says exactly which part of the request is blocked on which record.

## Step 8 — IMPLEMENT

Only after explicit acceptance, and only what the ADR decided:

1. Record the acceptance the human gave — status `Accepted`, with the date — because the human said
   it, never because the code is ready.
2. Follow the ordering for the class (§70.7 and Step 4): the database first where a DB change is
   involved; the graph only after an accepted ADR where §30.4 applies; both, DB first.
3. Implement the decision as written. If implementation reveals that the ADR decided the wrong thing,
   stop and return to Step 3 — do not implement the better idea and reconcile the record afterwards.
4. Leave the architecture documents alone. If an accepted decision means A1, A2 or A3 must change,
   say so and let the human make that edit.

## Step 9 — VALIDATE

- Run the gates the change touches: `uv run pytest -q -m integration` and
  `uv run pytest -q -m "not integration"` from `ragcore/` for a DB or graph change; the graph,
  checkpoint, governance, idempotency, authorization, isolation and architecture suites for a
  §30.4 change; the .NET and web suites where those are what changed.
- Run `python3 .claude/hooks/test_guards.py` whenever a governance artifact changed.
- **Never weaken a test because an ADR authorized the change.** If a test encodes the very rule the
  ADR changes, the ADR's Consequences said so and the test is updated as part of the accepted
  implementation. If the ADR did not say so, the test is not touched — return to Step 3.

## What this skill must never do

- **Choose among competing architectural alternatives when the choice is a human's.** Present the
  options, the consequences and the tradeoffs, name the architecture owner, and stop. Ease of
  implementation is not a tiebreaker, and neither is what the code already does.
- Accept its own ADR, write `Accepted` on a record it authored, or advance a status without the human
  saying so.
- Treat the drafting of the record as the passing of the gate.
- Implement the decision before acceptance, or implement more than the decision after it.
- Modify an architecture document, or an existing record `0001`…`0009`.
- Renumber, reuse or guess at a number.
- Weaken, skip or delete a test.
- Fix an architecture-vs-implementation deviation it happens to notice. Report it instead.
