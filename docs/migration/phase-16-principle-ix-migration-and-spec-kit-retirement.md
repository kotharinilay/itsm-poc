# Phase 16 — Principle IX migration and Spec Kit retirement

**Kind: record (Diátaxis *explanation* + *reference*).** This file records what Phase 16 did and
where it stopped. It is a migration record: **it is not authority**, it authorizes nothing, and it
does not amend `.claude/rules/**`, A1, A2 or A3.

**Phase 16 deleted `.specify/**` and `specs/**`**, after — and only after — the two Principle IX
clauses they alone stated were given a surviving authoritative home. The ordering is the point and
is evidenced in §4 and §5.

---

## 1. Starting state

| Check | Result |
|---|---|
| Branch | `speckit-to-claude`; Phase 16 executed in a worktree branched from its head |
| Starting commit | `9779705710b11a450ecbf49d807bb20e558aca2b` — *Merge phase 15: final Spec Kit reconciliation and citation repointing* |
| Working tree at start | clean |
| Phase 15 merge present | **yes** — `9779705`, with `d34c79b` beneath it |
| Phase 15 status | complete except blocker **B15-1**; verdict *NOT READY FOR PHASE 16* |
| `docs/adr/0010-frontend-engineering-baseline.md` | **Accepted** |
| `docs/adr/0011-required-test-categories-baseline.md` | **Accepted** |
| `speckit-*` Claude skills | **none** — `.claude/skills/` holds `adr-author`, `db-change`, `functional-update`, `langgraph-change` |
| Current governance files | all present — `.claude/rules/00,10,20,21,22,23,24,30,40,50,60,70,80,90` |
| `.specify/**` and `specs/**` | **present** at the start of Phase 16, as required |
| Governance guards at start | `python .claude/hooks/test_guards.py` → **792/792 passed** |

> **Worktree note, recorded because it affected the run.** The isolation worktree was created from
> the repository's default base ref and therefore started at `main` (`ca97a54`), which predates
> Phase 12 — `.specify/**`, `specs/**` *and* the ten `speckit-*` skills were all present, and
> ADR-0010/0011 were absent. This was detected by the Gate 1 checks before any edit was made, and
> the worktree was reset to `9779705`. **No work was performed against the wrong base**, and the
> Gate 1 results above are from the corrected tree.

## 2. Human decision

Recorded explicitly, as a decision and not as an inference:

```text
Option A selected by repository owner:
migrate Principle IX clauses 2b and 3 into the permanent engineering baseline.
```

The repository owner stated this selection in the Phase 16 brief, resolving the choice Phase 15
§6.1 put to a human. Option B — recording that the clauses lapse with the scaffold phase — was
**not** selected and is not presented as an open alternative.

**Selecting the option and accepting the ADR are two separate events** under
`.claude/rules/70-adr.md` §70.3 and `.claude/rules/00-authority.md` §00.10. Both have now
occurred, in this order:

1. Option A selected in the Phase 16 brief. Claude wrote ADR-0012 with status `Proposed` and
   **stopped**, implementing nothing.
2. The repository owner then read the record and accepted it explicitly, in session:
   *"I accept ADR-0012 — proceed with the full migration and deletion."*

Only after event 2 was `.claude/rules/10-principles.md` §10.7 written and the deletion performed.

## 3. ADR-0012

| Field | Value |
|---|---|
| File | `docs/adr/0012-principle-ix-reference-fixtures-and-no-fabricated-success.md` |
| Title | *Migrate Principle IX clauses 2b and 3: no fabricated success, and reference fixtures are never product* |
| Status **on disk** | **`Proposed`** — see the open item in §7.2; the H5 guard blocks Claude from editing an existing record, and the acceptance is recorded here and in the commit instead |
| Acceptance status | **ACCEPTED** by the repository owner, explicitly and in session, after the record was written |
| Class (`70-adr.md` §70.4) | **Engineering Baseline** — §70.2 B(6), a change to a mandatory engineering convention |
| Structure | MADR; validated by `.claude/hooks/adr_structure_guard.py` (H5), exit 0 |
| Indexed | yes — `docs/adr/README.md`, row `0012`, shown as `Proposed` |

**Exact decision.** Principle IX clauses 2b and 3 are adopted into the permanent engineering
baseline as two repository-wide rules, **`H-1`** and **`H-2`**, appended to
`.claude/rules/10-principles.md` as a new **§10.7 — Implementation honesty and reference
fixtures**.

**Location of the migrated rule text:** `.claude/rules/10-principles.md` §10.7.

```text
WRITTEN. .claude/rules/10-principles.md 10.7 — H-1 and H-2.
Appended after 10.6 so every existing section number stays stable.
```

Placement was chosen, not defaulted. Four alternatives were considered and rejected in the record:
`21-python.md` (stack-scoping a requirement that is not about Python, and `CLAUDE.md` §4 forbids
carrying it back by analogy), a new `11-scaffold-honesty.md` file (two rules do not warrant a tenth
repository-wide file), `90-functional-knowledge.md` (§90.11 says it authorizes nothing about
implementation), and letting the clauses lapse.

The rule text as drafted in the ADR cites **no** `.specify/**` or `specs/**` path as its authority.
Provenance is carried in the ADR and in this record, which is where `70-adr.md` §70.1 puts it.

## 4. Principle IX migration

### 4.1 Clause 2b

**Source meaning** (`.specify/memory/constitution.md` §IX, verbatim):

> A fallback MUST be explicit and visible; silently degrading, stubbing a success, or returning a
> plausible-looking fabricated result is prohibited.

**Surviving authority:** `.claude/rules/10-principles.md` §10.7 **`H-1` — No fabricated,
stubbed or silently degraded success.** Repository-wide, every stack.

Three prohibitions preserved one for one: silent degradation; a stubbed success; a fabricated,
simulated or plausible-looking result presented as real execution — explicitly including a
model-produced value returned as though it were retrieved, computed or externally confirmed.

**Not broadened.** `H-1` states in its own text that a declared fallback, a cached value served as
a cached value, a labelled partial result, a documented default and a retry are all legitimate. The
rule is the honesty of the report, not the ambition of the behaviour.

**Not duplicated.** Clause 2a — the fallback to manual resolution or escalation — is already
carried by A3 §6.2's outcome vocabulary (`escalated`, `escalation_reason`) and by P-11 and P-30, so
`H-1` states only the half that had no home. `00-authority.md` §00.5 forbids restating an owned
requirement, and the drafted text does not.

### 4.2 Clause 3

**Source meaning** (`.specify/memory/constitution.md` §IX, verbatim):

> **Reference fixtures are permitted, and are never product.** Inert reference operations may exist
> so that governance, consent and approval paths are demonstrable before any use case is defined.
> Each MUST be labelled a scaffold fixture, produce no real external effect, be excluded from
> production configuration, and MUST NEVER be counted as or allowed to become one of the twelve use
> cases.

Restated in `specs/001-platform-scaffold/spec.md` as `FR-SCOPE-004` (one fixture per treatment),
`FR-SCOPE-005` (inert), `FR-SCOPE-006` (labelled, not presented as product, excluded from
production configuration) and `FR-SCOPE-007` (never one of UC-01…UC-12).

**Surviving authority:** `.claude/rules/10-principles.md` §10.7 **`H-2` — Reference
fixtures are labelled, inert, production-excluded, and never product.** Repository-wide.

Four numbered properties, mapped one for one onto the source:

| `H-2` property | Source clause |
|---|---|
| 1. labelled a reference fixture, recognisably and without a catalogue lookup | "MUST be labelled a scaffold fixture" |
| 2. inert — no real external effect, no account/device/record modified, no claimed confirmation | "produce no real external effect" + `FR-SCOPE-005` |
| 3. excluded from production configuration, **enforced rather than documented** | "be excluded from production configuration" |
| 4. never presented as product capability, never counted as / substituted for / allowed to become a real capability | "MUST NEVER be counted as or allowed to become one of the twelve use cases" + `FR-SCOPE-006` |

One deliberate generalisation, stated so it is visible: the source says *"one of the twelve use
cases"*, which is scaffold-phase vocabulary. `H-2` says *"a real defined capability"*. This removes
a reference to a numbering that the retired documents own, and **strengthens nothing and weakens
nothing** — UC-01…UC-12 are a subset of "a real defined capability". The migration cannot preserve
"the twelve use cases" as a term without importing an obligation from a deleted document.

### 4.3 The test enforcing clause 3

`ragcore/tests/governance/test_fixtures_excluded.py`, five classes, every property asserted:

| `H-2` property | Asserted by |
|---|---|
| 1. labelled | `TestEveryFixtureIsLabelled` — flag, prefix, and that the two never disagree |
| 2. inert | `TestEveryFixtureIsInert` — no external system, no verification tool, no claimed confirmation, disclosed command set, stable content hash |
| 3. production-excluded | `TestExcludedFromProductionConfiguration` — a **raising** loader, available in the three non-production environments, and the environment literal read from `Settings` so the two cannot drift |
| 4. never a use case | `TestAFixtureIsNeverAUseCase` — no `uc-`/`uc_` identifier, the prefix check discriminates, and exactly one module declares fixtures |
| — the adjacent rule it protects | `TestTheExclusionDoesNotBecomeAnEnvironmentBranch` — no governance module reads the environment, and `fixtures.py` reads it only to refuse |

**State after Phase 16: intact, unmodified, passing.** Not deleted, not skipped, not `xfail`ed, no
assertion loosened, no fixture narrowed, no case removed.

### 4.4 Confirmation that no requirement was weakened

| Requirement | Preserved? |
|---|---|
| no silent degradation | yes — `H-1`, bullet 1 |
| no success claim for a capability that was not executed | yes — `H-1`, bullet 2 |
| no fabricated / simulated / plausible result presented as real | yes — `H-1`, bullet 3, extended explicitly to model output |
| fixtures clearly labelled | yes — `H-2`.1 |
| fixtures inert | yes — `H-2`.2 |
| fixtures cannot affect production execution | yes — `H-2`.3, with "enforced rather than documented" kept as normative text |
| fixtures excluded from production configuration | yes — `H-2`.3 |
| fixtures never a real use case | yes — `H-2`.4 |
| legitimate fallback still permitted | yes — stated explicitly in `H-1`, so the rule cannot be read as banning fallback |

Nothing in either rule is conditioned on the scaffold phase, on an environment, or on a document
that Phase 16 deletes.

### 4.5 M-19 — a manifest omission Phase 15 did not record

Found during Gate 2 and recorded rather than absorbed:

```text
ragcore/src/ragcore/governance/fixtures.py:198
    raises ReferenceFixtureInProductionError with a message citing "spec FR-SCOPE-006"

ragcore/tests/governance/test_fixtures_excluded.py::test_the_refusal_says_why
    asserts   "FR-SCOPE-006" in str(raised.value)
```

Both name a spec id that lives only in `specs/001-platform-scaffold/spec.md`, which is inside the
deletion set. Phase 15 §11 classifies `ragcore/**` runtime strings under M-14 but **did not list
this pair**, and its class-E ruling that `docs/adr/**` and test files "create no current
instruction" does not reach a runtime message a test asserts on.

**Disposition: completed.** The citation was repointed to `10-principles.md` `H-2` in the message
and the assertion together. ADR-0012 states this in its Consequences, which `70-adr.md` §70.8
requires before a test may be touched at all. It is a repointing of the authority named, **not a
relaxation**: the test still asserts that the refusal explains itself by citing its authority, with
the same strength, and the authority it names now still exists.

```diff
- "configuration (spec FR-SCOPE-006). They are not product capability ..."
+ "configuration (10-principles.md H-2). They are not product capability ..."

-         assert "FR-SCOPE-006" in str(raised.value)
+         assert "H-2" in str(raised.value)
```

### 4.6 M-20 — a second omission, in the ADR index

`docs/adr/README.md` §*Writing a new record* issued **live instructions** citing
`Synthia-Platform-Specification.md`, "constitution Principle V", "Principle VI" and "the
constitution" as the triggers for a new record. Phase 15 counted `docs/adr/**` as 69 class-E
occurrences on the ground that "none creates a current instruction"; that ruling is **wrong for
this section**, which is the only prose in the tree telling an author when an ADR is required, and
which contradicted `70-adr.md` §70.2 while pointing at documents being deleted.

**Disposition: corrected in Phase 16**, because `70-adr.md` §70.6 requires the index to be updated
in the same change as a new record, and because the repoint is true both before and after deletion.
The section now defers to `70-adr.md` §70.2 as authority and names P-8, ADR-0007 and
`24-electron.md` for the four cases it keeps. No trigger was added or removed.


## 5. Deletion manifest — M-01 … M-21

`.specify/**` and `specs/**` were deleted **after** §10.7 existed, in a single recursive removal
taking out **44 tracked files**.

| # | Item | **Phase 16 status** |
|---|---|---|
| **M-01** | `.dockerignore:86` — `specs/` | **completed** — line removed |
| **M-02** | `CLAUDE.md` §10 — "pending a later retirement phase" | **completed** — rewritten as completed history; §2 and §4 also updated for §10.7, and the stale B13-3 bullet corrected |
| **M-03** | `README.md:40–41` | **completed** — rewritten; now names all three migrations (0010, 0011, 0012) that preceded deletion |
| **M-04** | `.claude/rules/00-authority.md` §00.4 | **completed** — rewritten as completed history; **the non-authority statement is unchanged and stays**, strengthened with "nothing may cite them from git history either" |
| **M-05** | `.claude/rules/70-adr.md:19` — non-authority list | **completed** — deleted paths dropped from the list; the constitution's exclusion remains |
| **M-06** | `.claude/rules/90-functional-knowledge.md:53` | **completed** — repointed, keeping the trees named as non-evidence even from history |
| **M-07** | `.claude/skills/adr-author/SKILL.md:100` | **completed** — deleted paths dropped |
| **M-08** | `.claude/rules/22-web-typescript.md:53,59` | **preserved intentionally**, annotated "deleted from the tree in Phase 16; git history only" |
| **M-09** | `.claude/rules/40-testing.md:171` | **preserved intentionally**, annotated the same way |
| **M-10** | `.claude/rules/23-angular.md:102` (**FE-AMB-3**) | **preserved intentionally**, and strengthened: the section now states that it **is the rule's sole prose authority**, which is why it was migrated before the tree went |
| **M-11** | `.serena/memories/core.md:16,38` | **completed** — both lines updated; now also names the three migration targets |
| **M-12** | `.claude/hooks/test_guards.py:842–906` | **preserved unchanged** — the `speckit`/`.specify` regexes assert *absence* and are still correct and necessary. Verified passing after deletion |
| **M-13** | `apps/desktop/src/main/endpoint-execution-boundary.ts:59` | **repointed** to "ADR-0004 and ADR-0006". No desktop test asserts the removed text; checked before editing |
| **M-14** | six `ragcore/workers/*.py` + `integrations/workers/command_consumer.py` | **repointed** — the deleted-path pointer dropped from each `NotImplementedError`, message substance kept. These refusals are `H-1` behaviour and remain refusals |
| **M-15** | `ragcore/src/ragcore/api/customer/sample_flows.py:119` + `build/contracts/ragcore/customer.v1.openapi.json:435` | **regenerated** — docstring fixed at source, then the repository's own emitter run with `--out ../build/contracts/ragcore`. **The JSON was never hand-edited**; exactly one contract file changed |
| **M-16** | `build/infra/apim/apis.json:8`, `build/infra/messaging/queues.json:5` | **repointed** — `queues.json` now points at `build/contracts/**`; `apis.json` records that the prose source was deleted |
| **M-17** | `docs/current-implementation/file-map.md:260` | **completed** — row struck through and marked deleted in Phase 16 |
| **M-18** | `docs/architecture/integrations-service-delta.md` | **preserved intentionally** — a dated reconciliation record, non-authoritative, left as written |
| **M-19** | `fixtures.py` refusal + `test_the_refusal_says_why` (§4.5) | **completed** — repointed to `H-2`, message and assertion together |
| **M-20** | `docs/adr/README.md` §*Writing a new record* (§4.6) | **completed** — defers to `70-adr.md` §70.2 |
| **M-21** | **new** — six `Principle VIII` citations across `dotnet/src`, `ragcore/src`, `ragcore/migrations`, `ragcore/tests`, `integrations/tests` | **repointed**, and recorded rather than absorbed (§5.1) |

Summary: **16 completed or repointed, 5 preserved intentionally, 2 trees deleted, 1 contract
regenerated. Nothing left blocked.**

### 5.1 M-21 — a third omission from the Phase 15 manifest

Phase 15's mechanical pass matched the string `constitution`, so six citations reading **`Principle
VIII`** with no `constitution` prefix were never caught, and its §4.4 ambiguous list does not
contain them. After deletion each would have pointed at nothing.

They were repointed using **Phase 15's own §4.1 mapping table**, not a fresh judgement:

| Site | Requirement invoked | Repointed to |
|---|---|---|
| `dotnet/src/Synthia.Observability/SynthiaTelemetry.cs:42` | baggage allowlist | the `20-dotnet.md` BL-24 citation already on the line above; the redundant "(Principle VIII)" dropped |
| `ragcore/src/ragcore/governance/fixtures.py:118` | no claimed confirmation | **ADR-0004** |
| `ragcore/src/ragcore/persistence/models.py:878`, `ragcore/migrations/versions/0022_integration_job.py:20`, `integrations/tests/unit/test_consumer_and_authority.py:203` | hard-failure set | **`80-security-ops.md` §80.3** |
| `ragcore/tests/security/test_hard_failures.py:14,510` | hard-failure set + the failing-when-removed obligation | **`80-security-ops.md` §80.3** and **`40-testing.md` §40.10** |

This is the one place Phase 16 went beyond the Phase 15 manifest. It is reported here rather than
folded in silently, and it was not a licence to look for other work: nothing else was touched.

Separately, the **`Principle IX`** citations Phase 15 held open as B13-3 — sixteen live sites
across `ragcore/**`, `integrations/**` and `dotnet/**` — were repointed to `H-1` or `H-2` per site,
chosen from the requirement each sentence actually invokes. The `UC-01..UC-12` requirement phrasing
in six source files became "a real defined capability", matching `H-2`'s generalisation (§4.2).

## 6. Repository search results — post-deletion

| Term | Before | After |
|---|---|---|
| `speckit` | 157 occurrences in 31 files | **103 in 15 files** — all historical or guard |
| `constitution` | 573 in 70 files | reduced by the 178 occurrences that lived inside the deleted trees |
| `Principle IX` | 34 in 25 files | **3** outside `docs/migration/**` and `docs/adr/**`, all correct |
| `Synthia-Platform-Specification` | present | present, and named non-authority by `00-authority.md` §00.2 |

Every surviving occurrence, classified:

| Class | Where | Verdict |
|---|---|---|
| **current governance — active mechanism** | `.claude/hooks/test_guards.py` lines 879–906 (`speckit`/`.specify` regexes); line 1501 (asserts the Phase 14 record invents no Principle IX id) | **correct and necessary.** They assert *absence*, so deletion makes them more meaningful, not less. Verified passing |
| **current governance — past tense** | `CLAUDE.md` §10, `README.md`, `.claude/rules/00-authority.md` §00.4, `90-functional-knowledge.md`, `.serena/memories/core.md`, `docs/current-implementation/file-map.md` | **accurate** — each states the trees were deleted in Phase 16 and may not be cited |
| **migration provenance** | `22-web-typescript.md`, `23-angular.md`, `40-testing.md`, `10-principles.md` §10.7 | **retained deliberately** under ADR-0010 / 0011 / 0012; each says in the same breath that the source was migration input and not authority, and now also that it is deleted |
| **historical** | `docs/migration/**` (seven phase records), `docs/adr/0001–0012`, `docs/architecture/integrations-service-delta.md` | **retained** — history is the point |
| **stale / broken** | — | **none** |

```text
zero live execution dependency on Spec Kit        confirmed
zero current authority dependency on Spec Kit     confirmed
zero broken current references to deleted files   confirmed
historical provenance retained where intended     confirmed
```

No tracked `.specify` or `specs` directory remains; the removal is staged as 44 deletions with no
untracked residue left behind.

## 7. Validation

Every gate was run from the Phase 16 worktree, after the deletion.

| Gate | Command | Result |
|---|---|---|
| Governance guards | `python .claude/hooks/test_guards.py` | **793/793 checks passed** |
| Boundaries | `bash build/scripts/check-boundaries.sh` | **4/4 passed** |
| Edge path | `bash build/scripts/check-edge-path.sh` | **Edge path intact** |
| RagCore lint | `uv run ruff check .` | **All checks passed** |
| RagCore format | `uv run ruff format --check .` | **248 files already formatted** |
| RagCore types | `uv run mypy` | **no issues in 219 source files** |
| RagCore tests | `uv run pytest -q` | **1301 passed** |
| Contract staleness | `uv run pytest -q tests/contracts/test_openapi_contracts.py` | **54 passed**, including `test_the_committed_document_matches_the_generated_one` |
| Integrations lint / format / types | `ruff check`, `ruff format --check`, `mypy` | **passed; 68 files formatted; no issues in 67 source files** |
| Integrations tests | `uv run pytest -q` | **155 passed** |
| .NET build | `dotnet build` | **succeeded — 0 Warning(s), 0 Error(s)** (`TreatWarningsAsErrors` on) |
| .NET tests | `dotnet test` | **all passed** — ArchitectureTests 88, ContractTests 51, AuthorizationTests 21, TenantIsolationTests 11, SharedKernel 69, six module suites 1 each |
| .NET format | `dotnet format --verify-no-changes` | **fails — DV-14**, and **every error is `ENDOFLINE`**; no style error of any other kind |
| Desktop types / lint | `npm run typecheck`, `npm run lint` | **exit 0** |
| Desktop tests | `npx vitest run` | **178 passed, 4 files** |
| Web libs / types | `npm run build:libs`, `npx tsc -b` | **exit 0** |
| Web lint / format | `npx eslint .`, `npx prettier --check .` | **exit 0; all files use Prettier style** |
| Web tests | `npm test` | **9 passed, 3 suites** — architecture suite green |

Node dependencies were installed with `npm ci` in `apps/desktop` and `apps/web` first; the
worktree was a fresh checkout with no `node_modules`.

### 7.1 No test was weakened

Counts are identical to Phase 15 in every suite: RagCore **1301**, Integrations **155**, Desktop
**178**, .NET ArchitectureTests **88** / ContractTests **51**, web architecture **9**.

```text
No test deleted.  No skip.  No xfail.  No loosened assertion.
No narrowed fixture.  No removed case.  No disabled suite or job.
```

`ragcore/tests/governance/test_fixtures_excluded.py` — the suite that made B15-1 a blocker — is
**intact**: five classes, every assertion present, all passing. Its one changed line swaps the
authority the refusal cites (`FR-SCOPE-006` → `H-2`) and is the repointing ADR-0012 declared in
advance (§4.5).

The guard suite moved 792 → **793** because the ADR index check loops once per indexed record and
there is now one more record. Eight ADR-history assertions were updated to the new true facts
(eleven records → twelve, next number `0012` → `0013`, synthetic H5 fixtures moved off the
now-taken `0012` onto `0013`). **No assertion was removed, loosened or skipped** — every check that
existed before exists after, asserting the same property.

### 7.2 Open item — ADR-0012's status field still reads `Proposed`

**The acceptance is real; the file does not yet say so.** `.claude/hooks/adr_structure_guard.py`
(H5) blocks *every* write to a record already on disk, deterministically and with no override
flag — that is its design, and routing around a governance guard is not an option
(`00-authority.md` §00.8). Claude stated the human direction, as the guard's own message invites,
and the tool call was still refused.

So the tree currently carries:

```text
docs/adr/0012-….md      - **Status:** Proposed
docs/adr/README.md      row 0012 shown as Proposed
```

These two **agree**, which is why the guard suite's "index status matches the record" check passes.
They are consistent and understated, not contradictory.

**The acceptance is recorded in three places that are not the status field**: this section, §2 of
this record, and the commit message. Flipping the field is a two-line human edit, and until it is
made, a reader who trusts only the status field will under-read ADR-0012 rather than over-read it —
the safe direction for that error.

## 8. Existing deviations — carried forward, not resolved

| Id | State after Phase 16 |
|---|---|
| **DV-13** — `apps/web` `npx tsc -b` fails on 2 pre-existing `readHostedConfig` errors | **OPEN, and NOT REPRODUCED again.** `npx tsc -b` exits 0 here after `npm run build:libs`, as in Phase 15. **Not claimed resolved**: it needs a deliberate re-verification against the Phase 13/14 conditions, which this phase did not perform. **Not repaired** (`00-authority.md` §00.7) |
| **DV-14** — `dotnet format --verify-no-changes` fails on Windows CRLF | **OPEN, verified still failing, every error `ENDOFLINE`.** CI runs on Linux. **Not repaired** |
| **EG-10** — nothing binds a diff to the test categories `40-testing.md` §40.9 says it owes | **OPEN, unchanged.** ADR-0012 does not authorize building such a mechanism |
| **The eight ambiguous cross-stack citations** (Phase 15 §4.4) | **OPEN, unchanged, still explicitly classified.** `integrations/**` §Middleware order ×3, §Validation and errors, §Health, `egress/http.py`; `ragcore/**` `repositories.py`. Each cites a requirement stated only in the **.NET** baseline with no Python counterpart. **ADR-0012 explicitly does not address them** (its §Unresolved), and Phase 16 did not touch them. Closing them is a separate baseline decision under `70-adr.md` §70.2 B(6) |
| **DV-11 / BL-38** — the .NET image is built from a hand-written Dockerfile rather than SDK container publish | **OPEN, unchanged**, untouched |
| **DV-8, DV-9, DV-10** — Ruff `quote-style` unwritten, the migrations `per-file-ignores`, `T20` unselected | **OPEN, unchanged**, untouched |

No deviation was silently repaired, and none was rewritten to match the implementation.

### 8.1 A new enforcement gap, recorded

**EG-11.** `H-1` is **procedurally enforced**. No mechanism detects a stubbed success, a silent
degradation or a fabricated result, and ADR-0012 explicitly does not authorize building one.
Recorded as a gap, **not** as a reduction in the requirement (`40-testing.md` §40.7).

`H-2` is mechanically enforced for the fixtures that exist today, and **only** for those: a fixture
introduced on the .NET or frontend stacks would owe the same four properties with no check to catch
it. Recorded in `H-2`'s own enforcement line and in ADR-0012 §Unresolved.

## 9. Final verdict

```text
READY FOR FINAL RETIREMENT
```

Every condition is met:

- **B15-1 is discharged.** Principle IX clauses 2b and 3 have a surviving authoritative home —
  `.claude/rules/10-principles.md` §10.7, `H-1` and `H-2` — that cites no deleted path.
- **The ordering held.** The rule text was written *before* the deletion, and the deletion was
  performed *after* the ADR was accepted by a human. Claude wrote the record as `Proposed`,
  stopped, and resumed only on explicit acceptance.
- **`test_fixtures_excluded.py` is intact and now enforces a stated rule.** Before Phase 16 it
  enforced a requirement that, after deletion, nothing would have stated.
- **The Spec Kit trees are gone**, with no live execution dependency, no current authority
  dependency, and no broken current reference.
- **Every suite passes at its Phase 15 count or above, and no test was weakened.**
- **Every prior deviation is carried forward**, and the two new findings (M-19, M-21) plus the new
  gap (EG-11) are recorded rather than absorbed.

One item is open and is a human two-line edit, not a governance question: **ADR-0012's status field
reads `Proposed` though the decision was accepted** (§7.2). The guard that prevents Claude editing
an existing record is working as designed.

The repository state is now explainable entirely through:

```text
A1 / A2 / A3
.claude/rules/**
.claude/skills/**
docs/adr/**
docs/functional/implemented.md
docs/migration/**
```

with the retired Spec Kit trees removed and no current governance dependency on them.

## 10. Numbering — a deliberate departure from the brief's literal text

The brief instructed that `CLAUDE.md` §8 change from `(next: **0010**)` to `(next: **0012**)`. It
reads **`(next: 0013)`**.

The brief's value was correct when written and went stale the moment ADR-0012 was created in this
same phase. `70-adr.md` §70.6 states a number is never reused **including the number of a
superseded or deprecated record**; a record consumes its number when it is written. Writing `0012`
into the "next" field while the `0012` record exists would reproduce exactly the defect Gate 5
exists to fix, and would point the next author at a collision H5 would reject.

The same correction was applied to **`.claude/rules/70-adr.md` §70.6**, which read *"Existing
sequence: `0001` … `0009`. The next new record is **`0010`**"*. The brief asked only about
`CLAUDE.md` but directed a check for other governance references making the same claim; this was
the one, and it is authority where `CLAUDE.md` is a map.

**Flagged rather than done quietly**, because it departs from an explicit instruction and from one
of the brief's own success conditions.
