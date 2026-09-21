# Phase 13 — Spec Kit content reconciliation and retirement readiness

**Phase goal.** Close the remaining stale-authority citations, resolve the three Phase 11 content
comparisons (D-11-1, D-11-2, D-11-3), and produce an explicit retirement-readiness verdict for the
deletion phase.

**Scope rule observed.** `.specify/**` and `specs/**` were **not** deleted, moved or modified. No
architecture document was modified. No application behaviour, database schema, migration, LangGraph
topology, deployment artifact or runtime behaviour was changed. Every change in this phase is
non-behavioural citation text, plus two fixture constants in the governance suite.

---

## 1. Starting repository state

Verified before any change was made.

| Check | Result |
|---|---|
| Branch | `speckit-to-claude` |
| Working tree | clean (`git status --porcelain` empty) |
| Phase 12 committed | yes — `71b3c83` *docs(governance): migrate the frontend baseline and decouple Spec Kit (phase 12)* |
| Head at start | `6a1b951` *changed status to accepted* |
| `docs/adr/0010-frontend-engineering-baseline.md` | **exists** |
| ADR-0010 status **in the record** | `- **Status:** Accepted` |
| `docs/migration/phase-12-adr-0010-staged.md` | **gone** — `git show --stat 6a1b951` shows it was `git mv`-ed to `docs/adr/0010-frontend-engineering-baseline.md`, status changed in the same commit |
| Phase 12 report | `docs/migration/phase-12-spec-kit-decoupling.md` present |
| Phase 11 record | `docs/migration/phase-11-retirement-readiness.md` present, unmodified |
| Phase 10 record | `docs/migration/phase-10-baseline-reconciliation.md` present, unmodified |
| Based on completed Phase 12 state | yes — `71b3c83` is the direct parent of `6a1b951`, which is `HEAD` |

Nothing was reset, discarded or rewritten.

**Editorial defect found, reported, not repaired (`.claude/rules/00-authority.md` §00.6).**
`docs/adr/README.md:23` lists ADR-0010's status as **Proposed**, while the record itself says
**Accepted**. The record is the authority; the index is stale. The index row also sits between 0008
and 0009 rather than after 0009. Both are **human editorial corrections**, recorded here as
**B13-4**; Claude did not change an ADR status or reorder the index on its own initiative
(`.claude/rules/70-adr.md` §70.5).

---

## 2. Phase 12 validation-count reconciliation

The Phase 12 report is internally inconsistent: §13 opens with *"601 of 602 checks pass"*, its first
table row says *"496 before, 608 after"*, and §18 predicts *"confirm 602/602"*. None of the three was
taken on trust.

### What was actually measured

| Measurement | Method | Result |
|---|---|---|
| Phase 12 commit state | `git clone --shared` into a scratch directory outside the repository, `git checkout 71b3c83`, run `python .claude/hooks/test_guards.py` | **607/608 checks passed** |
| Current state at Phase 13 start (`6a1b951`) | run in the working checkout | **604/611 checks passed**, 7 failing |
| Current state after this phase | run in the working checkout | **611/611 checks passed** |

### The authoritative numbers, and the exact reason for each difference

- **608 is the correct total for the Phase 12 commit.** The `607/608` figure in the Phase 12 report
  is the accurate one. `601/602` and the `602/602` prediction are **wrong** and are corrected here.
  The one Phase 12 failure was the deliberate `exists: docs/adr/0010-frontend-engineering-baseline.md`,
  exactly as that report explains.

- **608 → 611 (+3) is caused by ADR-0010 being placed on disk, not by any check being added.**
  `.claude/hooks/test_guards.py:1171` guards three checks behind `if ADR_0010.is_file():` —
  *ADR-0010 is structurally valid*, *ADR-0010 names the authority it affects*, and *ADR-0010 keeps
  the constitution as migration input only*. With the record absent those three never ran. The
  suite's total is **state-dependent by construction**; this is the whole of the delta, and it
  reconciles exactly: `608 + 3 = 611`.

- **No check was added, removed or inverted by Phase 13.** The total was 611 before this phase's
  edit to the suite and 611 after.

- **The fixtures were re-anchored a second time, for the same reason.** After the repository owner
  placed ADR-0011 (`6e43a51`), the history became **eleven** records and the same seven fixtures
  failed again, one number up. They were re-anchored `ten → eleven` and `0011 → 0012`. The total
  stayed **611**, because — unlike ADR-0010 — no check is conditioned on ADR-0011 being on disk.
  The suite is **611/611**. This is the expected, intended behaviour: the suite pins the real ADR
  history exactly, so every new record makes it fail until it is re-anchored, which is what makes
  the assertion worth having.

### The 7 failures, and why they were failing

All seven were fixtures pinned to the pre-ADR-0010 history. They are **not** violations that
ADR-0010 introduced; they are the suite correctly reporting that its own constants no longer
described the repository:

```text
FAILED: H5 sees the nine historical records
FAILED: the next ADR number is 0010
FAILED: a valid 0010 record passes
FAILED: the minimal MADR dialect passes too
FAILED: H5 exits 0 on a structurally valid new record
FAILED: H5 says nothing when it passes
FAILED: the nine historical records are present
```

`docs/adr/` now holds **ten** records, so `0010` is taken and the next free number is `0011`. The
three fixtures that validate a *new* record were constructing one numbered `0010`, which H5 correctly
rejected with *"already taken"* — H5 was right and the fixtures were stale.

**Disposition — re-anchored, not weakened (`.claude/rules/40-testing.md` §40.1).** The constants were
moved to the current truth and the assertions kept their exact form:

| Before | After |
|---|---|
| `sorted(KNOWN) == list(range(1, 10))` | `sorted(KNOWN) == list(range(1, 11))` |
| `max(KNOWN) + 1 == 10` | `max(KNOWN) + 1 == 11` |
| `len(HISTORY) == 9` | `len(HISTORY) == 10` |
| fixture record `0010-*` | fixture record `0011-*` |
| non-sequential probe `0012-too-far-ahead.md` | `0013-too-far-ahead.md` |

No assertion was deleted, skipped, loosened or narrowed. Every one remains an **exact** equality, and
each is now strictly harder to satisfy by accident than it was (it asserts ten records and a next
number of 0011, both of which a future ADR will break until the suite is re-anchored again — which
is the intended behaviour).

**This inconsistency was a real, reportable defect and is now closed.** The number to quote for the
Phase 12 commit is **607/608**; the number for the repository as this phase leaves it is **611/611**.

---

## 3. Re-audit of live Spec Kit references

### 3.1 A conflation in the Phase 12 report, corrected

Phase 12 recorded *"approximately 35 live surfaces"* citing `constitution Principle VII`. That figure
is **wrong**, and it is wrong because a fixed-string search for `constitution Principle VII` also
matches `constitution Principle VIII`, which is a **different and non-frontend** principle
(*"Provable by Audit and by Test"*). Separated exactly:

| Pattern | Live-tree occurrences (excluding `.specify/**`, `specs/**`, `docs/migration/**`, `docs/adr/**`, `.claude/**`) |
|---|---|
| `constitution Principle VII` (frontend) | **21** |
| `constitution Principle VIII` (audit/telemetry) | **16** |
| combined, as Phase 12 counted them | 37 ≈ *"about 35"* |

### 3.2 The true size of the stale-citation surface

A case-insensitive search for `constitution` across the live trees (`apps/**`, `.github/**`,
`build/**`, `dotnet/**`, `ragcore/**`, `integrations/**`, excluding `node_modules`) returns
**344 lines across 220 files**, not 35. The constitution's non-frontend sections are cited
throughout: `§Python baseline`, `§Secrets`, `§Quality gate`, `§Angular`, Principles I, III, V, VI,
VIII and IX.

`CLAUDE.md` §10 currently states that the stale pointers are *"under `apps/**` and
`.github/workflows/**`"*. That statement is **incomplete** and is recorded as **B13-2**.

### 3.3 Classification

| Class | Count | Disposition |
|---|---|---|
| **A — active dependency** | **0** | No live code or test reads `.specify/**` or `specs/**` at runtime. Verified by searching every `open`/`read_text`/`readFile`/`Path`/`resolve`/`join`/`load` call for those paths: **zero hits**. `ragcore/tests/contracts/test_api_surface.py` names the frozen contract in prose only and does not read it |
| **B — current-authority statement** | 5 | Redirected — §5.3 |
| **C — live source citation** | 56 | Repointed — §4 (55 in `apps/**` + 1 in `.github/workflows/desktop.yml`) |
| **D — historical migration record** | all of `docs/migration/**` | Retained unchanged |
| **E — historical ADR / reference** | `docs/adr/0002,0004,0006,0008,0009,0010`, `docs/architecture/integrations-service-delta.md`, `docs/current-implementation/file-map.md` | Retained — historical records, and the last two are already non-authoritative by `00-authority.md` §00.2 |
| **F — example / test fixture** | `.claude/hooks/test_guards.py` (4 `speckit-` mentions) | Retained — they are the **negative** assertions that no `speckit-*` skill and no `.specify/` mechanism may return. Clearly non-authoritative |
| **G — ambiguous** | 289 | **Documented, not silently classified** — §3.4 |

### 3.4 Class G, stated rather than assumed

The remaining ~289 `constitution` citations in `dotnet/**`, `ragcore/**`, `integrations/**`,
`build/**` and the non-desktop workflows are **not** repointed by this phase, and the reason is
substantive rather than one of effort:

1. They cite constitution sections — `§Python baseline`, `§.NET baseline`, `§Secrets`,
   `§Quality gate`, Principles I, III, V, VI, VIII — whose requirements were migrated in **Phase 9
   from `principles.yaml`, `dotnet.yaml`, `python.yaml` and the explicit baseline block**, not from
   the constitution. The constitution was a *parallel restatement*, which is precisely why Phase 12
   only had to migrate the frontend blocks (the ones it held alone). The requirement is therefore
   **not lost** by deleting the constitution; only the pointer goes stale.
2. Repointing 289 citations across 220 files would be a diff no reviewer can meaningfully check, in
   a phase whose mandate is the frontend citations, and several would need per-case judgement about
   which of P-1…P-32 / BL-01…BL-39 / DN-*/PY-* they mean. `.claude/rules/70-adr.md` §70.2 and the
   Phase 13 brief both forbid inventing a requirement to obtain a replacement id.
3. None of them **asserts that the constitution is authoritative**. They are attributions of the
   form *"(constitution §X)"*. The authority layer already says the opposite, unambiguously and by
   path: `.claude/rules/00-authority.md` §00.4.

Recorded as **B13-2**, with a recommendation in §14.

**Principle IX has no migrated home — B13-3.** Constitution Principle IX (*"Scaffold Honestly; Do Not
Invent Product"*) was cited at three `apps/web` sites. It was **not** migrated by ADR-0010 and no
`FE-*` requirement states it. Rather than invent an id, those three comments were rewritten to state
the substance and cite nothing. The gap itself is recorded, not closed.

---

## 4. B12-2 — stale frontend constitution citations: CLOSED

Every occurrence was inspected individually; no blanket replacement was used. The working set taken
was **all 53 `constitution` mentions in `apps/**` plus the 2 in `.github/workflows/desktop.yml`** —
a superset of the 21 mandated `Principle VII` ones, chosen because `apps/**` is exactly the scope
that `.claude/rules/{22,23,24}` own, and because repointing only some lines of a comment block would
have left the surrounding prose citing a retired document.

### 4.1 Citation inventory and disposition

| File | Original citation | Requirement it actually refers to | Replacement |
|---|---|---|---|
| `.github/workflows/desktop.yml` (header, 2 lines) | Principle VII + "the constitution states unconditionally" | the Electron security suite | `.claude/rules/24-electron.md` §24.1–§24.5 |
| `apps/desktop/eslint.config.js` ×2 | no remote/dynamic code execution | **FE-EL-10** | `24-electron.md` |
| `apps/desktop/eslint.config.js` | "a control the constitution states unconditionally" | the switch set | `24-electron.md` |
| `apps/desktop/eslint.config.js` | `webSecurity` MUST NOT be disabled | **FE-EL-3** | `24-electron.md` |
| `apps/desktop/eslint.config.js` | `contextIsolation` MUST remain enabled | **FE-EL-2** | `24-electron.md` |
| `apps/desktop/eslint.config.js` | `nodeIntegration` MUST remain disabled | **FE-EL-2** | `24-electron.md` |
| `apps/desktop/eslint.config.js` | insecure content MUST NOT be allowed | **FE-EL-3** | `24-electron.md` |
| `apps/desktop/eslint.config.js` | raw `ipcRenderer` MUST NEVER be exposed | **FE-EL-4** | `24-electron.md` |
| `apps/desktop/src/ipc-contracts/index.ts` ×2 | sender + argument are two distinct obligations | **FE-EL-5** | `24-electron.md` |
| `apps/desktop/src/main/app-shell.ts` | authorization answered server-side | **FE-EL-1** | `24-electron.md` |
| `apps/desktop/src/main/endpoint-execution-boundary.ts` ×2 | what the endpoint execution path must do | **FE-EL-11** | `24-electron.md` |
| `apps/desktop/src/main/index.ts` | no business authorization decision in the renderer | **FE-EL-1** | `24-electron.md` |
| `apps/desktop/src/main/index.ts` | `openExternal` never receives an untrusted URL | **FE-EL-8** | `24-electron.md` |
| `apps/desktop/src/main/ipc-guard.ts` ×2 | every IPC sender and argument validated | **FE-EL-5** / **FE-EL-1** | `24-electron.md` |
| `apps/desktop/src/main/navigation.ts` | navigation / new-window restriction | **FE-EL-6** | `24-electron.md` |
| `apps/desktop/src/main/renderer-protocol.ts` | `file://` avoided where a safer strategy applies | **FE-EL-9** | `24-electron.md` |
| `apps/desktop/src/main/session-boundary.ts` | authorization re-verified server-side | **FE-EL-1** | `24-electron.md` |
| `apps/desktop/src/main/window.ts` | the endpoint decides nothing | **FE-EL-1** | `24-electron.md` |
| `apps/desktop/src/main/window.ts` | `sandbox` "where compatible" | **FE-EL-2** | `24-electron.md` |
| `apps/desktop/src/preload/bridge.ts` | narrow contextBridge surface | **FE-EL-4** | `24-electron.md` |
| `apps/desktop/tests/no-policy.spec.ts` | Principle VII + Principle III for the endpoint | **FE-EL-1** + **FE-EL-11** | `24-electron.md` |
| `apps/desktop/tests/security.spec.ts` | "a control the constitution states unconditionally" | the suite's subject | `24-electron.md` §24.1–§24.5 |
| `apps/web/README.md` | no state-management framework without a requirement | **FE-NG-7** | `23-angular.md` |
| `apps/web/eslint.config.js` | no secret in browser code; sanitization not optional | **FE-SH-2** + **FE-NG-10** | `22-web-typescript.md`, `23-angular.md` |
| `apps/web/eslint.config.js` | `bypassSecurityTrust*` needs justification | **FE-NG-10** | `23-angular.md` |
| `apps/web/.../chat/chat-shell.ts` | `inject()` where appropriate | **FE-NG-3** | `23-angular.md` |
| `{customer-portal,desktop-renderer,staff-portal}/app.config.ts` ×3 | infrastructure centralized, not repeated | **FE-NG-4** | `23-angular.md` |
| `{customer-portal,desktop-renderer,staff-portal}/app.config.ts` ×3 | no state-management framework | **FE-NG-7** | `23-angular.md` |
| `{customer-portal,desktop-renderer,staff-portal}/platform.config.ts` ×3 | no secret in browser code | **FE-SH-2** | `22-web-typescript.md` |
| `platform-core/src/lib/api/platform-api.config.ts` ×2 | no secret in browser code | **FE-SH-2** | `22-web-typescript.md` |
| `platform-core/src/lib/auth/auth.service.ts` | auth/token handling centralized | **FE-NG-4** | `23-angular.md` |
| `platform-core/src/lib/platform-core.providers.ts` | api/auth/realtime centralized | **FE-NG-4** | `23-angular.md` |
| `platform-core/src/lib/realtime/realtime.service.ts` | realtime infrastructure centralized | **FE-NG-4** | `23-angular.md` |
| `platform-core/src/lib/security/sanitization-policy.ts` | no sanitization bypass | **FE-NG-10** | `23-angular.md` |
| `desktop-renderer/.../desktop-bridge.service.ts` | no authorization decision in renderer or main | **FE-EL-1** | `24-electron.md` |
| `desktop-renderer/.../desktop-bridge.ts` | re-decided server-side | **FE-EL-1** | `24-electron.md` |
| `desktop-renderer/.../desktop-bridge.types.ts` | re-verified server-side | **FE-EL-1** | `24-electron.md` |
| `desktop-renderer/.../desktop-bridge.spec.ts` | no authorization surface | **FE-EL-1** | `24-electron.md` |
| `platform-core/no-authz.spec.ts` (2 `describe`, 2 messages) | bypass ban; no secret in browser code | **FE-NG-10**, **FE-SH-2** | `23-angular.md`, `22-web-typescript.md` |
| `desktop-renderer/src/app/app.ts` | Principle **IX** — honest scaffold | **no migrated requirement** | substance kept, citation removed — **B13-3** |
| `platform-core/src/lib/auth/auth.service.ts` | Principle **IX** | **no migrated requirement** | substance kept, citation removed — **B13-3** |
| `platform-core/src/lib/realtime/realtime-connection.ts` | Principle **IX** | **no migrated requirement** | substance kept, citation removed — **B13-3** |

Two citations additionally carried `spec FR-SURF-004`, a `specs/**` requirement id. Both are in
`desktop-renderer` bridge files whose subject is the no-authorization-surface rule; the id was
dropped with the constitution reference because **FE-EL-1** states the obligation and `specs/**` is
retiring.

### 4.2 Result

```text
constitution mentions in apps/** and .github/workflows/desktop.yml : 0
```

### 4.3 Proof that behaviour did not change

Every replacement is inside a comment, a JSDoc block, an ESLint `message:` string, a test
`describe()` label or an assertion failure message. No executable expression, no control flow, no
selector, no matcher and no configuration value was touched.

| Gate | Before this phase | After |
|---|---|---|
| `apps/desktop` — `npm run typecheck` | clean | clean |
| `apps/desktop` — `npm run lint` | clean | clean |
| `apps/desktop` — `npx vitest run` | **178 passed (4 files)** | **178 passed (4 files)** |
| `apps/web` — `npx eslint .` | clean | clean |
| `apps/web` — `npm test` | **9 passed, 0 failed** | **9 passed, 0 failed** |
| `apps/web` — `npx prettier --check .` | clean | clean |
| `apps/web` — `npx tsc -b` | **2 errors** (see below) | **the same 2 errors, unchanged** |

**Pre-existing deviation, recorded not repaired — DV-13.** `npx tsc -b` in `apps/web` fails at the
Phase 12 commit and still fails, identically:

```text
projects/customer-portal/src/app/app.config.ts(7,31): error TS2305:
  Module '"platform-core"' has no exported member 'readHostedConfig'.
projects/staff-portal/src/app/app.config.ts(7,31): error TS2305: ...
```

This is a deviation from **FE-SH-3** (the frontend quality gate requires a passing strict type
check). It was present before any Phase 13 edit, it is unrelated to citation text, and
`.claude/rules/00-authority.md` §00.7 requires it to be **recorded, not silently repaired as a side
effect of finding it**.

**Incident worth recording.** The first application of these edits wrote the files with CRLF line
endings, converting 35 LF files wholesale. `npx prettier --check` caught it immediately (21 files
flagged). All 35 files were normalised back to LF, after which prettier reports
*"All matched files use Prettier code style!"*. The final diff is **78 insertions / 63 deletions
across 40 files** — comment text only. Later edits detect and preserve each file's existing line
endings; two `.cs` files were CRLF in the working copy before and after.

---

## 5. D-11-1 — contracts content comparison: CLOSED

### 5.1 What is authoritative today, on the evidence

`.github/workflows/contracts.yml` states and enforces that the API contract *"is an ARTIFACT emitted
from the running services, not a document maintained beside them"*. The pipeline asserts, in order:
the documents generate from running services; emission is **byte-identical deterministic**; each is
publishable (no secret, no client-suppliable tenant/role/audience, RFC 9457 throughout); there is no
**breaking** difference against the committed contract without explicit approval; and **the committed
contracts are not stale**. `.claude/rules/20-dotnet.md` **BL-6** makes the contract code-first.

`build/contracts/**` is therefore the current authoritative *artifact* — not because it is generated,
but because a committed CI gate proves it matches the running services and fails when it does not.
Seven documents, 31 endpoints.

### 5.2 Disposition of each of the nine Spec Kit contract documents

Compared by content, not filename. Endpoint sets were extracted from each document and diffed against
the union of paths in `build/contracts/**`.

| Artifact | Classification | Evidence |
|---|---|---|
| `contracts/customer-api.md` | **Duplicate** | Declares no endpoint of its own; its surface is `build/contracts/{ragcore,dotnet}/customer.v1.openapi.json`, asserted exactly (`==`, not subset) by `ragcore/tests/contracts/test_api_surface.py` and `dotnet/tests/Synthia.ContractTests/` |
| `contracts/staff-api.md` | **Duplicate** | as above, `staff.v1.openapi.json` |
| `contracts/workload-api.md` | **Duplicate** | as above, `workload.v1.openapi.json` (RagCore and Integrations each emit their own, per ADR-0007) |
| `contracts/integrations-api.md` | **Duplicate** | as above |
| `contracts/read-views.md` | **Duplicate** | the view endpoints are all present in `build/contracts/dotnet/{customer,staff}.v1.openapi.json` |
| `contracts/sample-flows.md` | **Duplicate** | the sample-flow surface is implemented at `ragcore/src/ragcore/api/customer/sample_flows.py` and classified in `docs/functional/implemented.md` |
| `contracts/notifications.md` | **Historical snapshot** | its three "missing" paths (`/api/hubs/{hub}/…`) are **Azure Web PubSub upstream REST paths**, not platform endpoints, and were never part of the platform's own OpenAPI |
| `contracts/triggers.md` | **Duplicate** | see §5.2.1 |
| `contracts/README.md` | **Duplicate**, with one migrated item | see §5.2.2 |

**Unique current requirements found: none.** No contract obligation stated in the nine documents is
absent from a current authoritative artifact. Nothing needed migrating into a new location, and
nothing was copied wholesale into a new directory.

#### 5.2.1 `triggers.md` — the message contract

The trigger contract is the one place a prose-only obligation was plausible, because
`build/infra/messaging/queues.json` explicitly says *"triggers.md defines the MESSAGES — their kinds,
their closed field sets, what they do and do not carry, and the consumer's obligations."* It is
nonetheless fully represented in executable code:

| Obligation in `triggers.md` | Where it lives now |
|---|---|
| the three-field body `{workItemId, correlationId, kind}` | `ragcore/src/ragcore/domain/envelopes.py` |
| the `{jobId, correlationId, kind}` variant (ADR-0007) | `integrations/src/integrations/messaging/envelope.py` |
| the six trigger kinds | `TriggerKind` enum (`ragcore`), `envelope.py` (`integrations`), `build/infra/messaging/queues.json` |
| "a message carrying any additional field is refused and dead-lettered, not sanitised" | `integrations/tests/unit/test_envelope.py`, `ragcore/src/ragcore/messaging/deadletter.py` |
| "every trigger is untrusted; authority comes from the durable row" | `integrations/workers/command_consumer.py`, `integrations/tests/unit/test_consumer_and_authority.py` |
| queue identities, transport settings, which principal may send | `build/infra/messaging/queues.json` (which states it was created precisely to hold what the prose contract could not) |

#### 5.2.2 `contracts/README.md` — the sort/filter whitelist

`README.md` carries a per-resource sortable/filterable field matrix. The matrix itself **is** in
code — `dotnet/src/Modules/Synthia.Modules.Sessions/SortKeys.cs` holds the complete sets and
`Synthia.Contracts/Querying/QueryWhitelist` enforces them, with an unknown field a 400 rather than a
silent ignore. What was stale was the **citation**: two doc comments named the retiring document as
the place the sets are *enumerated*. Both were repointed (§5.3).

`apis.json` records that the APIM routing table *"lived only in prose — specs/…/contracts/README.md
and a sentence in tasks.md"* **until that file existed**; the routing has therefore already been
migrated to `build/infra/apim/apis.json`. That sentence is historical narrative, not a current
authority claim, and is retained.

### 5.3 Class B — current-authority statements redirected

Five citations asserted `specs/**` as a current source of truth for a contract. All were redirected
to the current authority; none preserved the old path as authority.

| File | Was | Now |
|---|---|---|
| `apps/web/projects/platform-core/src/lib/contracts/primitives.ts` | "Shared primitives from the contracts under `specs/001-platform-scaffold/contracts/`" | "…from the generated API contracts under `build/contracts/`" |
| `ragcore/tests/contracts/test_api_surface.py` | "checked against the frozen contract in `specs/001-platform-scaffold`" | "checked against the generated contracts under `build/contracts/`" |
| `dotnet/src/Synthia.Contracts/Querying/SortSpec.cs` | "The per-resource sets are enumerated in `specs/…/contracts/README.md`" | "…declared in each module's sort-key type and published in the generated contracts under `build/contracts/`" |
| `dotnet/src/Modules/Synthia.Modules.Sessions/SortKeys.cs` ×2 | "the complete ones from `contracts/README.md`"; "asserted against the contract document" | "the complete ones for this module"; "asserted against the generated contract" |

No architectural boundary and no contract authority model changed, so the ADR gate was **not**
triggered by D-11-1. `build/contracts/**` was **not** newly declared authoritative — the existing
pipeline evidence (staleness gate, determinism gate, breaking-change gate) already establishes it.

### 5.4 Validation of §5.3

| Gate | Result |
|---|---|
| `ragcore` — `uv run ruff check .` | All checks passed |
| `ragcore` — `uv run ruff format --check .` | 248 files already formatted |
| `ragcore` — `uv run pytest -q tests/contracts` | **99 passed** |
| `dotnet build` | **Build succeeded. 0 Warning(s), 0 Error(s)** (with `TreatWarningsAsErrors`) |
| `dotnet test` | **242 passed, 0 failed** across 7 assemblies |
| `build/scripts/check-boundaries.sh` | all four boundary assertions pass |
| `build/contracts/**` | **unmodified** — confirmed by `git status`; the .NET emission test did not change a committed contract |

---

## 6. D-11-2 — test-category matrix comparison: **OPEN**, ADR required

This is the one finding Phase 13 could not close, and it is the retirement blocker.

### 6.1 The comparison

The constitution carries three testing blocks. `.claude/rules/40-testing.md` was compared against each
by content.

| Constitution block | Status against `40-testing.md` | Detail |
|---|---|---|
| **§Required test categories** — 15 named categories, *"All are required; none substitutes for another"*, plus *"a security or isolation fix without a failing-then-passing test is incomplete"* | **MISSING** | §40.5 names test kinds required by **principles** (P-3, P-11, P-20, P-21, P-25, P-30, P-31, P-32, P-12, DN-19). That is a different axis. No file in `.claude/rules/` lists the fifteen categories or states their non-substitutability |
| **§Which change requires which category** — a 12-row matrix binding a kind of change to the categories it owes, *"so the obligation is mechanical at review rather than a matter of judgement"*, with unit tests owed by every change | **MISSING** | No equivalent anywhere in `.claude/rules/`. §40.5 answers *"what does this principle owe?"*; this answers *"what does this change owe?"*. Neither derives from the other |
| **§Coverage** — *"No line- or branch-coverage threshold is set, and none gates a merge"*, deliberate, and coverage **must not** become a gate without amending the section | **MISSING** | `40-testing.md` is silent on coverage. Losing a prohibition silently permits the thing it forbade |
| the recorded coverage exception — two Principle VIII hard failures (*tenant context from an untrusted client field*, *authorization bypass*) have no backend test because the protection was deferred | **MISSING** (the statement; the underlying gap is ADR-0008 **D-01**, which is recorded) | must be carried across as a recorded gap, not repaired |

Per row of the matrix, against the current tree:

| Row | Covered today? |
|---|---|
| API endpoint / message shape → Contract; authorization | **partially** — the suites exist and run; the *obligation* is unstated |
| authorization rule / role set → Authorization; security | partially, as above |
| query, repository, view, retrieval path → Tenant isolation; retrieval isolation | partially |
| catalogue entry / treatment policy / gate → Governance; authorization | partially |
| approval, consent, verdict, resume → Approval; concurrency; idempotency | partially — `30-langgraph.md` §30.9 owns part of this |
| external side effect → Idempotency; adapter | partially — P-21 in §40.5 covers idempotency only |
| migration, table, published view → Integration; tenant isolation; architecture dependency | partially — `50-database.md` §50.8 owns part |
| module boundary / project reference / import → Architecture dependency | **covered in substance** by §60.6 and the architecture suites |
| configuration option / secret reference → Configuration validation | **missing** |
| outbox, trigger, claim, worker → Idempotency; concurrency | **missing** |
| client surface primary journey → accessibility; e2e golden path | **covered** — `23-angular.md` FE-NG-5, FE-NG-6 (migrated by ADR-0010) |
| security/isolation fix → failing first, then passing | **missing** |

**Obsolete rows: none.** Every category named has a live suite directory
(`ragcore/tests/{governance,authorization,isolation,idempotency,concurrency,contracts,…}`,
`dotnet/tests/{ArchitectureTests,AuthorizationTests,ContractTests,TenantIsolationTests}`,
`integrations/tests/{architecture,security,unit}`).

**Architecture-specific and governed elsewhere:** the approval/resume and migration rows overlap
`30-langgraph.md` §30.9 and `50-database.md` §50.8, which keep their obligations; the frontend row is
owned by `23-angular.md`.

### 6.2 Why this could not simply be written into `40-testing.md`

Adding fifteen required categories, a twelve-row obligation matrix and a coverage prohibition to
`.claude/rules/40-testing.md` **is a change to the engineering baseline**. `.claude/rules/70-adr.md`
§70.2 B(6) makes a change to a mandatory engineering convention — naming test placement explicitly —
an ADR trigger, and **ADR-0010 set the precedent one phase earlier**: constitution requirement text is
migrated under an accepted ADR, never transcribed as an editorial act.

`.claude/rules/70-adr.md` §70.3 requires the ordering *DETECT → STOP → DESCRIBE → ADR → human
ACCEPTANCE → IMPLEMENT*, and states that **writing an ADR is not accepting it**. Claude does not
accept an ADR it authored, and acceptance is never inferred from the task description, from the
change being obviously needed, or from the session running unattended
(`.claude/rules/00-authority.md` §00.10).

### 6.3 What Phase 13 did

- Performed the content comparison in full (§6.1) — this is what D-11-2 asked for.
- Drafted **ADR-0011 — *Migrate the required-test-category baseline and the per-change test
  matrix*** with status `Proposed`, classified under `70-adr.md` §70.4 as **Engineering Baseline**.
- **Stopped.** Nothing was written into `40-testing.md`.

**The draft could not be placed from this session, and was placed by the repository owner.** H5
(`.claude/hooks/adr_structure_guard.py`) blocks every *shell* write to a new ADR path, because it can
only validate content carried by a whole-file `Write`; and the `Write` tool required worktree
isolation, which this phase was explicitly instructed not to use. This is the **same mechanical
obstacle Phase 12 hit** with ADR-0010, and routing around H5 was refused for the same reason: it is
exactly the behaviour the governance model exists to prevent.

The repository owner then placed the record themselves, in commit `6e43a51` *"added during phase 13
adr"*, at `docs/adr/0011-required-test-categories-baseline.md`, **with status `Proposed`**. Phase 13
then added its row to `docs/adr/README.md` (`.claude/rules/70-adr.md` §70.6 — the index is not a
record, and H5 exits 0 on it). Indexing a `Proposed` record asserts nothing about acceptance.

**D-11-2 remains OPEN.** The record exists and is indexed; it has **not** been accepted, and nothing
has been written into `.claude/rules/40-testing.md`. Acceptance is a human act and is never inferred
(`.claude/rules/00-authority.md` §00.10).

---

## 7. D-11-3 — deferred vs implemented comparison: CLOSED

`specs/001-platform-scaffold/tasks.md` §*"Deferred — not covered by the two golden paths"* names
exactly three items.

| Deferred item | Classification | Evidence in `docs/functional/implemented.md` |
|---|---|---|
| **Desktop script execution** (blocked on ADR-0004 script signing and the destructive taxonomy) | **Covered** | line 758 — *"`EndpointExecutionNotImplementedError` unconditionally. No script execution exists on the…"*; line 891 — *"Endpoint script execution \| Not implemented \| `IS_IMPLEMENTED = false`; both functions always throw"* |
| **Ingestion behaviour** (only the run record is scaffolded) | **Covered** | line 596 — *"Ingestion acquisition, chunking and embedding are **not implemented at all**; only the run record is"*; line 905 repeats it in the summary table |
| **UC-01 through UC-12** (Stage 14, gated behind both golden paths; *"no product definitions exist"*) | **Historical** | Absent from `implemented.md`, and **correctly so**. `.claude/rules/90-functional-knowledge.md` §90.4 forbids the record from containing *"future state, roadmap, or planned features"*. These are unspecified future use cases, not an omission in implemented behaviour. The Phase 13 brief likewise forbids turning historical planning information into implemented functionality |

**Contradictory: none. Missing: none. Ambiguous: none.**

The related claim — that seven worker modules cite `tasks.md` as the register of their own deferral —
was also checked. `implemented.md` §9.4 *"Worker processes — Not implemented"* classifies all seven
by name (`expiry_sweep`, `ingestion_run`, `integration_result_worker`, `outbox_dispatch`,
`resume_worker`, `retention_sweep`, `integrations/workers/command_consumer`) and states that the
behaviour functions are implemented and tested while no worker process can be started. That is the
same information, in the authoritative place, at a finer grain than `tasks.md` carries.

**No functional knowledge is lost when `specs/**` is deleted.** `docs/functional/implemented.md` was
**not modified** by this phase: nothing in Phase 13 changed product behaviour, so
`.claude/rules/90-functional-knowledge.md` §90.3 (*implement → verify → update*) owes no update, and
§90.6 step 1 identifies no affected functional knowledge.

---

## 8. Authority consistency audit

| Domain | Required authority | Verified |
|---|---|---|
| Identity architecture | `docs/architecture/identity-plane-final.md` | **Yes** — sole; unmodified this phase |
| Overall architecture | `docs/architecture/Synthia-OverallArchitecture-final.md` | **Yes** — sole; unmodified |
| Rag/agent architecture | `docs/architecture/RagAgent-Architecture-final.md` | **Yes** — sole; unmodified |
| Engineering baseline | `.claude/rules/**` | **Yes** — `00-authority.md` §00.3; the only Phase 13 change to the tree is fixture constants in a hook, not a rule |
| Frontend baseline | `.claude/rules/{22-web-typescript,23-angular,24-electron}.md` | **Yes** — and now cited by name from the 56 repointed surfaces |
| Functional knowledge | `docs/functional/implemented.md` | **Yes** — sole; unmodified |
| ADR policy / history | `.claude/rules/70-adr.md` + `docs/adr/**` | **Yes**, with editorial defect **B13-4** (index status) recorded |
| Database governance | `.claude/rules/50-database.md` + `.claude/skills/db-change/` | **Yes** — unmodified |
| LangGraph governance | `.claude/rules/30-langgraph.md` + `.claude/skills/langgraph-change/` | **Yes** — unmodified |
| Testing governance | `.claude/rules/40-testing.md` | **Yes** as the sole file, **but incomplete in content** — D-11-2 |

**Is `.specify/**` or `specs/**` named as current authority anywhere in live instructions?** No.
`.claude/rules/00-authority.md` §00.4 names both non-authoritative by path;
`.claude/rules/23-angular.md:102` cites `specs/…/plan.md` while explicitly calling it *"a retiring,
non-authoritative"* source; `.serena/memories/core.md:38` calls them *"retired Spec Kit trees.
History only."*; `CLAUDE.md` §10 says they *"are history — not architecture authority, not engineering
baseline, not evidence of implemented behavior."*

---

## 9. Claude Code context-loading re-check

| Requirement | Result |
|---|---|
| Global rules contain only repository-wide policy | **Yes** — nine files carry no `paths:`: `00`, `10`, `30`, `40`, `50`, `60`, `70`, `80`, `90`. Five state policy applying to any change; the four gate rules are deliberately global so they are detected *before* a governed file is opened |
| .NET rules scoped to the .NET tree | **Yes** — `20-dotnet.md` → `dotnet/**` |
| Python rules scoped to the Python application trees | **Yes** — `21-python.md` → `ragcore/**`, `integrations/**` |
| Common frontend rules apply to `apps/**` | **Yes** — `22-web-typescript.md` → `apps/**` |
| Angular rules apply to `apps/web/**` | **Yes** — `23-angular.md` |
| Electron rules apply to `apps/desktop/**` | **Yes** — `24-electron.md` |
| Task procedures remain skills | **Yes** — exactly four: `adr-author`, `db-change`, `functional-update`, `langgraph-change` |
| No `CLAUDE.md` import forces all rules into every session | **Yes** — `CLAUDE.md` maps and points; it imports nothing |
| No rule duplicated to be self-contained | **Yes** — unchanged this phase; the repointed citations *add* cross-rule pointers (`FE-EL-1`, `FE-NG-4`…) rather than copying rule text into source |

The suite asserts each scope prefix is a real directory **and** matches tracked files; all pass.

---

## 10. Final Spec Kit dependency audit

| Requirement | Result | Evidence |
|---|---|---|
| Zero `.claude/skills/speckit-*` | **MET** | `.claude/skills/` holds exactly `adr-author`, `db-change`, `functional-update`, `langgraph-change` |
| Zero active Claude skill dependency on `.specify/**` | **MET** | no skill references the mechanism; asserted by the suite |
| Zero active Claude configuration invoking Spec Kit | **MET** | `grep -i -E "speckit|\.specify" .claude/settings.json` → 0 |
| Zero current-authority references to `.specify/**` | **MET** | the four live mentions (`00-authority.md`, `22-web-typescript.md` ×2, `integrations-service-delta.md` ×2) all **deny** authority or are themselves non-authoritative |
| Zero current-authority references to `specs/**` | **MET** | the five class-B assertions were redirected (§5.3); the remainder are historical narrative or explicitly labelled retiring |
| No current source says the constitution is authoritative | **MET** | `00-authority.md` §00.4 says the opposite by path. The 289 remaining `constitution §X` attributions (**B13-2**) are stale pointers, not authority grants |
| No current source routes future development through Spec Kit | **MET** | `.serena/memories/task_completion.md:14` routes contract changes to `build/contracts/` and `20-dotnet.md` BL-6; line 16 routes test kinds to `40-testing.md` §40.5 and flags the matrix as open |
| Historical migration records intact | **MET** | `docs/migration/phase-{2,7,8,9,10,11,12}*` unmodified |
| Historical ADR references intact | **MET** | `docs/adr/0001`–`0009` unmodified; `0010` unmodified |
| **Zero runtime dependency** | **MET** | no `open`/`read_text`/`readFile`/`Path`/`resolve`/`join`/`load` call anywhere resolves a `.specify/**` or `specs/**` path |

Textual historical mentions remain and are allowed. The requirement met is **zero current
authority/dependency**, not zero historical words.

---

## 11. Tests executed, with exact results

Every figure below is an observed command result.

| Command | Where | Result |
|---|---|---|
| `python .claude/hooks/test_guards.py` | repo root | **611/611 checks passed** |
| `python .claude/hooks/test_guards.py` @ `71b3c83` (scratch clone) | reconciliation | **607/608 checks passed** |
| `npm run typecheck` | `apps/desktop` | pass, no output |
| `npm run lint` | `apps/desktop` | pass, no output |
| `npx vitest run` | `apps/desktop` | **4 files, 178 tests passed** |
| `npx eslint .` | `apps/web` | pass, no output |
| `npm test` | `apps/web` | **tests 9, pass 9, fail 0** |
| `npx prettier --check .` | `apps/web` | *All matched files use Prettier code style!* |
| `npx tsc -b` | `apps/web` | **2 errors — pre-existing and identical to baseline** (DV-13) |
| `dotnet build` | `dotnet/` | **Build succeeded. 0 Warning(s), 0 Error(s)** |
| `dotnet test --no-build` | `dotnet/` | **242 passed, 0 failed, 0 skipped** (ArchitectureTests 88, SharedKernel 69, ContractTests 51, Authorization 21, TenantIsolation 11, Modules.Audit 1, Modules.Governance 1) |
| `dotnet format --verify-no-changes` | `dotnet/` | **fails — pre-existing, DV-14** (see below) |
| `uv run ruff check .` | `ragcore/` | All checks passed |
| `uv run ruff format --check .` | `ragcore/` | 248 files already formatted |
| `uv run mypy` | `ragcore/` | Success: no issues found in 219 source files |
| `uv run pytest -q` | `ragcore/` | **1301 passed** |
| `uv run pytest -q tests/contracts` | `ragcore/` | **99 passed** |
| `uv run ruff check .` | `integrations/` | All checks passed |
| `uv run ruff format --check .` | `integrations/` | 68 files already formatted |
| `uv run mypy` | `integrations/` | Success: no issues found in 67 source files |
| `uv run pytest -q` | `integrations/` | **155 passed** |
| `bash build/scripts/check-boundaries.sh` | repo root | all four assertions pass |

**No test was deleted, skipped, `xfail`ed, loosened or narrowed** (`.claude/rules/40-testing.md`
§40.1). The only change to a test file in this phase is citation text inside `describe()` labels,
docstrings and assertion *messages*; no assertion, matcher, fixture or input changed.

**Pre-existing deviation DV-14 — `dotnet format --verify-no-changes` fails locally.** It reports
`ENDOFLINE` errors in 12 files, of which **10 were never touched by this phase** (for example
`dotnet/tests/Synthia.ContractTests/OpenApiEmissionTests.cs`, which `git status` shows as unmodified
and which `file` reports as CRLF). This is a Windows-checkout line-ending condition, not a formatting
defect: the index stores LF and CI runs the gate on `ubuntu-latest`. The two files this phase edited
were CRLF in the working copy before the edit and were written back with their original endings
preserved. **Recorded, not repaired** — normalising 12 files' line endings is outside this phase and
would be churn in an unrelated area.

### Mutation / negative validation (§12 of the brief)

Using the suite's **existing** negative and worktree-planting harness — no production code was
modified to create a mutation case:

| Negative case | Result |
|---|---|
| Reintroducing a Spec Kit skill is rejected | **pass** — the suite asserts exactly the four governance skills and no `speckit-*` |
| Reintroducing a current-authority constitution statement is rejected | **pass** — the suite asserts every live mention of the constitution denies authority |
| Reintroducing an old frontend baseline choice is rejected | **pass** — the three checks Phase 12 inverted (asserting no TS baseline had been invented) now assert the migrated baseline and its ADR |
| ADR-0010 structurally valid and Accepted | **pass** — H5's own `validate()` reports no problems; the record's status field reads `Accepted`; the suite asserts it names the authority it affects and keeps the constitution as migration input only |
| Path-scoped rules remain valid | **pass** — frontmatter terminated, `paths:` present and non-empty, one H1 after it, every prefix a real directory matching tracked files |
| DB / LangGraph / ADR gates unchanged | **pass** — `.claude/rules/{30,50,70}.md` and `.claude/hooks/{db_migration_guard,langgraph_change_guard,adr_structure_guard}.py` are byte-identical to `HEAD` |
| H5 still blocks an unvalidatable ADR write | **demonstrated live** — H5 refused both a shell `mv` onto an existing record and a shell write to a new `docs/adr/0011-*.md`, in this session |

---

## 12. Remaining blockers

| # | Blocker | Why it blocks deletion | What closes it |
|---|---|---|---|
| **BL-13-1** | **D-11-2 is open.** The constitution's §Required test categories (16), §Which change requires which category (12 rows) and §Coverage policy exist in **no** current authority | `.specify/memory/constitution.md` is inside the Phase 14 deletion set. Deleting it destroys a binding engineering requirement that nothing else states | A human **accepts ADR-0011**, then the three blocks are migrated into `.claude/rules/40-testing.md` and the suite re-run |
| ~~**BL-13-2**~~ | ~~ADR-0011 is not on disk~~ | — | **CLOSED.** The repository owner placed the record in `6e43a51` with status `Proposed`; Phase 13 indexed it in `docs/adr/README.md` |
| **BL-13-3** | **The placed ADR-0011 carries a factual error.** Four lines say *"sixteen named categories"*; the constitution's table has exactly **fifteen** rows. The enumerated name list in the same record is correct at 15 names — only the count word is wrong | A record should not be accepted while it misstates its own source | The repository owner overwrites the record with the corrected draft. Claude cannot: H5 blocks a write to an **existing** record, and `70-adr.md` §70.6 makes amending one a human-directed act |

### Non-blocking findings recorded

| # | Finding | Status |
|---|---|---|
| **B13-2** | The stale-citation surface is **344 lines across 220 files**, not the ~35 Phase 12 recorded. `CLAUDE.md` §10's statement that the stale pointers are confined to `apps/**` and `.github/workflows/**` is incomplete | recorded; §14 recommends a dedicated phase |
| **B13-3** | Constitution **Principle IX** (*Scaffold Honestly; Do Not Invent Product*) has **no** migrated home in `.claude/rules/**`. Three `apps/web` comments were rewritten to state the substance and cite nothing | recorded; a human decides whether it warrants a requirement |
| **B13-4** | `docs/adr/README.md:23` shows ADR-0010 as `Proposed` while the record says `Accepted`; the row is also out of sequence | recorded, **not repaired** — a status is a human act (`70-adr.md` §70.5) |
| **DV-13** | `npx tsc -b` in `apps/web` fails on 2 pre-existing `readHostedConfig` errors — a deviation from **FE-SH-3** | recorded, not repaired (`00-authority.md` §00.7) |
| **DV-14** | `dotnet format --verify-no-changes` fails locally on 12 files for Windows CRLF reasons; 10 are untouched by this phase; CI runs on Linux | recorded, not repaired |
| **EG-10** | No mechanical check binds a diff to the test categories it owes. Would be created by ADR-0011's migration as a recorded gap | recorded; building one is a separate human decision (Phase 9 brief §24) |

---

## 13. Retirement-readiness verdict

```text
NOT READY FOR PHASE 14 — SPEC KIT TREE DELETION
```

**Exact blockers:**

1. **BL-13-1 — D-11-2 unmigrated.** `.specify/memory/constitution.md` §Required test categories,
   §Which change requires which category and §Coverage are stated in no current authority. Deleting
   `.specify/**` today would lose a binding engineering-baseline requirement. This is precisely the
   condition §14 of the Phase 13 brief names: *"all replacement content needed for retirement exists
   under current authority."* It does not yet.
2. **BL-13-3 — the placed ADR-0011 misstates its own source.** It says *"sixteen named categories"*
   in four places where the constitution's table has **fifteen** rows. It should be corrected before
   it is considered for acceptance.

**BL-13-2 is closed:** ADR-0011 now exists at
`docs/adr/0011-required-test-categories-baseline.md` with status `Proposed`, and is indexed. What
remains is **acceptance**, which is a human act, and the migration that acceptance would authorize.

Everything else the brief requires is met: ADR-0010 exists and is Accepted; the Phase 12 count is
reconciled; B12-2 is closed; D-11-1 is closed; D-11-3 is closed; no current authority or active
dependency points to Spec Kit; historical records are preserved; and no application, database,
migration, LangGraph or architecture behaviour changed.

**`.specify/**` and `specs/**` were not deleted, and must not be deleted while BL-13-1 stands.**

---

## 14. Recommendation for Phase 14

Phase 14 is **not** the deletion phase as previously planned. In order:

1. **Human — place and decide ADR-0011.** Put the drafted record at
   `docs/adr/0011-required-test-categories-baseline.md`, add its row to `docs/adr/README.md`, and
   either accept it (status → `Accepted`) or reject it. Rejecting it is a legitimate outcome, but it
   must then be an explicit decision that the test-category matrix is **dropped**, recorded as such —
   not a silent loss through deletion.
2. **Human — close B13-4** by correcting ADR-0010's status in `docs/adr/README.md` and moving the row
   after 0009.
3. **If ADR-0011 is accepted:** migrate the three blocks into `.claude/rules/40-testing.md`, carrying
   the recorded coverage exception across unrepaired, pointing the frontend row at `23-angular.md`
   FE-NG-5/FE-NG-6 rather than restating it, and recording **EG-10**. Re-run
   `python .claude/hooks/test_guards.py`; add a check asserting the categories and the matrix are
   present, which raises the total above 611.
4. **Then Phase 15 — deletion**, using the manifest in §15.
5. **Separately, and not blocking deletion: B13-2.** A dedicated citation-repointing phase for the
   ~289 remaining `constitution §X` attributions in `dotnet/**`, `ragcore/**`, `integrations/**`,
   `build/**` and the non-desktop workflows. It is not a deletion blocker — every one of those
   requirements was migrated in Phase 9 from the YAML packs, so nothing is lost — but the pointers go
   stale the moment the constitution is deleted, and `CLAUDE.md` §10 should be corrected to describe
   the real scope.

---

## 15. Phase 14/15 deletion manifest — prepared, **not executed**

Listed for the deletion phase. **Nothing in this section was performed.** It is valid only once
BL-13-1 and BL-13-2 are closed.

### 15.1 `.specify/**` — 20 tracked files, all deletable

```text
.specify/.gitignore
.specify/init-options.json
.specify/integration.json
.specify/integrations/claude.manifest.json
.specify/integrations/speckit.manifest.json
.specify/memory/.constitution-template.json
.specify/memory/constitution.md          <-- ONLY after ADR-0011 is accepted and migrated
.specify/scripts/powershell/check-prerequisites.ps1
.specify/scripts/powershell/common.ps1
.specify/scripts/powershell/create-new-feature.ps1
.specify/scripts/powershell/resolve-template.ps1
.specify/scripts/powershell/setup-plan.ps1
.specify/scripts/powershell/setup-tasks.ps1
.specify/templates/checklist-template.md
.specify/templates/constitution-template.md
.specify/templates/plan-template.md
.specify/templates/spec-template.md
.specify/templates/tasks-template.md
.specify/workflows/speckit/workflow.yml
.specify/workflows/workflow-registry.json
```

### 15.2 `specs/**` — 24 tracked files, all deletable

```text
specs/001-platform-scaffold/checklists/architecture.md
specs/001-platform-scaffold/checklists/implementation.md
specs/001-platform-scaffold/checklists/requirements.md
specs/001-platform-scaffold/contract-freeze.md
specs/001-platform-scaffold/contracts/README.md
specs/001-platform-scaffold/contracts/customer-api.md
specs/001-platform-scaffold/contracts/integrations-api.md
specs/001-platform-scaffold/contracts/notifications.md
specs/001-platform-scaffold/contracts/read-views.md
specs/001-platform-scaffold/contracts/sample-flows.md
specs/001-platform-scaffold/contracts/staff-api.md
specs/001-platform-scaffold/contracts/triggers.md
specs/001-platform-scaffold/contracts/workload-api.md
specs/001-platform-scaffold/data-model.md
specs/001-platform-scaffold/implementation-freeze.md
specs/001-platform-scaffold/plan.md
specs/001-platform-scaffold/quickstart.md
specs/001-platform-scaffold/research.md
specs/001-platform-scaffold/spec.md
specs/001-platform-scaffold/stage-1-notes.md
specs/001-platform-scaffold/stage-2-notes.md
specs/001-platform-scaffold/stage-4-notes.md
specs/001-platform-scaffold/stage-6-notes.md
specs/001-platform-scaffold/tasks.md
```

All 24 are **Duplicate** or **Historical snapshot** per §5 and §7. None holds a unique current
requirement.

### 15.3 References that are intentionally historical — leave unchanged

| Path | Why it stays |
|---|---|
| `docs/migration/phase-{2,7,8,9,10,11,12,13}*.md` | the migration history itself |
| `docs/adr/0002,0004,0006,0008,0009,0010` | historical records; `70-adr.md` §70.6 forbids rewording them |
| `docs/architecture/integrations-service-delta.md` | non-authoritative by `00-authority.md` §00.2; a dated delta record |
| `docs/current-implementation/file-map.md` | non-authoritative by `00-authority.md` §00.2 |
| `.claude/hooks/test_guards.py` (4 `speckit-` mentions) | the negative assertions that keep Spec Kit out |
| `.claude/rules/00-authority.md` §00.4 | names both trees non-authoritative **by path** — it must keep naming them |

### 15.4 Files Phase 14/15 must update as part of the deletion

Each contains a live textual reference that becomes a dangling pointer once the trees are gone. None
is an authority statement; none affects behaviour.

| File | Reference | Action |
|---|---|---|
| `.dockerignore:86` | `specs/` | remove the entry |
| `README.md` | points at `specs/.../tasks.md §Deferred` as the omissions register | repoint to `docs/functional/implemented.md` (D-11-3 proves it is the same information) |
| `CLAUDE.md` §10 | describes `.specify/**` / `specs/**` as "pending a later retirement phase" | rewrite as completed history; also correct the B13-2 scope error |
| `.claude/rules/00-authority.md` §00.4 | names both trees | keep the names, change "remain in the tree pending a later retirement phase" to past tense |
| `.claude/rules/22-web-typescript.md` ×2, `23-angular.md:102` | cite `.specify/memory/constitution.md` and `specs/.../plan.md` as retiring migration input | change to "the retired constitution", no path |
| `.claude/rules/70-adr.md`, `90-functional-knowledge.md`, `.claude/skills/adr-author/SKILL.md` | list the trees among non-authoritative sources | keep the exclusion, drop the "remain in the tree" wording |
| `.claude/hooks/test_guards.py` | asserts the live mentions deny authority | update the assertions to the post-deletion shape; **do not weaken them** |
| `.serena/memories/core.md:38` | "retired Spec Kit trees. History only." | change to past tense |
| `apps/desktop/src/main/endpoint-execution-boundary.ts:59` | **runtime error message** citing `specs/.../plan.md Stage 4 non-goals` | repoint to `FE-EL-11` / ADR-0004. It is a thrown `Error` message — non-functional text, but confirm the desktop suite's assertions before changing |
| `ragcore/workers/{expiry_sweep,ingestion_run,integration_result_worker,outbox_dispatch,resume_worker,retention_sweep}.py`, `integrations/workers/command_consumer.py` | 7 `NotImplementedError` messages saying "see `specs/.../tasks.md`" | repoint to `docs/functional/implemented.md` §9.4 |
| `ragcore/src/ragcore/api/customer/sample_flows.py:119` | docstring cites task `T241` in `tasks.md` | drop the task id, keep the behaviour description |
| `build/infra/apim/apis.json:8`, `build/infra/messaging/queues.json:5` | historical narrative ("until this file existed it lived only in prose at …") | rewrite as history without the path, or leave — decide explicitly |
| `build/contracts/ragcore/customer.v1.openapi.json:435` | **GENERATED** — text originates in a RagCore docstring | **do not hand-edit.** Fix the source docstring and regenerate via the contracts pipeline |
| `docs/adr/README.md` | "Writing a new record" section cites "constitution Principle V/VI" and "the constitution states unconditionally" | repoint to `.claude/rules/**`; this is the index, not a historical record |

### 15.5 Validation that must pass after deletion

```bash
python .claude/hooks/test_guards.py          # expect the new total, all passing
cd apps/desktop && npm run typecheck && npm run lint && npx vitest run
cd apps/web     && npx eslint . && npx prettier --check . && npm test
cd dotnet       && dotnet build && dotnet test
cd ragcore      && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q
cd integrations && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q
bash build/scripts/check-boundaries.sh
```

Plus: `git grep -n -I -E "\.specify|specs/001-platform-scaffold"` returns **only** the intentionally
historical paths in §15.3; and the contracts pipeline regenerates `build/contracts/**` byte-identically.

---

## 16. Change inventory for this phase

41 files modified, one of them the ADR index. No file added, deleted, renamed or moved by Phase 13; `docs/adr/0011-required-test-categories-baseline.md` was added by the repository owner in `6e43a51`.

| Area | Files | Nature |
|---|---|---|
| `apps/desktop/**` | 13 | comments, JSDoc, ESLint `message:` strings, test docstrings |
| `apps/web/**` | 23 | comments, JSDoc, `describe()` labels, assertion messages, README prose |
| `.github/workflows/desktop.yml` | 1 | header comment |
| `dotnet/src/**` | 2 | XML doc comments |
| `ragcore/tests/contracts/test_api_surface.py` | 1 | module docstring |
| `.claude/hooks/test_guards.py` | 1 | ADR fixture constants re-anchored `0010 → 0011 → 0012`, `9 → 10 → 11` (twice: once for ADR-0010, once after the owner placed ADR-0011) |
| `docs/adr/README.md` | 1 | index row added for ADR-0011 (`70-adr.md` §70.6); no status changed |

Not modified: `.specify/**`, `specs/**`, `docs/architecture/**`, `docs/functional/implemented.md`,
`docs/adr/**`, `.claude/rules/**`, `.claude/skills/**`, `.claude/settings.json`,
`.claude/hooks/{db_migration_guard,langgraph_change_guard,adr_structure_guard}.py`,
`build/contracts/**`, `ragcore/migrations/**`, `ragcore/src/ragcore/graph/**`, any Dockerfile, any
Container Apps manifest.
