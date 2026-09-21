# 0011. Migrate the required-test-category baseline and the per-change test matrix

- **Status:** Proposed
- **Date:** 2026-09-21
- **Deciders:** Repository owner
- **Supersedes:** nothing
- **Amends:** `.claude/rules/40-testing.md`, which today states the testing baseline without the
  sixteen named test categories, without the per-change-type obligation matrix, and without the
  coverage policy that governs whether a percentage threshold may gate a merge
- **Related:** [0010](./0010-frontend-engineering-baseline.md) (the same class of act — migrating
  requirement text that the retired Spec Kit constitution held alone, under an ADR rather than by
  editorial transcription)

## Context and Problem Statement

Phase 11 recorded finding **D-11-2**: the retired Spec Kit constitution
(`.specify/memory/constitution.md`) carries three blocks of testing requirement that
`.claude/rules/40-testing.md` does not:

1. **§Required test categories** — sixteen named categories (Unit, Integration, Contract,
   Authorization, Tenant isolation, Retrieval isolation, Governance, Approval, Idempotency,
   Concurrency, Adapter, Architecture dependency, Configuration validation, Security, End-to-end
   golden path), stated as *"All are required; none substitutes for another"*, together with the
   rule that **a security or isolation fix without a failing-then-passing test is incomplete**.

2. **§Which change requires which category** — a twelve-row matrix binding a *kind of change* to
   the categories it owes, explicitly so that *"the obligation is mechanical at review rather than
   a matter of judgement"*, with **unit tests owed by every change**.

3. **§Coverage** — *"No line- or branch-coverage threshold is set, and none gates a merge"*, stated
   as a deliberate decision rather than an omission, with the condition that coverage **must not**
   become a gate without amending that section.

Phase 13 performed the content comparison D-11-2 asked for. `.claude/rules/40-testing.md` §40.5
names the test **kinds** that individual *principles* require — a contract suite for P-3, an
execution test for P-21, structural checks for P-11, P-20, P-25, P-31, an architecture assertion
for P-30 and P-12, a Roslyn check for DN-19. That is a different axis. §40.5 answers *"what does
this principle owe?"*; the constitution's matrix answers *"what does this change owe?"*. Neither
derives from the other, and no other file in `.claude/rules/` carries the second.

The categories themselves are not hypothetical. The directories exist and the suites run:
`ragcore/tests/{governance,authorization,isolation,idempotency,concurrency,contracts,checkpoint,integration,migrations,security,retention,egress,e2e,architecture}`,
`dotnet/tests/{Synthia.ArchitectureTests,Synthia.AuthorizationTests,Synthia.ContractTests,Synthia.TenantIsolationTests}`,
and `integrations/tests/{architecture,security,unit}`. What is missing is the **stated obligation**
that binds a change to them — the thing a reviewer applies.

`.specify/**` is scheduled for deletion. `.claude/rules/00-authority.md` §00.4 already records the
constitution as non-authoritative, so this is not a question of restoring its authority; it is a
question of whether the requirement it alone states survives the deletion of the file.

**Migration input is not authority.** The constitution is the *source text* for this migration in
exactly the sense ADR-0010 used it, and its non-authoritative status is unchanged by being read.

## Decision Drivers

- Deleting `.specify/**` with this content unmigrated destroys a requirement that no current
  authority states. Phase 13 will not certify retirement readiness while that is true.
- `.claude/rules/70-adr.md` §70.2 B(6) makes a change to a *mandatory engineering convention* —
  explicitly including test placement — a baseline change requiring an ADR. Adding sixteen required
  categories and a twelve-row obligation matrix is a baseline change by any reading.
- ADR-0010 set the precedent one phase earlier: constitution requirement text is migrated **under an
  accepted ADR**, never transcribed into a rule file as an editorial act.
- The coverage block is a *prohibition* (no threshold may gate a merge without amendment). Losing a
  prohibition is not a neutral loss; it silently permits the thing it forbade.

## Considered Options

1. **Migrate the three blocks into `.claude/rules/40-testing.md` under this ADR.** Preserves the
   requirement, keeps one testing authority, and keeps the baseline-change gate honest.
2. **Transcribe the blocks into `40-testing.md` without an ADR.** Rejected: it is a baseline change
   made by editorial act, which §70.2 B forbids and which ADR-0010 established is not how this
   repository migrates constitution text.
3. **Keep `.specify/memory/constitution.md` undeleted as the home for this content.** Rejected: it
   would make a document that `00-authority.md` §00.4 declares non-authoritative the sole home of a
   binding requirement, and would block the Spec Kit retirement indefinitely.
4. **Declare the matrix obsolete and drop it.** Rejected on the evidence: every category it names
   has a live suite, and the matrix is the only statement of when each is owed. Dropping it is a
   real reduction in the baseline, and would itself need to be the decision this record proposes.

## Decision Outcome

**Option 1.** Migrate all three blocks into `.claude/rules/40-testing.md` as a new section, with:

- the sixteen categories and what each proves, stated as required and non-substitutable;
- the per-change-type matrix, unchanged in meaning, with unit tests owed by every change;
- the failing-then-passing obligation for a security or isolation fix;
- the coverage policy, including the prohibition on a coverage threshold becoming a merge gate
  without a further ADR;
- the recorded exception the constitution carries — that two hard failures (*tenant context derived
  from an untrusted client field*, and *authorization bypass*) have **no** such test at the backend
  because the protection was deferred and not replaced, that the obligation is therefore **not met**
  for that pair, and that no weaker test may be written to appear to meet it. This is carried across
  as a recorded gap, not repaired (`.claude/rules/00-authority.md` §00.7).

The frontend row of the matrix (*"Touches a client surface's primary journey → Frontend
accessibility; end-to-end golden path where the journey is one"*) is already owned by
`.claude/rules/23-angular.md` FE-NG-5 and FE-NG-6. The migrated matrix **points at those rules** for
that row rather than restating them (`.claude/rules/00-authority.md` §00.5).

Enforcement is recorded honestly: the categories are **procedural** — reviewed, not gated — because
no mechanism in this repository maps a diff to the categories it owes. That is an enforcement gap to
record, not a reason to weaken the requirement, and this ADR does **not** authorize building such a
mechanism (Phase 9 brief §24).

**Nothing is implemented on this record until a human accepts it** (`.claude/rules/70-adr.md`
§70.3). Claude wrote it with status `Proposed`; Claude does not accept it.

## Consequences

**What becomes true.**

- `.claude/rules/40-testing.md` becomes the single authority for both testing axes — what a
  *principle* owes (§40.5) and what a *change* owes (the migrated matrix).
- `.specify/memory/constitution.md` can be deleted without losing a testing requirement.
- The coverage prohibition survives as a rule with a named amendment path.

**What it costs.**

- `40-testing.md` grows by roughly a page, and a reviewer must read two tables rather than one.
- The matrix's obligations become visible against changes that do not currently carry those tests.
  Any such gap is a **deviation to record** (`.claude/rules/00-authority.md` §00.7) — it is not a
  licence to weaken or delete a test (`.claude/rules/40-testing.md` §40.1), and it is not a reason
  to narrow the migrated requirement to match what the tree already does.
- One new enforcement gap is recorded: no mechanical check binds a diff to its owed categories.

**What does not change.**

- No test is added, removed, weakened, skipped or loosened by this record.
- No application, database, migration, LangGraph or architecture behaviour changes.
- The constitution does not regain authority. `00-authority.md` §00.4 stands unamended.
- The gate-owned testing obligations stay where they are: `.claude/rules/50-database.md` §50.8,
  `.claude/rules/30-langgraph.md` §30.9, `.claude/rules/70-adr.md` §70.8,
  `.claude/rules/90-functional-knowledge.md` §90.10.

## Unresolved

- Whether the two unmet hard-failure tests named in the coverage exception are closed by writing the
  tests or by restoring the deferred protection. That is ADR-0008's open item **D-01**, not this
  record's.
- Whether a mechanical diff-to-category check should ever exist. Recorded as an enforcement gap;
  building one is a separate, human-directed decision.

## More Information

- Finding **D-11-2**: `docs/migration/phase-11-retirement-readiness.md` §L-3, §M-1, §HD-2.
- The content comparison that closed the question:
  `docs/migration/phase-13-spec-kit-content-reconciliation.md` §6.
- Source text: `.specify/memory/constitution.md` §Required test categories, §Which change requires
  which category, §Coverage — **migration input, not authority**.
