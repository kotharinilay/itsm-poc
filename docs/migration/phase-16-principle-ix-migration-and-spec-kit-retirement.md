# Phase 16 — Principle IX migration and Spec Kit retirement

**Kind: record (Diátaxis *explanation* + *reference*).** This file records what Phase 16 did and
where it stopped. It is a migration record: **it is not authority**, it authorizes nothing, and it
does not amend `.claude/rules/**`, A1, A2 or A3.

**Phase 16 deleted nothing.** `.specify/**` and `specs/**` are byte-for-byte as Phase 15 left them.
The reason is stated in §9 and is a governance stop, not an incomplete task.

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

**This decision selects the option. It is not acceptance of ADR-0012.** Those are two separate
events under `.claude/rules/70-adr.md` §70.3 and `.claude/rules/00-authority.md` §00.10, and the
second has not occurred. See §9.

## 3. ADR-0012

| Field | Value |
|---|---|
| File | `docs/adr/0012-principle-ix-reference-fixtures-and-no-fabricated-success.md` |
| Title | *Migrate Principle IX clauses 2b and 3: no fabricated success, and reference fixtures are never product* |
| Status **on disk** | **`Proposed`** |
| Acceptance status | **NOT ACCEPTED.** No human has accepted it in this session |
| Class (`70-adr.md` §70.4) | **Engineering Baseline** — §70.2 B(6), a change to a mandatory engineering convention |
| Structure | MADR; validated by `.claude/hooks/adr_structure_guard.py` (H5), exit 0 |
| Indexed | yes — `docs/adr/README.md`, row `0012`, shown as `Proposed` |

**Exact decision.** Principle IX clauses 2b and 3 are adopted into the permanent engineering
baseline as two repository-wide rules, **`H-1`** and **`H-2`**, appended to
`.claude/rules/10-principles.md` as a new **§10.7 — Implementation honesty and reference
fixtures**.

**Location of the migrated rule text:** `.claude/rules/10-principles.md` §10.7.

```text
NOT YET WRITTEN. §10.7 does not exist in the tree.
70-adr.md 70.5 — "Proposed: written, not yet accepted. Nothing may be implemented on it."
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

**Surviving authority (proposed):** `.claude/rules/10-principles.md` §10.7 **`H-1` — No fabricated,
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

**Surviving authority (proposed):** `.claude/rules/10-principles.md` §10.7 **`H-2` — Reference
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

**Disposition: deferred to the post-acceptance step**, where the citation is repointed to
`10-principles.md` `H-2` in the message and the assertion together. ADR-0012 states this in its
Consequences, which `70-adr.md` §70.8 requires before a test may be touched at all. It is a
repointing of the authority named, not a relaxation: the test still asserts that the refusal
explains itself by citing its authority.

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

## 5. Deletion manifest — M-01 … M-20

**Nothing in this table was executed.** Gate 6 conditions the manifest on the Principle IX
requirements having a surviving authoritative home, and §10.7 is unwritten pending acceptance
(§9). Statuses below are therefore the honest ones; `blocked` means blocked on that acceptance, not
unexamined.

| # | Item | Phase 15 action | **Phase 16 status** |
|---|---|---|---|
| **M-01** | `.dockerignore:86` — `specs/` | delete the line | **blocked** — the pattern is still valid while `specs/` exists; removing it now would be premature, not a cleanup |
| **M-02** | `CLAUDE.md` §10 — "pending a later retirement phase" | rewrite as completed history | **blocked** — the sentence is **true today**; rewriting it before deletion would make it false |
| **M-03** | `README.md:40–41` — "retained pending a later retirement phase" | rewrite as completed history | **blocked** — as M-02 |
| **M-04** | `.claude/rules/00-authority.md` §00.4 | rewrite as completed history, keep the non-authority statement | **blocked** — as M-02. The non-authority statement is unchanged and stays |
| **M-05** | `.claude/rules/70-adr.md:19` — non-authority list | keep or move to past tense | **blocked** — harmless either way; deferred with the set |
| **M-06** | `.claude/rules/90-functional-knowledge.md:53` | as M-05 | **blocked** |
| **M-07** | `.claude/skills/adr-author/SKILL.md:100` | as M-05 | **blocked** |
| **M-08** | `.claude/rules/22-web-typescript.md:53,59` — constitution as migration input | **keep**; note the source was deleted | **preserved intentionally** — no change needed now; the note is owed at deletion |
| **M-09** | `.claude/rules/40-testing.md:171` | as M-08 | **preserved intentionally** |
| **M-10** | `.claude/rules/23-angular.md:102` — `specs/.../plan.md` as provenance (**FE-AMB-3**) | **keep** — rule text is stated in full | **preserved intentionally** |
| **M-11** | `.serena/memories/core.md:16,38` — both trees described as retained | update to "deleted in Phase 16" | **blocked** — the description is true today |
| **M-12** | `.claude/hooks/test_guards.py:842–906` — `speckit`/`.specify` regexes | **keep unchanged** | **preserved intentionally** — verified present and passing; they assert *absence* and stay correct after deletion |
| **M-13** | `apps/desktop/src/main/endpoint-execution-boundary.ts:59` — runtime error cites `specs/.../plan.md` | repoint to ADR-0004 / ADR-0006 | **blocked** — sequenced with deletion per Gate 6 |
| **M-14** | six `ragcore/workers/*.py` + `integrations/workers/command_consumer.py` — `NotImplementedError` cites `specs/.../tasks.md` | repoint or drop the pointer | **blocked** — as M-13 |
| **M-15** | `ragcore/src/ragcore/api/customer/sample_flows.py:119` **+** `build/contracts/ragcore/customer.v1.openapi.json:435` | fix docstring, then **regenerate** | **blocked** — **not regenerated**, because the source docstring is not yet changed. The JSON was not touched by any means |
| **M-16** | `build/infra/apim/apis.json:8`, `build/infra/messaging/queues.json:5` | repoint to `build/contracts/**` or drop | **blocked** — as M-13 |
| **M-17** | `docs/current-implementation/file-map.md:260` — describes `specs/` as present | update or mark historical | **blocked** — the description is true today |
| **M-18** | `docs/architecture/integrations-service-delta.md:9–11,140,162` | **keep** — dated reconciliation record | **preserved intentionally** |
| **M-19** | `ragcore/src/ragcore/governance/fixtures.py:198` + `test_fixtures_excluded.py::test_the_refusal_says_why` — `FR-SCOPE-006` | *(not in the Phase 15 manifest)* | **recorded, blocked** — new finding, §4.5. Repoint to `H-2` at the post-acceptance step |
| **M-20** | `docs/adr/README.md` §*Writing a new record* — live instructions citing the constitution and the specification | *(not in the Phase 15 manifest)* | **completed** — §4.6. Done now because §70.6 requires the index updated with the new record |

Summary: **1 completed** (M-20), **5 preserved intentionally** (M-08, M-09, M-10, M-12, M-18),
**14 blocked** on ADR-0012 acceptance. **0 deleted. 0 regenerated.**

## 6. Repository search results

Counts are over tracked files in the Phase 16 worktree, with `.specify/**` and `specs/**` still
present. They are therefore the **pre-deletion** census, and the post-deletion census is owed by
the phase that performs the deletion.

| Term | Occurrences | Files |
|---|---|---|
| `speckit` | 157 | 31 |
| `.specify` | included in the `constitution` / path census below | — |
| `constitution` | 573 | 70 |
| `Principle IX` | 34 | 25 |
| `Synthia-Platform-Specification` | present, non-authoritative by `00-authority.md` §00.2 | — |

Classification, unchanged from Phase 15 except where this phase acted:

| Class | Where | Verdict |
|---|---|---|
| **historical** | `.specify/**`, `specs/**` (inside the deletion set); `docs/adr/0001…0009`; `docs/architecture/integrations-service-delta.md` | retained deliberately |
| **migration provenance** | `docs/migration/**`; the `Source: constitution#…` lines in `22`, `23`, `24`, `40-testing.md`; ADR-0010, ADR-0011, ADR-0012 | retained deliberately — each says in the same breath that the constitution is migration input, not authority |
| **current governance** | `.claude/hooks/test_guards.py` `speckit`/`.specify` regexes | **active and correct** — they assert *absence*; they are the mechanism, not a dependency |
| **stale / broken** | `docs/adr/README.md` §*Writing a new record* | **corrected** (M-20) |
| **stale after deletion, not yet stale** | M-01…M-07, M-11, M-13…M-17, M-19 | **blocked**, enumerated in §5 |

The ~16 live `Principle IX` citations in `ragcore/**`, `integrations/**`, `dotnet/**` and their
tests are the set Phase 15 §4.4 held open as part of B13-3. They are **left in place**, exactly as
Phase 15 left them, because they remain the only in-tree pointer to the requirement until §10.7
exists. Repointing them to `10-principles.md` `H-1`/`H-2` is post-acceptance work.

```text
zero live execution dependency on Spec Kit      confirmed
zero current authority dependency on Spec Kit   confirmed
zero broken current references to deleted files confirmed (nothing is deleted yet)
historical provenance retained                  confirmed
```

## 7. Validation

Phase 16 changed **no** application source, no schema, no migration, no graph code, no contract and
no test of application behaviour. The four modified files are `CLAUDE.md`,
`.claude/rules/70-adr.md`, `docs/adr/README.md` and `.claude/hooks/test_guards.py`, plus the new
ADR. The gate that covers a `.claude/**` change is the governance guard suite
(`.claude/rules/40-testing.md` §40.6), and it was run.

| Gate | Command | Result |
|---|---|---|
| ADR structure (H5) | `python .claude/hooks/adr_structure_guard.py docs/adr/0012-….md` | **exit 0**, no problems |
| Governance guards | `python .claude/hooks/test_guards.py` | **793/793 checks passed** |
| Deletion set integrity | `git status --porcelain .specify specs` | **empty** — byte-for-byte unchanged |
| Working tree | `git status --short` | 4 modified, 1 added — no source, no test of application behaviour |

The full multi-stack matrix (RagCore, Integrations, .NET, Desktop, Web) was **not re-run**, and
that is a deliberate statement rather than an omission: no file any of those suites compile,
import, lint or assert against was modified. They were last run green in Phase 15 §12 at the same
tree state for all of `ragcore/**`, `integrations/**`, `dotnet/**` and `apps/**`. **They are owed
again by the post-acceptance step**, which does change `ragcore/**`, `integrations/**`,
`apps/desktop/**`, `build/**` and a generated contract.

### 7.1 The guard-suite count changed, and why that is not a weakened test

`test_guards.py` tracks the ADR history as a fact: how many records exist, what the next free
number is, and that the index lists them in ascending order. Creating ADR-0012 made eight of those
assertions false. They were updated to the new true facts — eleven records → twelve, next number
`0012` → `0013`, and the synthetic H5 fixtures moved off `0012` (now taken) onto `0013`.

```text
No assertion was removed, loosened, skipped or narrowed.
Every check that existed before exists after, asserting the same property.
792 checks -> 793: the index loop runs once per indexed record, and there is one more record.
```

This is the same maintenance a new ADR always owes, in the same class as updating
`docs/adr/README.md`.

## 8. Existing deviations — carried forward, not resolved

| Id | State after Phase 16 |
|---|---|
| **DV-13** — `apps/web` `npx tsc -b` fails on 2 pre-existing `readHostedConfig` errors | **OPEN, unchanged and not re-verified.** Phase 15 could not reproduce it in a fresh worktree and explicitly declined to claim it resolved. Phase 16 touched no file in `apps/**` and adds no new evidence either way. **Not repaired** (`00-authority.md` §00.7) |
| **DV-14** — `dotnet format --verify-no-changes` fails locally on Windows CRLF, 7246 `ENDOFLINE` errors | **OPEN, unchanged.** Phase 16 touched no `dotnet/**` file. CI runs on Linux. **Not repaired** |
| **EG-10** — no mechanism binds a diff to the test categories `40-testing.md` §40.9 says it owes | **OPEN, unchanged.** ADR-0012 does not authorize building one, and nothing here closes it |
| **The eight ambiguous cross-stack citations** (Phase 15 §4.4) | **OPEN, unchanged, still explicitly classified.** `integrations/**` §Middleware order ×3, §Validation and errors, §Health, `egress/http.py` prose, `ragcore/**` `repositories.py` prose. Each cites a requirement stated only in the **.NET** baseline; no Python rule states it. Closing them is a separate baseline decision under `70-adr.md` §70.2 B(6), and **ADR-0012 explicitly does not address them** |
| **DV-11 / BL-38** — the .NET image is built from a hand-written Dockerfile rather than SDK container publish | **OPEN, unchanged**, untouched by this phase |

No deviation was silently repaired, and none was rewritten to match the implementation.

## 9. Final verdict

```text
NOT READY FOR FINAL RETIREMENT — ADR-0012 is Proposed and has not been accepted.
```

**Precise reason.** Option A is recorded, and ADR-0012 states the decision in full — but selecting
an option and accepting an ADR are two events, and `.claude/rules/70-adr.md` §70.3 and
`.claude/rules/00-authority.md` §00.10 both state that the second is never inferred from the first.
§70.5 is unambiguous about what a `Proposed` record permits: *"Nothing may be implemented on it."*
Writing `10-principles.md` §10.7 **is** the implementation of ADR-0012, so it has not been written.

Everything downstream follows from that one stop:

- `H-1` and `H-2` do not yet exist in `.claude/rules/**`, so Principle IX clauses 2b and 3 still
  have **no surviving authoritative home**;
- deleting `.specify/**` and `specs/**` would therefore still destroy the only written statement of
  a requirement `ragcore/tests/governance/test_fixtures_excluded.py` mechanically enforces — which
  is **B15-1 unchanged**;
- fourteen of the twenty manifest items are gated on that deletion or on the surviving rule, and
  are recorded `blocked` in §5 rather than executed early.

This is the ordering `70-adr.md` §70.3 and `60-architecture-gates.md` §60.1 require, and the Phase
16 brief anticipated it: *"STOP at the ADR acceptance boundary if the repository process requires
the record itself to become Accepted before implementation."* It does.

### What Phase 16 completed

- Option A formally recorded as a human decision (§2).
- **ADR-0012** written in MADR format, `Status: Proposed`, H5-valid, indexed, naming the exact rule
  text and its exact destination (§3).
- The stale ADR numbering corrected in **two** places, not one — `CLAUDE.md` §8 and
  `.claude/rules/70-adr.md` §70.6 carried the same error (§10).
- `docs/adr/README.md` sequential and accurate through `0012`, showing its real status.
- **M-20** found and corrected; **M-19** found and recorded (§4.5, §4.6) — two omissions from the
  Phase 15 manifest, neither absorbed silently.
- Governance guards green at 793/793, with the count change justified (§7.1).
- Every prior deviation carried forward untouched (§8).

### What the next step is, once a human accepts ADR-0012

In this order, and not before acceptance:

1. Write `.claude/rules/10-principles.md` §10.7 — `H-1`, `H-2`.
2. Repoint **M-19** (`fixtures.py` message **and** its assertion, together) to `H-2`.
3. Repoint the live `Principle IX` citations in `ragcore/**`, `integrations/**`, `dotnet/**` to
   `H-1` / `H-2`.
4. Execute **M-13, M-14, M-16**; fix the **M-15** docstring and **regenerate** with the
   repository's own emitter — never hand-edit `build/contracts/**`.
5. Delete `.specify/**` and `specs/**`.
6. Execute the now-true history rewrites: **M-01, M-02, M-03, M-04, M-05, M-06, M-07, M-11,
   M-17**, and add the "source deleted in Phase 16" note to **M-08, M-09, M-10**.
7. Re-run the **full** matrix — governance guards, boundaries, edge path, RagCore, Integrations,
   .NET, Desktop, Web — plus the generated-contract staleness test.
8. Re-census `speckit` / `.specify` / `constitution` / `Principle IX` post-deletion and classify
   every survivor.

## 10. Numbering — a deliberate departure from the brief's literal text

The Phase 16 brief instructed that `CLAUDE.md` §8 be changed from `(next: **0010**)` to
`(next: **0012**)`. It now reads **`(next: 0013)`**.

The brief's value was correct when the brief was written and became stale the moment ADR-0012 was
created in this same phase. `70-adr.md` §70.6 states that a number is never reused **including the
number of a superseded or deprecated record** — an unaccepted `Proposed` record consumes its number
just as surely. Writing `0012` into the "next" field while `docs/adr/0012-….md` exists on disk
would reproduce exactly the defect Gate 5 exists to fix, and would point the next author at a
collision H5 would reject.

The same correction was applied to **`.claude/rules/70-adr.md` §70.6**, which read *"Existing
sequence: `0001` … `0009`. The next new record is **`0010`**"*. The brief asked only about
`CLAUDE.md` but directed a check for other governance references making the same claim; this was
the one, and it is authority where `CLAUDE.md` is a map.

**Flagged rather than done quietly**, because it departs from an explicit instruction and from one
of the brief's own success conditions.
