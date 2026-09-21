# 0012. Migrate Principle IX clauses 2b and 3: no fabricated success, and reference fixtures are never product

- **Status:** Proposed
- **Date:** 2026-09-21
- **Deciders:** Repository owner
- **Supersedes:** nothing
- **Amends:** `.claude/rules/10-principles.md`, which today states no requirement about what an
  implementation may *return* when it cannot do the thing asked of it, and no requirement about
  reference fixtures at all
- **Related:** [0010](./0010-frontend-engineering-baseline.md) and
  [0011](./0011-required-test-categories-baseline.md) — the same class of act, migrating
  requirement text that the retired Spec Kit constitution held alone, under an ADR rather than by
  editorial transcription

## Context and Problem Statement

Phase 15 (`docs/migration/phase-15-final-spec-kit-reconciliation.md` §6) decomposed the retired
constitution's Principle IX — *"Scaffold Honestly; Do Not Invent Product"* — clause by clause
against the migrated baseline, and found that two of its four clauses are **unique normative
requirements with no home in `.claude/rules/`**. That finding was recorded as blocker **B15-1**,
and it is the only thing standing between the repository and the retirement of `.specify/` and
`specs/`.

### What is already covered, and is not at issue here

| Clause | Classification | Where it already lives |
|---|---|---|
| **1.** the objective is a buildable reference scaffold; UC-01…UC-12 are placeholders and must not be invented | **historical** | phase-specific to the original scaffold; nothing current depends on it |
| **2a.** an unsupported capability falls back to manual resolution or escalation, explicitly and visibly | **covered** | the outcome vocabulary `{answered_sop, resolved_action, escalated, denied}` with `escalation_reason` is **A3 §6.2**; the explicit-failure half is `10-principles.md` **P-11** and **P-30** |

Neither is migrated by this record.

### The two clauses that are not covered

**Clause 2b**, verbatim from `.specify/memory/constitution.md` §IX:

> A fallback MUST be explicit and visible; silently degrading, stubbing a success, or returning a
> plausible-looking fabricated result is prohibited.

**Clause 3**, verbatim from the same section:

> **Reference fixtures are permitted, and are never product.** Inert reference operations may exist
> so that governance, consent and approval paths are demonstrable before any use case is defined.
> Each MUST be labelled a scaffold fixture, produce no real external effect, be excluded from
> production configuration, and MUST NEVER be counted as or allowed to become one of the twelve use
> cases.

Clause 3 is restated in `specs/001-platform-scaffold/spec.md` as `FR-SCOPE-004`, `FR-SCOPE-005`,
`FR-SCOPE-006` and `FR-SCOPE-007`. **Both of its written homes are inside the deletion set.**

### Why the existing baseline does not already say this

This was checked rule by rule, not assumed:

- **P-8** (no speculative capability) forbids *building* a capability a requirement does not need.
  It says nothing about *fabricating a result* from one that was never built.
- **P-30** (no swallowed errors) governs a **caught error**. In the failure clause 2b describes, no
  error is raised at all — that is precisely what makes it silent.
- **P-11** (fail fast) requires invalid input to be rejected at the boundary. A stubbed success is
  not invalid input; it is valid input answered dishonestly.
- **P-14** (least astonishment) asks for unsurprising behaviour without prohibiting a synthesized
  success.
- **P-15** (command/query separation) and **P-20** (illegal states unrepresentable) are structural;
  neither constrains the truthfulness of a returned value.
- **`90-functional-knowledge.md`** §90.4 and §90.5 govern what the **record** may claim — including
  the `Wired but inert` and `Test-only` classifications — and §90.11 states explicitly that it
  authorizes nothing about implementation behaviour.
- **No rule in `.claude/rules/` mentions fixtures** in any sense other than a test fixture.

### The requirement is mechanically enforced today

`ragcore/tests/governance/test_fixtures_excluded.py` asserts every property of clause 3:

| Property | Asserted by |
|---|---|
| labelled, two independent ways that must agree | `TestEveryFixtureIsLabelled` |
| inert — no external system, no verification tool, no claimed confirmation | `TestEveryFixtureIsInert` |
| excluded from production configuration, by a **raising** loader rather than a runbook step | `TestExcludedFromProductionConfiguration` |
| never a use case, and declared in exactly one module | `TestAFixtureIsNeverAUseCase` |
| the exclusion never becomes an environment branch on a treatment, role or entitlement | `TestTheExclusionDoesNotBecomeAnEnvironmentBranch` |

`ragcore/src/ragcore/governance/fixtures.py` implements them. So after the Spec Kit trees are
deleted, **the repository would mechanically enforce a requirement that no surviving document
states** — the exact inversion of the authority model, in which a test is evidence of what is and a
rule is authority for what should be (`.claude/rules/00-authority.md` §00.4).

**Migration input is not authority.** The constitution and `specs/001-platform-scaffold/spec.md` are
the *source text* for this migration in exactly the sense ADR-0010 and ADR-0011 used the term. Their
non-authoritative status under `00-authority.md` §00.4 is unchanged by having been read, and this
record does not restore it.

## Decision Drivers

- Deleting `.specify/` and `specs/` with these clauses unmigrated destroys the only written
  statement of a requirement the repository still enforces. Phase 15 refused to certify retirement
  readiness while that is true.
- `.claude/rules/70-adr.md` §70.2 B(6) makes a change to a mandatory engineering convention a
  baseline change requiring an ADR. Adding two repository-wide requirements is a baseline change by
  any reading, and §70.2 B is explicit that editorial transcription is not the instrument.
- The alternative — letting the clauses lapse — is a decision, not a default, and it would leave
  `test_fixtures_excluded.py` enforcing nothing anybody stated.
- A requirement about *what an implementation may return* belongs with the language-independent
  engineering principles, not with the record of what the implementation does.

## Considered Options

1. **Migrate both clauses into `.claude/rules/10-principles.md`.** — chosen.
2. **Migrate clause 3 into `.claude/rules/21-python.md`.** Rejected: the only fixtures that exist
   today are Python, but the requirement is about the governance catalogue, not about Python. A
   demo fixture added to a .NET or frontend surface would escape a Python-scoped rule, and
   `CLAUDE.md` §4 forbids carrying a rule to another stack by analogy — which is exactly what would
   then be needed.
3. **Create a new rule file, e.g. `11-scaffold-honesty.md`.** Rejected: two requirements do not
   warrant a tenth repository-wide file, and `10-principles.md` already owns the
   language-independent engineering obligations both clauses belong to.
4. **Migrate clause 2b into `90-functional-knowledge.md`.** Rejected: that file governs the
   *functional record* and says so in §90.11. A rule about what code returns does not belong in the
   file that documents what code does.
5. **Let the clauses lapse with the scaffold phase.** Rejected by the repository owner. Recorded
   here because Phase 15 §6.1 required the choice to be explicit rather than defaulted.

## Decision

**The repository adopts Principle IX clauses 2b and 3 into the permanent engineering baseline**, as
two new repository-wide rules appended to `.claude/rules/10-principles.md` as **§10.7 —
Implementation honesty and reference fixtures**.

They are appended after the existing §10.6, not inserted, so that every existing section number in
that file stays stable and no cross-reference from another rule breaks. This is the same mechanism
ADR-0011 used for `40-testing.md` §40.8–§40.10.

They carry a new rule-id space, **`H-*`**, because they come from neither `principles.yaml` (the
`P-*` space) nor the identically-stated .NET/Python convention blocks (the `C-*` space). Their
`Source:` line names ADR-0012 and this migration, **never `.specify/` or `specs/`**.

### H-1 — No fabricated, stubbed or silently degraded success

An operation that did not do the thing asked of it never reports that it did. Where a capability is
unsupported, unavailable or not implemented, the outcome is **explicit and visible** at the
boundary that returns it: an escalation, a declared unsupported outcome, a raised error, or a
documented inert surface that says it is inert. Prohibited specifically:

- **silent degradation** — quietly doing less than was asked and returning the shape of a full
  success;
- **a stubbed success** — a placeholder, `TODO` or unimplemented path that returns a success value,
  a success status or a success-shaped record;
- **a fabricated result** — a synthesized, simulated, sampled or plausible-looking value presented
  as the product of real execution, including a value produced by a model and returned as though it
  were a retrieved, computed or externally confirmed fact.

**This is not a prohibition on fallback.** A declared fallback, a cached value served as a cached
value, a partial result labelled partial, a documented default and a retry are all legitimate; what
they have in common is that the caller can tell what they got. The rule is about the **honesty of
the report**, not the ambition of the behaviour.

### H-2 — Reference fixtures are labelled, inert, production-excluded, and never product

Inert reference operations may exist so that governance, consent and approval paths are exercisable
before a real capability is defined. Each one:

1. **is labelled a reference fixture**, recognisably and without a catalogue lookup;
2. **is inert** — it produces no real effect in any external system and modifies no account, device
   or record, and it claims no confirmation the platform could not perform;
3. **is excluded from production configuration**, and the exclusion is **enforced rather than
   documented**;
4. **is never presented to any user as a product capability**, and is never counted as,
   substituted for, or allowed to become a real defined capability.

A fixture is not a capability waiting to be finished. Promoting one is a deliberate act that
replaces it with a real capability under whatever gate that capability needs — never a relabelling.

### The authority this record affects

- `.claude/rules/10-principles.md` — **amended**, by appending §10.7 (`H-1`, `H-2`).
- `.claude/rules/00-authority.md` §00.3 — the engineering-baseline authority list gains a
  baseline-change source that is this ADR rather than a migrated pack. §00.4's statement that the
  Spec Kit artifacts are not authority is **unchanged**, and this record does not amend it.
- No architecture document is amended. A1, A2 and A3 are untouched, and `70-adr.md` §70.1 means
  this record could not amend them even if it tried.

## Consequences

### What this makes true

- **Spec Kit is no longer required to express these requirements.** After this record is accepted
  and §10.7 is written, `.claude/rules/10-principles.md` is their sole authority, and it cites
  `.specify/` and `specs/` nowhere.
- **Deleting `.specify/` and `specs/` no longer removes a normative requirement.** B15-1 is
  discharged, and Phase 15's §11 deletion manifest becomes executable.
- **`ragcore/tests/governance/test_fixtures_excluded.py` remains valid, intact and meaningful.** It
  is not weakened, narrowed, skipped or deleted. What changes is what it is evidence *for*: it
  moves from enforcing a retired constitution's clause to enforcing `H-2`, and every assertion it
  makes maps onto one of `H-2`'s four numbered properties.
- **Reference fixtures remain explicitly non-production**, by an enforced exclusion, in every
  environment the settings permit.
- **A successful-looking fabricated or stubbed result remains prohibited**, repository-wide and on
  every stack, rather than only for as long as the scaffold phase lasted.

### The one test-visible change, stated here because §70.8 requires it

`ragcore/src/ragcore/governance/fixtures.py` raises `ReferenceFixtureInProductionError` with a
message citing **`spec FR-SCOPE-006`**, and
`test_fixtures_excluded.py::test_the_refusal_says_why` asserts that citation is present. Both point
at a file this phase deletes.

Under this record the citation is **repointed** to `10-principles.md` `H-2`, in the message and in
the assertion together. **This is a repointing, not a relaxation**: the test continues to assert
that the refusal explains itself by naming its authority, with the same strength, and the authority
it names becomes one that will still exist. Nothing else in that file is touched, no assertion is
loosened, and no case is removed.

Phase 15's §11 manifest did not list this occurrence. It is recorded as **M-19** in the Phase 16
record so the omission is visible rather than absorbed.

### What does not change

- **No test is weakened.** No deletion, no `skip`, no `xfail`, no loosened assertion, no narrowed
  fixture (`.claude/rules/40-testing.md` §40.1).
- **No application, database, migration, LangGraph or architecture behaviour changes.** `H-1` and
  `H-2` state requirements the implementation already meets; this record gives them an authority,
  it does not alter the code they govern. The `fixtures.py` change is the text of an error message.
- **The constitution does not regain authority.** `00-authority.md` §00.4 stands unamended, and
  `specs/001-platform-scaffold/spec.md` gains none by being quoted here.
- **Clause 1 of Principle IX is not migrated.** It is phase-specific to the original scaffold and
  Phase 15 classified it historical; reviving it would be inventing a requirement.
- **Clause 2a is not duplicated.** A3 §6.2, P-11 and P-30 already carry it, and
  `00-authority.md` §00.5 forbids restating an owned requirement.

### What it costs

- `10-principles.md` gains a second rule-id space. `H-*` is deliberately distinct from `P-*` and
  `C-*` so that a reader can tell at a glance that its source is an ADR and not a migrated pack, but
  a third space in one file is a legibility cost this record accepts knowingly.
- `H-1` is **procedurally enforced**. No mechanism in this repository detects a stubbed success or a
  fabricated result, and this record does not authorize building one — that is a separate,
  human-directed decision (`.claude/rules/40-testing.md` §40.7). `H-2`, by contrast, is mechanically
  enforced for the fixtures that exist today, and only for those.

## Unresolved

- **Whether `H-1` should ever have a mechanical gate.** Recorded as an enforcement gap; nothing here
  authorizes building one.
- **Whether `H-2` should be extended to a fixture on a stack that has none today.** `H-2` is written
  repository-wide deliberately, but only `ragcore` has fixtures, so only `ragcore` has a check. A
  future .NET or frontend fixture owes the same four properties and would need its own.
- The eight ambiguous cross-stack citations recorded in
  `docs/migration/phase-15-final-spec-kit-reconciliation.md` §4.4 are **not** addressed by this
  record. They remain open, and closing them is a separate baseline decision.

## More Information

- Blocker **B15-1** and the full clause-by-clause decomposition:
  `docs/migration/phase-15-final-spec-kit-reconciliation.md` §6 and §6.1.
- The deletion manifest this record unblocks: the same file, §11.
- Source text, **migration input and not authority**: `.specify/memory/constitution.md` §IX;
  `specs/001-platform-scaffold/spec.md` `FR-SCOPE-004`…`FR-SCOPE-007`.
- The mechanical enforcement of clause 3: `ragcore/tests/governance/test_fixtures_excluded.py`,
  `ragcore/src/ragcore/governance/fixtures.py`.
