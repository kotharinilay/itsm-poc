---
name: "functional-update"
description: "Update docs/functional/implemented.md after verified implementation behavior changes: detect what changed, identify the affected functional areas, confirm behavior from implementation and test evidence, update the record, classify behavior as implemented / unbound / inert / test-only / unavailable, record any architecture conformance finding without fixing it, and validate that no unsupported functional claim remains."
argument-hint: "The implemented change whose functional knowledge needs recording"
user-invocable: true
disable-model-invocation: false
---

# Functional knowledge update procedure

Governing rule: `.claude/rules/90-functional-knowledge.md`. The rule says **what must be true**; this
skill is **how to do it, in order**.

Invoke this skill **after** a change has been implemented and verified — never before. If the change
is still being designed or is mid-implementation, this is the wrong skill.

**This skill does not modify application code, schema, migrations, graph behavior, contracts,
architecture documents or ADRs. It does not create an architecture decision. It does not invent
future functionality.** Its only outputs are edits to `docs/functional/implemented.md`.

**It is downstream of every other gate.** If the change needed the DB, LangGraph or ADR procedure,
that procedure ran first and in full. Running this skill is not evidence that it did.

---

## Step 1 — DETECT

Establish that **verified** implementation behavior changed.

Ask:

- What behavior is different now from before the change?
- Was it verified — did the relevant suites run, and pass?
- Is the change in an implementation artifact, or only in prose/governance?

Stop here if:

- the change touched only documentation, rules, skills or hooks — there is no functional knowledge to
  record;
- the behavior has not been verified yet — return when it has (rule §90.3);
- nothing about *observable behavior* changed, only internal structure.

Record the **revision being described**. It is the revision actually audited.

## Step 2 — IDENTIFY

Name the functional areas of `docs/functional/implemented.md` the change touches. The document's own
section structure is the checklist:

- deployables, and their build/test state
- entry points and API surfaces, per service
- authentication and authorization as enforced
- multi-tenancy and isolation
- validation and API contracts
- LangGraph workflow — topology, state, reducers, interrupts, resume, checkpointing, nodes,
  the run host and the streaming path
- deterministic governance — treatment policy, the gate, the catalogue
- persistence and data lifecycle — schema, migrations, views, principals, repositories
- background processing — outbox, consumers, sweepers, worker processes
- execution leg and idempotency
- external integrations and model egress
- realtime behavior
- web implementation
- desktop implementation
- error and failure behavior
- testing evidence
- the summary table of inert/unbound/unimplemented areas
- the implementation findings and conformance findings sections

List every affected area before editing any of them. A change that alters a surface usually also
alters the summary table and the testing section.

## Step 3 — VERIFY

Confirm the behavior from **current** implementation and test evidence. Do not carry a statement
forward because it is already in the document.

For each statement you are about to write, answer all four:

```text
Where is this behavior implemented?      (file, and ideally line)
How is it invoked?                       (route, node, worker, component, CLI)
What test proves it?                     (a test file that exists — check it)
Is it reachable in normal composition?   (trace the container / provider / registration)
```

The fourth question is the one most often skipped and most often decisive. Trace the composition
root, not the class. An implementation whose dependency is bound `None` does not run.

Use only repository-tracked files (`git ls-files`). Exclude `bin/`, `obj/`, `.venv/`,
`__pycache__/`, `node_modules/`, Angular cache and packaging output.

Prefer running the suite to citing it. Record the command and the result.

**A docstring is not evidence.** If a comment claims a behavior the code does not perform, the code
wins and the gap is a finding (Step 6).

## Step 4 — UPDATE

Edit `docs/functional/implemented.md`.

- **Correct, do not append.** If current implementation disproves an existing statement, replace it.
  If current implementation cannot prove a statement, remove it or reclassify it against evidence the
  code does provide.
- **Do not preserve a stale claim for history** (rule §90.8). Git holds it.
- **Update the revision metadata** to the revision actually audited (rule §90.9).
- **Cite implementation references** — `ragcore/src/ragcore/graph/builder.py`,
  `dotnet/src/Synthia.Api/Endpoints/CustomerViewEndpoints.cs`,
  `ragcore/tests/unit/test_graph_state.py` — rather than writing "the service supports…". Not every
  sentence needs a citation; the document needs enough that another engineer can verify it.
- **Update the testing section** from suites that actually exist and were actually run, with their
  commands and results. Never copy a test requirement from a rule or an architecture document.
- **Where a previous snapshot was wrong**, say so in the corrections section. That is a statement
  about the document, not a functional claim, and it helps a reader who remembers the old text.

## Step 5 — CLASSIFY

Label the behavior. Do not flatten everything into "implemented".

| Label | Use when |
|---|---|
| **Implemented** | Reachable and working in the normal production composition. |
| **Implemented but unbound** | The code exists; composition binds no dependency for it. |
| **Wired but inert** | The surface exists and deliberately does nothing — 501, `{}`, `NotImplementedError`, no-op. |
| **Test-only** | Runs only because a test supplied the composition or fixture. |
| **Not implemented** | Evidence shows the capability is deliberately unavailable. |
| **Unverified** | Code exists; no executable evidence of its behavior exists in the repository. |

Rules that hold every time:

- **Never collapse production-reachable and test-only into "implemented".**
- A route that returns 501 is an **implemented contract with unimplemented behavior**, not a working
  feature. Say both halves.
- A declared request model, a rendered component, or a registered class is **not** a capability.
- Use **Unverified** sparingly, and only after investigating. It is not a shortcut past Step 3.

## Step 6 — CONFORMANCE CHECK

If the implementation differs from an authoritative architecture document, **record it and move on**.

Write:

- what the implementation actually does;
- the observable evidence;
- the affected area;
- that it is a deferred conformance finding.

Neutral wording:

> The current implementation does X. The architecture source of truth specifies Y. This is a deferred
> conformance finding.

Do **not**: modify the architecture document, modify application code, change the functional
description to match the architecture, or decide which side is correct.

If resolving the finding would change architecture, that is `.claude/rules/70-adr.md` §70.2 A — a
separate, human-accepted decision, not part of this skill.

Engineering-baseline deviations get at most a one-line observable fact where it is needed to explain
behavior. `implemented.md` is not an engineering-conformance report.

## Step 7 — VALIDATE

Re-read the changed sections and check for each of the following. Fix what you find.

- [ ] Future-tense capability claims — "will", "should", "planned", "future", "to be implemented" —
      except where explicitly describing what the implementation does **not** do.
- [ ] Roadmap, requirements or acceptance-criteria language.
- [ ] Unsupported "supports…" statements.
- [ ] Architecture intent presented as implementation.
- [ ] References to endpoints, components, modules or test files that do not exist — check them.
- [ ] Claims contradicted by an explicit 501, `NotImplementedError`, `None` binding or raised refusal.
- [ ] A stale revision reference in the metadata.
- [ ] Duplicate or conflicting descriptions of the same capability in two sections.
- [ ] Production-reachable behavior described in the same breath as test-only behavior.
- [ ] Prose evidence — any statement whose only support is a document rather than code.

Then confirm the repository is unchanged apart from the documentation:

- [ ] No application source, test, migration, contract or configuration file was modified.
- [ ] No architecture document or ADR was modified.
- [ ] No test was deleted, skipped, `xfail`ed, loosened or narrowed. This is absolute.
- [ ] The existing governance suite still passes: `python .claude/hooks/test_guards.py`.

---

## What this skill must never do

- Change application behavior, schema, graph behavior, contracts or architecture.
- Create, accept or imply an architecture decision.
- Weaken a test for any reason.
- Write a functional claim the implementation does not support, however reasonable it sounds.
- Treat a governance file, an architecture document, an ADR or a specification as evidence that a
  capability exists.
- Substitute for the DB, LangGraph or ADR gate, or be offered as evidence that one was satisfied.
