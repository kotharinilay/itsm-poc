# Phase 14 — migrating the testing baseline out of the retired Spec Kit constitution

**Phase record. This document is not authority.** It records what Phase 14 did, what it verified,
and what it deliberately left open. The testing-baseline authority it produced is
`.claude/rules/40-testing.md` §40.8–§40.10; the decision that authorized the migration is
`docs/adr/0011-required-test-categories-baseline.md`.

Phase 14 closes the last substantive Spec Kit retirement blocker recorded by Phase 13:
**D-11-2 / BL-13-1** — the testing requirement text held only by `.specify/memory/constitution.md`.

---

## 1. Starting state

| Check | Result |
|---|---|
| Branch | `speckit-to-claude` at `ce09b3e` ("accepted adr") |
| Working tree | clean |
| Phase 13 commit present | yes — `869c3ec` *docs(governance): reconcile Spec Kit content and repoint stale citations (phase 13)* |
| Phase 13 follow-ups present | `61335b4` (count corrected to fifteen), `eb1a828` (ADR-0011 indexed, fixtures re-anchored), `ff4e75b`, `ce09b3e` (acceptance) |
| `docs/adr/0011-required-test-categories-baseline.md` | exists |
| Staged/unplaced ADR file | none — the record is on disk, not staged |
| `docs/adr/0010-frontend-engineering-baseline.md` | exists, `Status: Accepted` |
| `.specify/**` and `specs/**` | present and unmodified |

Work was carried out in an isolated git worktree branched from `ce09b3e` (**not** from `main`), so
that Phase 14 builds on the completed Phase 13 state rather than resetting it. No user work was
reset, discarded or rewritten.

## 2. ADR-0011 acceptance verification

```text
docs/adr/0011-required-test-categories-baseline.md
  - **Status:** Accepted
  - **Date:** 2026-09-21
  - **Amends:** .claude/rules/40-testing.md
```

Status was read from the record on disk and **not** changed by this phase. Claude neither accepted,
rejected nor edited the status (`.claude/rules/70-adr.md` §70.5, §70.3). Implementation began only
because the record already carried `Accepted` when the phase started.

**BL-13-3 is closed.** Phase 13 recorded that the placed ADR-0011 misstated its own source as
*"sixteen named categories"*. The record now reads **fifteen** throughout, corrected by the
repository owner in `61335b4` before acceptance. The count in the accepted record matches the
source, so §2 of the Phase 14 brief's stop condition did not fire.

## 3. Source count verification — **fifteen** categories

`.specify/memory/constitution.md` was read independently of the ADR. The three blocks are at:

| Block | Line | Content |
|---|---|---|
| `### Required test categories` | 757 | a 15-row table + the failing-then-passing sentence |
| `### Which change requires which category` | 781 | a 12-row table + the every-change unit rule |
| `### Coverage` | 802 | the no-threshold policy + the recorded exception |

**The source table has exactly fifteen rows.** No sixteenth category exists and none was invented.
The change matrix has exactly twelve rows.

> **Residual editorial defect — reported, then corrected on the owner's instruction.**
> `docs/migration/phase-13-spec-kit-content-reconciliation.md` line 623 described the source as
> *"§Required test categories (16)"*. It was an editorial defect under
> `.claude/rules/00-authority.md` §00.6, not a conflict: the count was already correct everywhere
> it mattered (the ADR, and BL-13-3's own row on line 625, which states fifteen correctly).
>
> Phase 14 **reported** it rather than repairing it, because amending a phase record is a
> human-directed act. The repository owner then directed the correction, and line 623 now reads
> **(15)**. The surrounding rows are unchanged: BL-13-3 and §14 item 2 still quote the ADR's
> original *"sixteen named categories"* wording, because there they are describing the error that
> was fixed, and rewriting those quotations would destroy the record of it.

## 4. Category mapping — source → `40-testing.md` §40.8

All fifteen migrated with their stated proof preserved. Identifiers `TC-01`…`TC-15` are assigned by
**this** migration, following the repository's existing convention of migration-assigned ids
(`BL-*` in Phase 9, `FE-*` in Phase 12). They are **not** written back into the source.

| ID | Category | Proof preserved | Source row |
|---|---|---|---|
| **TC-01** | Unit | Component behaviour in isolation | verbatim |
| **TC-02** | Integration | Real collaborators, real database, real messaging | verbatim |
| **TC-03** | Contract | Published API and message shapes, including between deployables | verbatim |
| **TC-04** | Authorization | Every operation against every role set, including the empty intersection | verbatim |
| **TC-05** | Tenant isolation | No path returns another organisation's data | verbatim |
| **TC-06** | Retrieval isolation | The tenant filter cannot be evaded, including by crafted input | verbatim |
| **TC-07** | Governance | Treatment comes from the catalogue and never from model output | verbatim |
| **TC-08** | Approval | Binding, expiry, first-valid-verdict-wins, no synthesized verdict | verbatim |
| **TC-09** | Idempotency | At-least-once delivery produces exactly one effect | verbatim |
| **TC-10** | Concurrency | Concurrent claims and decisions resolve to one outcome | verbatim |
| **TC-11** | Adapter | Provider behaviour stays behind its boundary | verbatim |
| **TC-12** | Architecture dependency | Module boundaries, banned APIs, the no-cross-deployable-dependency rule | verbatim |
| **TC-13** | Configuration validation | Options bind, validate and fail fast at start | verbatim |
| **TC-14** | Security | *"The prohibitions in this document are actually unreachable"* → **"The prohibitions stated by the baseline and the architecture are actually unreachable"** | re-anchored |
| **TC-15** | End-to-end golden path | A representative journey completes through every layer | verbatim |

**One deliberate wording change, TC-14.** The source says *"the prohibitions in **this document**"*,
where "this document" is the constitution. Carrying that phrase unchanged would make the migrated
rule point back at a non-authoritative file for its own subject matter. The referent is re-anchored
to the baseline and the architecture, which is where those prohibitions now live. **The obligation
is unchanged**; only the pointer moved.

The non-substitutability rule and the failing-then-passing rule both carried across:

- *"All are required; none substitutes for another"* → *"All fifteen are required; none substitutes
  for another"* (the count made explicit, so a future drop is visible).
- *"A security or isolation fix without a failing-then-passing test is incomplete"* — verbatim, with
  the **order** now stated explicitly rather than left in the hyphenated adjective.

## 5. Change-matrix mapping — source → `40-testing.md` §40.9

All twelve rows migrated. Category names were **not** altered to fit what the tree currently
contains; each owed category is named by its `TC-*` id *and* its source name.

| ID | Source row | Owes (migrated) |
|---|---|---|
| **CM-01** | Adds or alters an API endpoint or message shape | TC-03; TC-04 |
| **CM-02** | Adds or alters an authorization rule, role set or accepted-role declaration | TC-04; TC-14 |
| **CM-03** | Touches a query, repository, view or retrieval path | TC-05; TC-06 where retrieval is involved |
| **CM-04** | Adds or alters a catalogue entry, treatment policy or gate condition | TC-07; TC-04 |
| **CM-05** | Touches approval, consent, verdict or the resume path | TC-08; TC-10; TC-09 |
| **CM-06** | Adds or alters an external side effect | TC-09; TC-11 |
| **CM-07** | Adds or alters a migration, table or published view | TC-02; TC-05; TC-12 |
| **CM-08** | Adds or alters a module boundary, project reference or import | TC-12 |
| **CM-09** | Adds or alters a configuration option or secret reference | TC-13 |
| **CM-10** | Touches an outbox, trigger, claim or worker | TC-09; TC-10 |
| **CM-11** | Touches a client surface's primary journey | Frontend accessibility → **FE-NG-5 / FE-NG-6** (see §6); **plus** TC-15 where the journey is one |
| **CM-12** | Fixes a security or isolation defect | the relevant category, **failing first, then passing** |

Both governing semantics preserved verbatim in meaning:

- **A change matching several rows owes all of their categories.**
- **TC-01 Unit is owed by every change**, and is therefore not repeated in any row — the migrated
  text states both halves, so the absence of Unit from the rows cannot be misread as an exemption.

The matrix is stated as an **obligation**, not a heuristic. Its purpose sentence — *"so the
obligation is mechanical at review rather than a matter of judgement"* — is carried across, and the
word *mechanical* there describes the **reviewer's** application of the table. It is **not** a claim
that a mechanism enforces it; enforcement is recorded as `procedural`. See §10.

## 6. The frontend row — referenced, not duplicated

`CM-11` is the only row whose owed obligation was already migrated elsewhere. Phase 12 migrated the
frontend baseline under ADR-0010, and the accessibility requirement lives at:

- `.claude/rules/23-angular.md` **FE-NG-5** — WCAG 2.2 Level AA on every surface
- `.claude/rules/23-angular.md` **FE-NG-6** — the project-supported test runner, and the a11y test a
  journey change owes

`40-testing.md` §40.9 **points at those two rules by id** and restates neither. The division is the
one `.claude/rules/00-authority.md` §00.5 requires:

```text
the MATRIX is authoritative for the OBLIGATION  (this change owes frontend accessibility)
the ANGULAR RULE is authoritative for the REQUIREMENT  (what frontend accessibility means)
```

A governance assertion proves the pointer exists **and** that the FE-NG-5/FE-NG-6 body text was not
copied into `40-testing.md` (§11). `CM-11` still owes `TC-15` in its own right, because the
end-to-end golden path is this file's category, not the Angular rule's.

## 7. Coverage policy migration

All three aspects preserved in `40-testing.md` §40.10:

| Aspect | Migrated as |
|---|---|
| No line- or branch-coverage threshold is set | verbatim, with *"This is deliberate, not an omission"* |
| None gates a merge | verbatim; the behavioural rationale carried across in full |
| It must not become a gate without amendment | strengthened to name the instrument: an **accepted ADR** under `.claude/rules/70-adr.md` §70.2 B(6) |

**No threshold was introduced. No coverage gate was added.** A governance assertion fails the suite
if any percentage-shaped coverage threshold appears in the file.

The amendment path is the only substantive change: the source said *"MUST NOT become a gate without
amending this section"*, where the section lived in a document that is not authority. The migrated
rule names the actual instrument that can change a mandatory engineering convention in this
repository. The prohibition is **not weakened** by that — it is made harder to bypass, because
"amending a section" is an edit and "an accepted ADR" is a gated human decision.

## 8. The recorded hard-failure exception

Carried across as a **gap, not a carve-out**, in `40-testing.md` §40.10:

> Two hard failures — **tenant context derived from an untrusted client field**, and **authorization
> bypass** — have **no** failing-then-passing test at the backend, because the protection they
> tested was deferred and not replaced.

The distinction the source insists on is preserved explicitly:

```text
The obligation in §40.8 is unchanged.  It is simply NOT MET for that pair.
```

And the prohibition that follows from it:

> **No test may be written that appears to meet it by asserting something weaker.**

Recorded as a deviation under `.claude/rules/00-authority.md` §00.7. The pointer was re-anchored
from the constitution's internal `#d-01` anchor to
`docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md`, which is where **D-01**
actually lives and which remains `Accepted`. **The deferred architecture decision was not reopened,
and no substitute test was written.**

## 9. Duplication and context-loading analysis

### The two axes are distinguished, not merged

`40-testing.md` now states two obligations on different axes and says so in both places:

| Axis | Section | Answers |
|---|---|---|
| **What a principle owes** | §40.5 (pre-existing, unchanged) | *"what does this principle owe?"* — a contract suite for P-3, an execution test for P-21, structural checks for P-11/P-20/P-25/P-31, architecture assertions for P-30/P-12, a Roslyn check for DN-19 |
| **What a change owes** | §40.8 + §40.9 (migrated) | *"what does this change owe?"* — TC-01…TC-15, bound to a change by CM-01…CM-12 |

§40.5 gained one paragraph naming the split and pointing forward; nothing in it was removed,
reworded or absorbed. A change satisfies **both** axes.

### Nothing gate-owned was duplicated

The obligations already owned elsewhere are cross-referenced and not restated. The pointer table at
the head of `40-testing.md` was already correct and is unchanged:

| Obligation | Owner (unchanged) |
|---|---|
| Migration and persistence suites, single head, working `downgrade()` | `50-database.md` §50.8 |
| Graph, checkpoint, governance, idempotency, authorization, isolation, architecture suites | `30-langgraph.md` §30.9 |
| An accepted ADR never licenses skipping a test | `70-adr.md` §70.8 |
| Updating the functional record never substitutes for a gate | `90-functional-knowledge.md` §90.10 |
| Frontend quality gate; `.spec.ts` naming; the Angular runner; WCAG 2.2 AA; the Electron security suite | `22-web-typescript.md`, `23-angular.md`, `24-electron.md` (§40.4) |

### Section numbering

The migrated material was **appended** as §40.8, §40.9 and §40.10 rather than inserted after §40.5.
Inserting would have renumbered §40.6 and §40.7, which carry 4 and 3 inbound cross-references
respectively from other rule files and from the guard suite. Appending keeps every existing section
number stable and breaks no reference. The file says so in-place, so the ordering is not mistaken
for an accident.

### Context loading

`40-testing.md` carries no `paths:` frontmatter and loads every session (`CLAUDE.md` §4). The file
grew from 151 to ~280 lines. That is a deliberate cost accepted by ADR-0011 ("`40-testing.md` grows
by roughly a page"), and it is the cost of the requirement being loaded at all rather than living in
a file scheduled for deletion.

## 10. Enforcement status, and **EG-10**

Enforcement is recorded with the honest vocabulary
(`docs/migration/phase-9-baseline-coverage.md` §5): `mechanical` | `partial` | `procedural` |
`currently-unenforced`.

| Migrated block | Enforcement | Why |
|---|---|---|
| §40.8 categories TC-01…TC-15 | **procedural** | The suites exist and run in CI (§40.6). Nothing binds a *change* to the categories it owes |
| §40.9 matrix CM-01…CM-12 | **procedural** | Applied by a reviewer |
| §40.10 coverage prohibition | **procedural** | Honoured by the absence of a coverage gate in every workflow; nothing mechanically prevents one being added |

> **EG-10 — no diff-to-category mechanism.**
> The repository has **no** deterministic check that maps a changed file or a diff to all the test
> categories §40.9 says it owes. Recorded, **not** closed. ADR-0011 does not authorize building one,
> and building one is a separate, human-directed decision (Phase 9 brief §24). **No fake mechanical
> check was created**, and no enforcement claim in the migrated text is stronger than what actually
> runs.

EG-10 was first recorded in `docs/migration/phase-13-spec-kit-content-reconciliation.md` §636 as a
gap ADR-0011's migration *would* create. It now exists and is stated inline in the rule that carries
the requirement, following EG-9's precedent from Phase 12.

**What governance *does* prove** is that the migrated baseline text is present and traceable — see
§11. That is a different and weaker claim than enforcing the obligation, and it is stated as such.

## 11. Governance assertions added

`.claude/hooks/test_guards.py` gained a Phase 14 block. **No existing assertion was deleted,
skipped, loosened or narrowed** (`.claude/rules/40-testing.md` §40.1). The suite went from
**611** to **792** checks — **+181**, all additive.

**Cross-check that nothing existing was broken.** The Phase 13 guard suite, restored verbatim from
`HEAD` and run unchanged against the Phase 14 rule files, passes **611/611**. Every pre-existing
assertion therefore still holds against the migrated `40-testing.md`; the 181 new checks are the
only difference.

Assertions are keyed on **unique identifiers and meaning**, never on a count alone — a count check
would pass against fifteen empty rows:

| Group | Proves |
|---|---|
| (1) | Each of TC-01…TC-15 is defined **exactly once**, carries its category **name**, and carries the **proof** it makes. `TC-16` is absent |
| (2) | The failing-then-passing sentence survives, **and** the order is stated explicitly |
| (3) | Each of CM-01…CM-12 is defined exactly once, states the change it matches, and still names each `TC-*` it owes. `CM-13` is absent |
| (4) | TC-01 Unit is explicitly owed by every change; the multi-row rule survives; CM-12 carries the failing-first ordering |
| (5) | CM-11 points at `23-angular.md` FE-NG-5/FE-NG-6, still owes TC-15, and the FE-NG body text is **not** duplicated into `40-testing.md`; FE-NG-5/FE-NG-6 remain defined once each in `23-angular.md` |
| (6) | All three coverage aspects survive; the ADR amendment path is named; **no percentage threshold exists** |
| (7) | Both hard-failure exceptions remain recorded; the "obligation unchanged / NOT MET" wording survives; the no-weaker-substitute prohibition survives; the ADR-0008 / D-01 pointer exists |
| (8) | Enforcement is claimed as `procedural`; EG-10 is recorded as a gap and stated as not closed |
| (9) | The two axes are distinguished; §40.5 is intact; gate-owned obligations are cross-referenced; §40.1 is untouched |
| (10) | ADR-0011 exists, is structurally valid under H5, is **`Accepted`**, names `40-testing.md`, says *fifteen* and never *sixteen*, keeps the constitution as migration input, and is indexed |
| (10b) | The ADR index lists **eleven** records in **ascending** order, and every displayed status **matches the record on disk** |
| (11) | This Phase 14 record exists, verifies the count, traces every TC-* and CM-*, carries EG-10, and leaves B13-2 / B13-3 open |

The pre-existing Spec Kit retirement assertions still pass unchanged — in particular the one
requiring that **every live Claude file naming Spec Kit denies it authority**. The new §40.8
preamble names `.specify/memory/constitution.md` and carries the denial *"It is migration input. It
is not authority."* in the same file.

## 12. Tests and exact results

Run from the Phase 14 worktree for governance, and from the main checkout for the language suites —
the application trees are byte-identical at this commit, since the Phase 14 diff touches only
`.claude/**` and `docs/**`.

| Gate | Command | Result |
|---|---|---|
| Governance guards | `python .claude/hooks/test_guards.py` | **792/792 checks passed** |
| Governance guards, Phase 13 version | `HEAD`'s `test_guards.py`, run against the Phase 14 rules | **611/611 checks passed** — no existing assertion broken |
| RagCore lint | `uv run ruff check .` | **pass** — all checks passed |
| RagCore format | `uv run ruff format --check .` | **pass** — 248 files already formatted |
| RagCore types | `uv run mypy` | **pass** — no issues in 219 source files |
| RagCore tests | `uv run pytest -q` | **1301 passed**, 9 warnings, 81.65s |
| Integrations lint | `uv run ruff check .` | **pass** |
| Integrations format | `uv run ruff format --check .` | **pass** — 68 files already formatted |
| Integrations types | `uv run mypy` | **pass** — no issues in 67 source files |
| Integrations tests | `uv run pytest -q` | **155 passed**, 1 warning, 7.77s |
| .NET build | `dotnet build` | **succeeded — 0 Warning(s), 0 Error(s)** |
| .NET tests | `dotnet test` | **246 passed, 0 failed, 0 skipped** across 11 assemblies (ArchitectureTests 88, SharedKernel 69, ContractTests 51, Authorization 21, TenantIsolation 11, six module suites 1 each) |
| Web lint | `npx eslint .` | **pass** |
| Web format | `npx prettier --check .` | **pass** |
| Web tests | `npm test` | **9 passed**, 3 suites, 0 failed |
| Desktop types | `npm run typecheck` | **pass** |
| Desktop lint | `npm run lint` | **pass** |
| Desktop tests | `npx vitest run` | **178 passed**, 4 files |
| Boundaries | `bash build/scripts/check-boundaries.sh` | **pass** — all four boundary assertions |

### The two deviations, preserved honestly — **neither is fixed**

| | Command | Result now | Verdict |
|---|---|---|---|
| **DV-13** | `npx tsc -b` in `apps/web` | **2 errors**, identical to the Phase 13 baseline: `projects/customer-portal/src/app/app.config.ts(7,31)` and `projects/staff-portal/src/app/app.config.ts(7,31)` — `TS2305: Module '"platform-core"' has no exported member 'readHostedConfig'` | **unchanged — still open** |
| **DV-14** | `dotnet format --verify-no-changes` in `dotnet/` | **fails**, 12 files, Windows CRLF whitespace. None is a file this phase touched — Phase 14 modified zero `.cs` files. CI runs on Linux | **unchanged — still open** |

Both are recorded, not repaired (`.claude/rules/00-authority.md` §00.7). Neither was "fixed" by
this phase and neither is reported as fixed.

### One environment flake, noted

The guard suite's Windows worktree-cleanup assertion (*"every temporary worktree was removed"*)
failed on the first run and passed on an immediate re-run, leaving
`.claude/worktrees/guard-regression-probe` behind once. This is a pre-existing Windows file-lock
timing issue in the suite's own fixture teardown, unrelated to Phase 14 — no guard code path in that
block was modified. Recorded as an observation, not repaired.

## 13. Remaining findings, carried forward unchanged

| Finding | Status after Phase 14 | Why it stays open |
|---|---|---|
| **B13-2** — the stale-citation surface is 344 lines across 220 files (not the ~35 Phase 12 recorded); `CLAUDE.md` §10's claim that the stale `constitution §…` pointers are confined to `apps/**` and `.github/workflows/**` is incomplete | **OPEN — deliberately not touched** | Out of Phase 14 scope by the phase brief §13. No bulk citation rewrite was performed, and no unrelated source comment was changed to reduce a search count. The D-11-2 migration is independently reviewable as a result. One instance was observed in `docs/adr/README.md` §"Writing a new record" (*"constitution Principle V"*, *"Principle VI"*, *"the constitution states unconditionally"*) and **left in place** for the same reason |
| **B13-3** — constitution **Principle IX** (*Scaffold Honestly; Do Not Invent Product*) has no migrated home in `.claude/rules/**` | **OPEN — classification preserved** | **No new requirement id was invented.** Converting a historical principle into a baseline rule is a decision a human makes, under `70-adr.md` §70.2 B, not something a migration phase creates because the source once contained it |
| **DV-13** — `apps/web` `npx tsc -b` fails on 2 pre-existing `readHostedConfig` errors (a deviation from FE-SH-3) | **OPEN — verified still failing identically** | Repairing it would be an application change, out of scope (§15 of the brief) |
| **DV-14** — `dotnet format --verify-no-changes` fails locally on 12 files for Windows CRLF reasons | **OPEN — verified still failing** | Same |
| **EG-10** — no mechanism maps a diff to its owed categories | **NEWLY RECORDED** | Building one is a separate human decision |
| Editorial: Phase 13 record line 623 said *"(16)"* | **CLOSED** — corrected to **(15)** | Reported by Phase 14 rather than repaired, then corrected on the repository owner's explicit instruction. The quotations of the original error in BL-13-3 and §14 are deliberately left intact |

**Closed by this phase:** **D-11-2 / BL-13-1** (the testing baseline is migrated into current
authority) and **BL-13-3** (the ADR's count error, corrected by the owner before acceptance).

## 14. Retirement readiness after Phase 14

| Readiness question | Before Phase 14 | After |
|---|---|---|
| Does any binding requirement exist **only** in `.specify/memory/constitution.md`? | **Yes** — the three testing blocks (D-11-2) | **No** |
| Is `.claude/rules/40-testing.md` the single testing-baseline authority? | Yes as the sole file, **incomplete in content** | **Yes, and complete** |
| Is the constitution still explicitly non-authoritative? | Yes | **Yes** — `00-authority.md` §00.4 unamended; §40.8's preamble denies it authority in the same breath as citing it |
| Has any Spec Kit skill returned? | No | **No** — exactly four governance skills remain: `adr-author`, `db-change`, `functional-update`, `langgraph-change` |
| Does any active Claude configuration invoke Spec Kit? | No | **No** — `.claude/settings.json` matches nothing on `speckit|\.specify` |
| Are `.specify/**` and `specs/**` unchanged? | — | **Yes** — `git diff --name-only HEAD -- .specify specs` returns **0 files** |

The trees remain on disk. **Phase 14 deleted nothing**, as required.

Historical references to the constitution still occur across the repository. That is acceptable and
expected: the test is whether any of them is a **current authority or dependency**, not whether the
word appears zero times. Every live `.claude/**` and `CLAUDE.md` mention is asserted by the guard
suite to deny authority.

## 15. Recommendation for Phase 15

```text
READY FOR PHASE 15 — FINAL SPEC KIT REFERENCE / AUTHORITY CLEANUP
```

Phase 15 should, in this order:

1. **Repoint the stale citation surface (B13-2).** 344 lines across 220 files still read
   `constitution §…` or `constitution Principle …`. Repoint each to the rule that now carries the
   requirement — `22-web-typescript.md`, `23-angular.md`, `24-electron.md` for the frontend blocks,
   `40-testing.md` §40.8–§40.10 for testing. Correct `CLAUDE.md` §10, whose scope statement is
   incomplete. Include `docs/adr/README.md` §"Writing a new record", which still makes Principle V
   and Principle VI live triggers for writing an ADR.
2. **Put B13-3 to the repository owner as a decision, not a migration.** Either Principle IX gets a
   requirement id under an ADR, or it is recorded as deliberately retired. **Do not invent one.**
3. **Only then delete `.specify/**` and `specs/**`,** in a commit that does nothing else, so the
   deletion is reviewable on its own.
4. **Re-run the full gate set afterwards,** and invert the guard assertions that currently prove the
   trees are untouched into assertions that they are gone — an inversion, in the governed sense
   Phase 12 established, not a deletion.
5. **Leave DV-13, DV-14 and EG-10 open.** None is a Spec Kit retirement blocker, and each is a
   separate human-directed decision.

**Nothing blocks the deletion of `.specify/**` and `specs/**` on requirement-preservation grounds
after this phase.** The remaining work is citation hygiene and one open classification question,
neither of which depends on the trees continuing to exist.
