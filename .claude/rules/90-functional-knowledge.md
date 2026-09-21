# 90 — Functional knowledge and the implemented-truth record

Procedure: `.claude/skills/functional-update/SKILL.md`. There is **no deterministic hook** for this
rule, and that is deliberate — no mechanical check can tell a supported functional claim from an
unsupported one.

Authority for this file:

- The **implementation itself** is the sole authority for what `docs/functional/implemented.md` says.
  Application source, automated tests, database schema and migrations, ORM models, implemented API
  routes, generated contracts, executable configuration, the LangGraph implementation, background
  workers, message publishers and consumers, the frontend and desktop implementation, dependency
  manifests, build scripts and CI workflows.
- `docs/architecture/identity-plane-final.md` (A1), `docs/architecture/Synthia-OverallArchitecture-final.md`
  (A2) and `docs/architecture/RagAgent-Architecture-final.md` (A3) remain authoritative **for
  architecture**. They are **not** evidence that a capability is implemented, and this rule never
  overrides them.

No other repository document is authority for this file. Existing implementation is evidence of what
**is**; architecture is authority for what **should be**. This rule governs only the first.

---

## 90.1 Purpose

`docs/functional/implemented.md` is the **canonical record of implemented functional behavior** — the
single place that answers "what does this repository demonstrably do today?"

It exists because that question has a different answer from "what is this platform meant to do", and
the two were previously answerable only by reading the code. A stale or aspirational functional
record is worse than none: it invites a change to be built on a capability that does not exist.

The document is **downstream of verified implementation**. It records; it never authorizes.

## 90.2 Evidence policy

Every functional statement in `implemented.md` must be supported by an implementation artifact:

- application source code
- automated tests, and preferably tests that were actually run
- database schema, migrations, ORM models
- implemented API route handlers and the generated OpenAPI contracts
- executable configuration, dependency manifests and lock files
- the LangGraph implementation — builder, state, nodes, checkpointer, host
- background workers, publishers, consumers
- frontend and desktop implementation
- build scripts, CI workflows, validation scripts

The following are **never** evidence that a capability is implemented:

- A1, A2 or A3, or any other architecture document
- `docs/adr/**`, `docs/migration/**`, `README.md`, `Synthia-Platform-Specification.md`
- `.serena/**`, `docs/current-implementation/**` (and the `.specify/**` / `specs/**` trees deleted
  in Phase 16, which may not be cited from git history either)
- `docs/architecture/integrations-service-delta.md`, `docs/architecture/ragcore-langgraph-flow.md`
- `.claude/rules/**`, `.claude/skills/**`, `.claude/hooks/**` — governance machinery describes what
  Claude must do, never what the product does
- a code comment or docstring that *describes* a behavior the surrounding code does not perform
- a previous version of `implemented.md`

**Build residue is not source.** `bin/`, `obj/`, `.venv/`, `__pycache__/`, `node_modules/`, Angular
cache and packaging output are excluded. Use `git ls-files` or an equivalent repository-aware method
to establish what exists.

**A docstring naming a test is not that test.** If a claim rests on a test, the test file exists and
its name is checked.

## 90.3 Update timing

```text
Implement  →  Verify  →  Update implemented.md
```

The document is updated **after** the behavior is verified, never before and never alongside. A
functional record written from an intention rather than from a passing run is the exact failure this
rule exists to prevent.

Concretely: the tests run, the build is green, the behavior is observed — and only then does the
functional statement get written.

## 90.4 Prohibited content

`implemented.md` must not contain:

- future state, roadmap, or planned features
- requirements, acceptance criteria, or user stories
- architecture intent presented as implementation
- speculative behavior, or behavior inferred from a design document
- a claim that "the service supports X" where nothing in the tree demonstrates X
- a stale revision reference

The words **"will support"**, **"should support"**, **"planned"**, **"future"** and **"to be
implemented"** do not appear, with one exception: text that is explicitly describing that the current
implementation does **not** provide a capability.

## 90.5 Required classification

Functional behavior is classified, not flattened into "implemented". At minimum the document
distinguishes:

| Label | Meaning |
|---|---|
| **Implemented** | Directly implemented and reachable in the normal production composition. |
| **Implemented but unbound** | The implementation exists; normal composition binds no dependency for it. |
| **Wired but inert** | The surface exists and deliberately performs no operation — a 501, an empty return, a `NotImplementedError`, a no-op. |
| **Test-only** | Demonstrated only through test fixtures or test composition. |
| **Not implemented** | Evidence exists that the capability is deliberately unavailable. |
| **Unverified** | Code exists and the repository holds no executable evidence of its behavior. |

**Production-reachable behavior is never collapsed with test-only behavior.** A capability that runs
only because a test supplied a container is test-only, however complete its implementation.

**`Unverified` is used sparingly** and never as a substitute for reading the implementation. It is
correct only where the investigation was done and the evidence genuinely does not exist.

## 90.6 Change discipline

When implementation changes behavior:

```text
1. IDENTIFY   Which functional knowledge the change affects.
2. IMPLEMENT  Make the change, under whatever gate governs it.
3. VERIFY     Run the applicable suites; observe the behavior.
4. UPDATE     Update docs/functional/implemented.md.
5. VALIDATE   Check the document against implementation evidence.
```

Steps 4 and 5 are part of the change, not a follow-up. A behavior change that leaves `implemented.md`
describing the old behavior is an incomplete change.

**A statement is corrected, not appended to.** If the implementation disproves an existing statement,
the statement is replaced. If the implementation cannot prove a statement, it is removed or
reclassified against evidence the code does provide.

## 90.7 Conformance findings are reported, never reconciled

Where the implementation differs from an authoritative architecture document, `implemented.md`:

- records what the implementation actually does;
- records the observable evidence;
- names the affected area;
- states that it is a conformance finding.

Neutral wording, of this shape:

> The current implementation does X. The architecture source of truth specifies Y. This is a deferred
> conformance finding.

It does **not**: modify the architecture document, modify application code, change the functional
description to match the architecture, or decide which side is correct. Resolving a conformance
finding is a separate, human-directed act, and where it changes architecture it is an ADR under
`.claude/rules/70-adr.md` §70.2 A.

The same holds for engineering-baseline deviations: record the observable implementation fact where
it is needed to explain actual behavior, and nothing more. `implemented.md` is not an
engineering-conformance report.

## 90.8 Historical snapshot rule

**The document does not preserve a stale claim for the sake of history.** Git already holds every
previous version, with its commit, its author and its date. Keeping a disproved statement in the
current record trades the document's only useful property — that it is true now — for a history that
is already recorded elsewhere.

A statement is kept only because current evidence supports it. Its presence in a previous version is
not a reason.

Recording *corrections* is different and is encouraged: a short section naming what a previous
snapshot got wrong helps a reader who remembers the old text, and it is a statement about the
document, not a functional claim.

## 90.9 Metadata

The document states the **revision it describes**. That revision is the one actually audited — not a
branch name, not a future state, not a commit carried over from a previous pass. When the document is
updated, the revision is updated with it.

## 90.10 Relationship to the other gates

Functional documentation is **downstream of every other gate and overrides none of them**:

```text
DB / LangGraph / ADR governance
        ↓
implementation
        ↓
tests / verification
        ↓
functional-update
```

- A database change follows `.claude/rules/50-database.md` first, in full.
- A LangGraph change follows `.claude/rules/30-langgraph.md` first, in full.
- A change requiring an architecture or baseline decision follows `.claude/rules/70-adr.md` first, in
  full, including human acceptance.

Only once the governed change is implemented and verified does this rule apply. **Updating
`implemented.md` is never a substitute for a gate, and never evidence that one was satisfied.** The
DB, LangGraph and ADR procedures are not restated here and must not be duplicated, extended or
narrowed by this rule.

## 90.11 What this rule does not do

- It does not authorize a change to application behavior, schema, graph, contracts or architecture.
- It does not create or accept an architecture decision.
- It does not permit a test to be weakened, deleted, skipped, `xfail`ed, loosened or narrowed —
  under any circumstances, including to make a functional claim true.
- It does not make `implemented.md` authoritative for anything. The document describes; the
  implementation is what it describes, and architecture remains authoritative for what should be.
