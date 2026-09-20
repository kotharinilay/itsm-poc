# Phase 10 — Baseline reconciliation and remaining governance decisions

**This is the authoritative Phase 10 record.** It records one resolved decision, the amendment that
resolved it, the consistency verification that followed, and everything that deliberately remains
open.

It is a **migration record**, not authority. The operative baseline is `.claude/rules/`
(`.claude/rules/00-authority.md` §00.3).

| | |
|---|---|
| **Phase** | 10 — baseline reconciliation (conflict **CF-1**, decision **UD-3**) |
| **Revision at start of phase** | `12133b1e8cfc0b22dc28be305f800216f5f9df98` — *chore(repo): ignore .claude/worktrees scratch* |
| **Branch** | `speckit-to-claude` |
| **Repository content established by** | `git ls-files` (generated and untracked residue excluded) |
| **Predecessors** | `docs/migration/phase-7-validation.md`, `phase-8-worktree-guard.md`, `phase-9-baseline-input.md`, `phase-9-baseline-coverage.md` |
| **Requirement count** | **167 — unchanged.** One item was reworded; none added, none removed |

---

## 1. Decision taken

> **PostgreSQL schema migrations remain owned and executed by the Python/RagCore migration path
> using Alembic. There is no requirement to move schema migrations into .NET/EF Core.**

Supplied as an **explicit human decision** in the Phase 10 brief. It is not inferred from a task
description, a plan, a precedent in the tree, a satisfied hook, or the session running unattended
(`.claude/rules/00-authority.md` §00.10).

The decision **confirms the model that A2 and `.claude/rules/50-database.md` already stated.** It
introduces no architecture. Schema ownership, the store, the trust boundary and the deployment
ordering are identical before and after it.

## 2. CF-1 resolution

**CF-1** (`phase-9-baseline-coverage.md` §9.1) was the conflict between:

| | |
|---|---|
| **Source A** | the explicit baseline block, item `BL-10`: *"Migrations: EF Migrations bundle in CI/deploy step"* |
| **Source B** | `.claude/rules/50-database.md` §50.7 + **A2 §8.1**: Alembic under `ragcore/migrations/` is the single schema-migration mechanism; the .NET side owns **no** migrations |

**Resolved by amending Source A** — option (i) of decision **UD-3**. This is the disposition
`00-authority.md` §00.6 contemplates when the outlier is an input rather than an authority: a human
decided, and Claude did not pick a winner.

```text
CF-1  STATUS: CLOSED
UD-3  STATUS: CLOSED
Closed by amending the baseline INPUT.
No architecture changed.  No rule in force changed.
No test, analyzer, configuration or application file was touched.
```

**What did not change.** `50-database.md` §50.7 is word-for-word what it was. `20-dotnet.md`'s
prohibition on EF Core migrations, a second migration tool, a second migration directory and
startup-time DDL is word-for-word what it was. `NoMigrationTests` is untouched.

## 3. Exact baseline amendment

Recorded in full, with its authority, in **`docs/migration/phase-9-baseline-input.md` Appendix A.1**.
Reproduced here:

**Original wording**

> Migrations: EF Migrations bundle in CI/deploy step

**Approved replacement wording**

> Migrations: The platform schema is owned by exactly one versioned migration mechanism, executed
> as a gated job in the CI/deploy step before the new application revision is activated — never at
> application startup. In this repository that mechanism is Alembic, under `ragcore/migrations/`.
> The .NET deployable owns no migrations and applies no DDL; it reads through published views that
> the same migration history creates and versions.

**Abstraction level.** The replacement is deliberately a **repository- and deployment-level** rule —
*one versioned mechanism, gated in CI/deploy, never at startup* — with the repository's
instantiation of it named. It is **not** written as a RagCore implementation detail, because the
obligation is not RagCore's alone: it binds the .NET deployable (owns none, applies no DDL) and the
deployment pipeline (gated job, before revision activation) as much as it binds `ragcore/**`.

**Semantic scope change, stated exactly.** The item's obligation is preserved; its mechanism
attribution and abstraction level change.

| | Before | After |
|---|---|---|
| Named mechanism | EF Migrations, bundled from the .NET side | Alembic, under `ragcore/migrations/` |
| Execution point | "a CI/deploy step" | a gated job in the CI/deploy step, **before revision activation**, never at application startup |
| Abstraction level | a .NET framework choice | a repository/deployment-level rule about ownership and execution point |
| Scope | `.NET / C#`, database | `.NET / C#` (owns none), Python (owns it), database, deployment/runtime |
| Rule in force | `50-database.md` | `50-database.md` — **unchanged** |

The EF requirement is **withdrawn** (a narrowing). The *never at startup* and *before revision
activation* qualifiers — already binding under `50-database.md` §50.7 and `80-security-ops.md` §80.6
— are now stated in the input too (a widening of the **text**, not of the **obligation**). **No
obligation in force before the amendment stopped being in force, and none was newly created.**

## 4. Authority and evidence

| Source | What it establishes |
|---|---|
| **A2** §11.4(5) | Database, index and schema migrations are *controlled* as a deliberate release step |
| **A2** §8.1 | Azure Postgres is the platform store whose schema is at issue |
| `.claude/rules/50-database.md` §50.7 | Alembic under `ragcore/migrations/` is the mechanism; the .NET side owns **no** migrations; no second tool, no second directory, no startup DDL |
| `.claude/rules/80-security-ops.md` §80.6 | Gated job *before* revision activation; backward-compatible with the revision still serving |
| `ragcore/alembic.ini` | *"Alembic — the only tool that changes the platform schema"*; gated job, never at application startup |
| `.github/workflows/migrations.yml` | The gated job: single head, upgrade from base, models match DDL, every downgrade |
| `dotnet/tests/Synthia.ArchitectureTests/NoMigrationTests.cs` | `Database.Migrate()`, `EnsureCreated()` and EF migration files prohibited in the .NET deployable — mechanically gated |

`docs/adr/0003-database-migrations-and-rollback.md` (Accepted) records the same decision
historically. Per `.claude/rules/70-adr.md` §70.1 it is cited as **history and evidence**, never as
the authority for the replacement text.

### 4.1 ADR determination — none required, none invented

Assessed against every `.claude/rules/70-adr.md` §70.2 trigger; the trigger-by-trigger table is
`phase-9-baseline-input.md` Appendix A.2. Summary:

- **§70.2 A** — no component, zone, trust boundary, tenant boundary, identity/authority semantic,
  topology or store changes. A(8) governs a contradiction between two authoritative **architecture**
  documents; A1, A2 and A3 do not disagree here.
- **§70.2 B** — no analyzer, lint, `noqa`, `pragma`, nullability or warning setting is touched; no
  mandatory engineering convention changes; and the amendment **removes** a contradiction with a
  migrated baseline rule rather than creating one (B(7)).
- **§70.2 C** — no `30-langgraph.md` §30.4 trigger. Checkpoint persistence, checkpoint ownership and
  the `langgraph` schema exclusion are unchanged.
- **§70.2 D** — no change to identity-bearing immutability, to roles/principals/grants, to where an
  invariant lives, or to checkpoint-persistence ownership.

**Determination: no ADR is required.** The amendment changes no governed behaviour — it corrects an
input to say what the operative rule already said. Per the Phase 10 brief, no ADR was invented.
`docs/adr/` is unchanged; the next ADR number is still **0010**.

> **Why the amendment is still a governance act.** `00-authority.md` §00.3 makes the source block
> the **tiebreaker** if a rule file is ever found to have lost a requirement. Amending a tiebreaker
> is not an editorial tidy-up, which is why the full audit trail in Appendix A is mandatory and why
> the original wording is preserved verbatim there.

## 5. Consistency verification

Every location that states or implies schema-migration ownership was checked.

| Location | States | Verdict |
|---|---|---|
| `docs/migration/phase-9-baseline-input.md` `BL-10` | Alembic under `ragcore/migrations/`; gated job; never at startup; .NET owns none | **amended — consistent** |
| `.claude/rules/50-database.md` §50.7 | Alembic is the mechanism; .NET owns no migrations; no second tool/directory; no startup DDL | consistent — **section text unchanged**, closure note added |
| `.claude/rules/20-dotnet.md` `BL-10` | This deployable owns no schema; no EF migration, bundle, second tool, second directory or startup DDL | **updated** — conflict notice replaced by closure notice; `NoMigrationTests` still named as the live gate |
| `.claude/rules/21-python.md` §21.9 | `BL-10` removed from the "no Python counterpart" list; the amended item applies to `ragcore/**` directly | **updated** |
| `.claude/rules/80-security-ops.md` §80.6 | Gated job before revision activation, never at startup; backward-compatible with the serving revision | consistent — **no change needed** |
| `.github/workflows/migrations.yml` | Alembic job: single head, upgrade from base, models match DDL, every downgrade | consistent — **not modified** |
| `ragcore/alembic.ini` | The only tool that changes the platform schema; gated job, never at startup | consistent — **not modified** |
| `dotnet/tests/.../NoMigrationTests.cs` | .NET owns no schema; migrate/ensure-created APIs prohibited | consistent — **not modified** |
| `docs/migration/phase-9-baseline-coverage.md` | `BL-10` row, §4 roll-up, §5.2 enforcement roll-up, §9.1, §9.3, §11 | **updated** — see §5.1 |

**The .NET governance remains explicitly free of EF migrations.** Nothing introduced an EF
migration file, an EF migration bundle, a second migration directory, a second schema authority or
startup DDL. `20-dotnet.md` `BL-10` now states the prohibition as a **rule** rather than as the
losing side of a conflict, which is a strengthening of its readability, not of its content.

### 5.1 Phase 9 coverage recalculation

| What | Before | After | Why |
|---|---|---|---|
| Requirement count | 167 | **167** | the amendment rewords one item; it adds and removes none |
| `BL-10` enforcement label | `not-applicable` | **`mechanical`** | the amended requirement *is* gated — `NoMigrationTests` on the .NET side, `migrations.yml` on the owning side. The old label recorded that the *EF* requirement had no application here |
| `mechanical` roll-up | 78 | **79** | `BL-10` moved in |
| `not-applicable` roll-up | 2 | **1** | `BL-38` only |
| Semantic verdict `conflicting` | 2 (`BL-10`, `BL-38`) | **1** (`BL-38`) | CF-1 closed |
| New semantic verdict `amended by explicit human decision` | — | **1** (`BL-10`) | so no requirement silently changes category |
| Traceability | `BL-10` → `20-dotnet.md` | `BL-10` → `20-dotnet.md` §20.4 + `50-database.md` §50.7 | unchanged ID, wider destination |

No requirement disappeared. `BL-10` remains a first-class row in the §3.7 applicability matrix, with
its original ID, and remains traceable from a rule file — both asserted mechanically
(`.claude/hooks/test_guards.py`).

## 6. Remaining human decisions — none resolved in this phase

Each of the following was left **exactly as Phase 9 recorded it**. No solution was chosen, no
configuration changed, no file edited to make one true.

| ID | Decision | Status after Phase 10 | Why untouched |
|---|---|---|---|
| **UD-1 / B-4** | TypeScript / Angular / Electron baseline: principles-only, a supplied TS baseline, or deliberately ungoverned | **OPEN** | No human decision supplied. `22-web-typescript.md` still states `TYPESCRIPT/ANGULAR/ELECTRON-SPECIFIC BASELINE NOT DEFINED`; the ESLint/tsconfig/Electron gates remain recorded as `NOT BASELINE AUTHORITY` and are **not weakened** |
| **UD-2** | `CA2007` / `DN-8`: accept the relaxation by ADR, or restore `severity = error` | **OPEN** | Outside this phase's authorization. `dotnet/.editorconfig` **not modified**. **DV-1** stays visible in `20-dotnet.md` DN-8 and coverage §8 |
| **UD-4** | The truncated `BL-08` offset/limit requirement | **OPEN** | The text is unrecoverable from any authoritative source; reconstructing it would be invention. **Not silently edited** — see §8 |
| **UD-5** | Whether to add `T20` to ruff `select`, making `PY-4` mechanical | **OPEN** | A configuration change, outside the one approved decision. Neither `ragcore/pyproject.toml` nor `integrations/pyproject.toml` was modified. **The `print` ban remains binding regardless**, as `21-python.md` PY-4 states |
| **UD-6** | `BL-38` vs `BL-39` build mode | **OPEN** | No decision supplied. Dockerfile **not modified**; baseline wording **not altered**. See §7 |
| **UD-7** | Whether and in what order to close **EG-1…EG-8** | **OPEN** | No analyzer, hook or CI control was added. Enforcement-gap status is **informational** until separately authorized |
| **OQ-5** | Whether A3's inline ADR-001…ADR-012 are authoritative as part of an authoritative document | **OPEN** | Carried forward unchanged. The two ADR numbering spaces are still never conflated |

## 7. Remaining conflicts

### CF-2 — `BL-38` SDK container publish vs `BL-39` chiseled base image — **OPEN**

Both are items of the **same** authoritative source, which is what makes this a conflict rather than
a deviation.

| | |
|---|---|
| **`BL-38`** | *"Build mode: .NET SDK container publish."* |
| **`BL-39`** | Production images use `mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled`, built **multi-stage** (SDK image builds, chiseled runtime image runs), digest-pinned, non-root UID 1654, shell-less |
| **The exact contradiction** | `dotnet publish /t:PublishContainer` builds an image from an **SDK-resolved base**. Microsoft **publishes no chiseled SDK image**. Therefore the literal SDK-publish path of `BL-38` cannot produce the chiseled runtime image `BL-39` mandates. `BL-39`'s own text concedes this by describing a *multi-stage* build — while simultaneously attributing that build to "the D13.3 SDK-publish path", which is the very mechanism that cannot reach a chiseled base. The source is self-contradictory within one item |
| **What the repository does** | Satisfies `BL-39` via a hand-written multi-stage `build/docker/dotnet.Dockerfile`, which states the reason inline and sets explicitly the hardening properties `BL-38` would have set by construction. Recorded as deviation **DV-11** |
| **Not resolved here** | Neither option was chosen. The Dockerfile was **not modified**; neither item's wording was **altered** |
| **Human decision required** | **UD-6** — confirm that `BL-39` supersedes `BL-38`, or restate `BL-38` as *"SDK-publish semantics realized through a multi-stage Dockerfile"*, or establish that `BL-38` describes a different artifact |

> Unlike CF-1, CF-2 **cannot** be closed by confirming an existing authority, because both sides are
> the same authority. It needs a human to say which item governs.

### 7.1 Second-authority audit — discovery pass

After closing CF-1, a focused pass looked for requirements where the explicit baseline block, the
architecture documents, and a mandatory `.claude/rules/` governance rule do not agree. **This was a
discovery pass. Nothing found was resolved, and no policy was changed.**

#### F-1 — the .NET deployable is read-only, while the baseline block assigns it write-path concerns

**Classification: architecture conformance finding (implementation deviation), *not* a source
conflict.**

| | |
|---|---|
| **Baseline block says** | `BL-11` optimistic concurrency on write, `BL-12` Serializable on invariant transactions, `BL-13` soft-delete + audit columns, `BL-29` an inbound idempotency-key filter + Postgres store, `BL-33` a transactional outbox — all scoped `.NET / C#` in the Phase 9 matrix, and all of them **write-path** concerns |
| **A2 says** | §7's container table assigns the .NET containers ownership of authoritative records — *"Approvals Service (.NET) … owns the authoritative approval and consent records"*, *"Tenant & Configuration (.NET) … tenant registry and mapping, tenant status and lifecycle"*, *"Integrations — M365/AD (.NET) … reads and governed writes"* |
| **The implementation says** | The .NET deployable is **read-only**. `dotnet/src/Synthia.Persistence/SynthiaReadContext.cs` throws from `SaveChanges`/`SaveChangesAsync`; `NoWriteEndpointTests` walks the built routing table and fails on any `POST`/`PUT`/`PATCH`/`DELETE`. The outbox and idempotency tables named as `BL-29`/`BL-33` evidence are **RagCore** revisions (`0014_outbox_message.py`, `0015_idempotency_record.py`) |
| **Why it is not a source conflict** | The baseline block and A2 **agree** with each other. The outlier is the implementation — and implementation is *never* authority (`00-authority.md` §00.4). There is also **no mandatory `.claude/rules/` rule** asserting the read-only property; it rests on implementation evidence and on `docs/adr/0002` (Accepted), which §70.1 makes history, not authority |
| **Handling** | Recorded, not reconciled (`60-architecture-gates.md` §60.4). The architecture document was **not** modified, the application code was **not** modified, and no side was declared correct |
| **Human decision required** | Whether A2 §7's role assignment is met by the current read-only split, or whether one side should change. If A2 changes, that is an ADR under `70-adr.md` §70.2 A(5)/(7) |

#### D-4 — five `.NET / C#`-scoped baseline items are evidenced only by RagCore artifacts

**Classification: editorial / scoping defect in the Phase 9 record.**

`BL-29` and `BL-33` are recorded in `20-dotnet.md` §20.8 with enforcement evidence that is entirely
RagCore (`ragcore/migrations/versions/0015_idempotency_record.py`,
`ragcore/migrations/versions/0014_outbox_message.py`). `BL-11`, `BL-12` and `BL-13` are scoped
`.NET / C#` but describe persistence-write semantics that the read-only .NET deployable cannot
exercise.

The recorded **scope** of these items therefore does not match their recorded **evidence**.

**Not repaired here.** Re-scoping them would change which stack the requirements bind, which is a
baseline change under `70-adr.md` §70.2 B(6) — not an editorial fix Claude may make on its own
initiative. Recorded for a human editorial decision.

#### Candidates examined and classified `no conflict`

| Examined | Verdict |
|---|---|
| `BL-01` modular monolith vs A2's separate RagCore / Integrations deployables | **No conflict** — `20-dotnet.md` §20.2 already scopes `BL-01` to the .NET deployable and defers topology to A2 |
| `BL-09` EF Core for data access vs Alembic owning schema | **No conflict** — already recorded as a deliberate split with a drift deviation (`50-database.md` §50.7) |
| `BL-29` idempotency vs ADR-011 signed idempotent execution in the graph | **No conflict** — `20-dotnet.md` §20.8 already names them as distinct subjects with distinct governance |
| `BL-34` Azure Service Bus vs A2 topology ownership | **No conflict** — `80-security-ops.md` §80.5 defers topology to A2 |
| Outbox and idempotency tables absent from A2 §8.1's enumeration of what Azure Postgres holds | **Low-confidence conformance candidate, not raised as a finding** — A2 §8.1 reads as a purpose summary rather than an exhaustive table inventory. Noted so a later conformance phase can settle it |

## 8. Remaining editorial defects

| ID | Defect | Status | Action taken |
|---|---|---|---|
| **D-1** | `dotnet.yaml#P-DN-S4` declares `realizes: lang/dotnet#DN19`, but `DN19` is the `goto` rule; `EnforceCodeStyleInBuild` realizes `DN-28`/`DN-29` | **OPEN** | **`dotnet.yaml` not modified** — source-pack correction was not authorized in this phase. The defect stays documented in `20-dotnet.md` §20.1 and coverage §9.2. No coverage impact: `DN-19` and `DN-28`/`DN-29` are migrated in full and independently |
| **D-2** | `BL-08`'s offset/limit sentence is truncated and runs into the next heading: *"Offset/limitOutbound resilience pipeline"* | **OPEN** | **Not reconstructed and not silently edited.** The authoritative baseline input is malformed at this point and remains so. Every legible clause of `BL-08` is migrated in full to `20-dotnet.md` §20.3. Decision **UD-4** |
| **D-3** | `dotnet_lang.yaml:307` — `DN21`'s `text:` scalar is unquoted and begins `Every #pragma warning disable …`, so a YAML parser truncates it at `#` to the single word `"Every"` | **OPEN as a source defect; re-verified as no coverage loss** | **`dotnet_lang.yaml` not modified.** Re-verified this phase against the raw source record captured in Phase 9: `20-dotnet.md` DN-21 carries the intended requirement in full — suppressions scoped and justified, `#pragma warning restore` or a non-empty `SuppressMessage` `Justification`, and no file- or project-wide blanket disables. Mechanically asserted by `test_guards.py` (*"DN21 states the suppression requirement itself"*, *"DN21 is not represented only as an ADR trigger"*) |
| **D-4** | Five `.NET / C#`-scoped items evidenced only by RagCore artifacts | **NEW, OPEN** | Recorded in §7.1. Not repaired |

## 9. Remaining enforcement gaps

**EG-1 … EG-8 are all open and all informational.** No analyzer, hook, CI step or structural check
was added to close any of them (Phase 10 brief §4 UD-7, Phase 9 brief §24).

| ID | Gap | Affects |
|---|---|---|
| **EG-1** | No commit-message check, no release/versioning tooling | `C-1`, `C-2` |
| **EG-2** | `BannedApiAnalyzers` absent; no `BannedSymbols.txt` | `DN-13`, `DN-14`, C# credential literals |
| **EG-3** | `Microsoft.VisualStudio.Threading.Analyzers` not referenced | `DN-5` |
| **EG-4** | No custom Roslyn/structural check for `goto` | `DN-19` |
| **EG-5** | No analyzer requiring a non-empty `SuppressMessage` justification | `DN-21` |
| **EG-6** | No Python dependency-vulnerability audit step | `80-security-ops.md` §80.4 |
| **EG-7** | No lint/architecture check for graph-navigation call chains | `principles#P12` |
| **EG-8** | No analyzer/lint warning-count baseline ratchet | `principles#P22` |

A rule whose enforcement is a gap **is still binding**. The gap is recorded, never an exemption
(`00-authority.md` §00.4).

## 10. Governance test results

Run from the worktree, on the amended tree.

```text
python .claude/hooks/test_guards.py    ->  486/486 checks passed
```

The suite is the Phase 8 worktree-aware guard suite, extended in Phase 9 with the baseline
traceability, coverage and dropped-rule checks. It covers, among others:

- all governance hook tests, including the Phase 8 worktree-aware enforcement paths (H2/H3/H5);
- **baseline traceability** — every one of the 115 keyed YAML IDs, the 13 unkeyed row IDs and the
  39 `BL-*` IDs appears in the coverage record **and** in at least one rule file;
- **baseline coverage** — 167 accounted for; one matrix row per requirement; no duplicate row;
  every row carries an enforcement label; the §5.2 roll-up matches the matrix **count for count**;
- **dropped-rule checks** — `C-1`…`C-5` present exactly once each, with their actual grammar;
- the **invented-TypeScript-baseline negative test** — the `NOT DEFINED` marker, the
  `NOT BASELINE AUTHORITY` marker and the `HUMAN DECISION REQUIRED` marker must all still be present;
- no `BL-*` ID written back into a source YAML pack;
- every `.claude/...` path referenced by a rule or by `CLAUDE.md` resolves;
- the pre-existing governance rules (30, 50, 70, 90) were not rewritten to fit the baseline.

### 10.1 Mutation / plant tests

The suite was exercised by planting a regression, confirming the suite fails, and restoring. The
tree was verified back at `486/486` after every plant.

| Plant | Result | Caught by |
|---|---|---|
| Remove every occurrence of a `BL-*` id from the rule files | **CAUGHT** | *every baseline id is traceable from a rule file: BL-33* |
| Replace the TypeScript `NOT DEFINED` marker with an invented baseline | **CAUGHT** | *the TS/Angular/Electron gap is recorded verbatim* |
| Delete an item from the baseline input block | **CAUGHT** | *the baseline block still holds 39 items* |
| Rename `NoMigrationTests` in `20-dotnet.md` `BL-10` | **CAUGHT** | *the migration invariant is not weakened by the conflict* |
| Skew the `mechanical` enforcement roll-up by one | **CAUGHT** | *the enforcement roll-up matches the matrix for mechanical* |

> **One plant initially read as a MISS and was not.** The first traceability plant removed only the
> `### BL-33 — Outbox pattern` *heading*, leaving the id in that rule's `Source:` line — so the id
> was still traceable and the suite was right to pass. The plant was re-run removing **every**
> occurrence, and the suite failed as it should. Recorded because an ineffective mutation that
> reads as a suite gap is exactly the kind of false comfort this exercise exists to prevent.

### 10.2 What was deliberately not done

- **No test was deleted, skipped, `xfail`ed, loosened or narrowed** (`40-testing.md` §40.1).
- **No application code was modified to satisfy a governance check.** The only files changed are
  governance and migration records, listed in §5.
- No stack-specific gate (`.NET`, RagCore, Integrations, web, desktop, boundaries, migrations,
  contracts) was weakened or disabled.

## 11. Retirement-readiness impact

**Readiness is not declared.** Phase 10 moves one item and nothing else.

### Resolved

| Item | Status |
|---|---|
| **B-3** worktree enforcement | Resolved in Phase 8 |
| **B-1** baseline migration | Resolved in Phase 9 |
| **B-2** baseline input availability | Resolved in Phase 9 |
| **CF-1 / UD-3** migration ownership | **Resolved in Phase 10 — this document** |

### Still open

| Item | Status |
|---|---|
| **B-4 / UD-1** TypeScript / Angular / Electron governance scope | **OPEN** — blocker |
| **UD-2** `CA2007` / `DN-8` relaxation | **OPEN** |
| **UD-4** malformed `BL-08` | **OPEN** |
| **UD-5** `T20` enforcement | **OPEN** |
| **UD-6 / CF-2** `BL-38` vs `BL-39` | **OPEN** |
| **UD-7** enforcement-gap closure (`EG-1`…`EG-8`) | **OPEN** |
| **OQ-5** A3 inline ADR authority | **OPEN** |
| Architecture conformance findings (`60-architecture-gates.md` §60.4, plus **F-1** in §7.1) | **OPEN** |

### Therefore

```text
SPEC KIT IS NOT RETIRED IN THIS PHASE.
```

`.specify/**`, `specs/**` and the `speckit-*` skills are **untouched**. They remain in the tree,
non-authoritative (`00-authority.md` §00.4, `CLAUDE.md` §10), pending a later retirement phase.
Blocker **B-4** alone is sufficient to keep retirement closed; **CF-2** and the open editorial
defects are further reasons.

---

## 12. What this document does not do

- It does not become authority. `.claude/rules/` is the operative baseline.
- It does not resolve **UD-1, UD-2, UD-4, UD-5, UD-6, UD-7, OQ-5**, **CF-2**, **D-1**, **D-2**,
  **D-4**, or any conformance finding.
- It does not close an enforcement gap, and it does not authorize closing one.
- It does not create or accept an ADR.
- It does not retire Spec Kit, and it does not declare retirement readiness.
