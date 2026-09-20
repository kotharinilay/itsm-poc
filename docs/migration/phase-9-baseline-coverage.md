# Phase 9 — Engineering baseline migration coverage

**This is the authoritative Phase 9 migration record.** It is the mapping from every authoritative
baseline requirement to its representation in `.claude/rules/`, with honest enforcement status.

It is a **migration record**, not authority. The operative baseline is `.claude/rules/`
(`.claude/rules/00-authority.md` §00.3). This document exists so an auditor can answer two
questions: *where did this Claude rule come from?* and *where is this baseline requirement
represented?*

| | |
|---|---|
| **Phase** | 9 — complete engineering baseline migration (blockers B-1, B-2) |
| **Revision audited** | `aac8351da1a1d77aef9c3d13ba2a658e9d1cfb00` — *fix(governance): worktree-aware path normalization for H2/H3/H5 (phase 8)* |
| **Branch** | `speckit-to-claude` |
| **Repository content established by** | `git ls-files` (generated and untracked residue excluded) |
| **Predecessors** | `docs/migration/phase-2-authority-model.md`, `docs/migration/phase-2-coverage-matrix.md`, `docs/migration/phase-7-validation.md`, `docs/migration/phase-8-worktree-guard.md` |

> **Amended by Phase 10.** `docs/migration/phase-10-baseline-reconciliation.md` records an
> explicit human decision that resolved conflict **CF-1** / decision **UD-3**. The `BL-10` row in
> §3.7, the enforcement roll-up in §5.2, the semantic-preservation roll-up in §4, and §9.1 / §9.3
> below are updated in place to reflect it. **The requirement count is unchanged at 167** — the
> amendment rewords one item, it does not add or remove one. Everything else in this document is
> the Phase 9 record as written.

---

## 1. Inputs

Exactly six authoritative sources were used. Nothing else was treated as baseline authority.

### 1.A Structured engineering rule packs (repository root)

| File | Category | Scope declared by the file itself | Keyed IDs |
|---|---|---|---|
| `principles.yaml` | `principles` | language-agnostic by construction | 32 |
| `dotnet.yaml` | profile/toolchain | `applied_when: language in [dotnet, csharp]` | 12 |
| `dotnet_lang.yaml` | language rules | `applied_when: language in [dotnet, csharp]` | 37 |
| `python.yaml` | profile/toolchain | `applied_when: language == python` | 9 |
| `python_lang.yaml` | language rules | `applied_when: language == python` | 25 |
| | | **total keyed** | **115** |

### 1.B Explicit baseline block

`docs/migration/phase-9-baseline-input.md` — the exact `<baseline-rules>` block supplied for this
migration, unavailable to Phase 2 (`OQ-1`) and to Phase 7 (blocker `B-2`), **available and treated
as authoritative here**.

It contains **39 items**, none of which carries an ID in the source. Phase 9 assigns the stable
migration identifiers **`BL-01`…`BL-39`** in source order. Those identifiers live in this document
and in the rule files; **they are not written back into the source block**, and no ID was invented
inside any source YAML.

### 1.C What was NOT used as baseline authority

`.specify/**`, `specs/**`, `.serena/**`, `README.md`, `Synthia-Platform-Specification.md`,
`docs/current-implementation/**`, the retired Spec Kit constitution, `docs/adr/0001`…`0009`,
`docs/architecture/integrations-service-delta.md`, `docs/architecture/ragcore-langgraph-flow.md`,
the existing repository configuration, and general engineering knowledge. A1/A2/A3 remain
authoritative **for architecture** and were consulted only as such.

---

## 2. Inventory — reconciling 115, 128 and 39

Phase 2 recorded **128 rules**. Phase 7 established that the YAML files carry only **115 explicitly
keyed IDs**, and that the difference is unkeyed toolchain/baseline entries promoted into matrix
rows. Phase 9 reproduces that arithmetic exactly and **preserves the distinction**.

| Component | Count | What it is |
|---|---|---|
| Keyed YAML rules | **115** | every entry carrying an explicit `id:` field |
| Unkeyed `toolchain.*` entries | **11** | 6 in `python.yaml`, 5 in `dotnet.yaml` — real requirements with no `id:` |
| Unkeyed `baseline:` values | **2** | `python.yaml` → `py312`; `dotnet.yaml` → `net10.0` |
| **Phase 2 matrix total** | **128** | 115 + 11 + 2 |
| Explicit baseline-block items | **39** | `BL-01`…`BL-39`, newly available in Phase 9 |
| **Phase 9 total accounted for** | **167** | 128 + 39 |

Verified per table against `docs/migration/phase-2-coverage-matrix.md`: `principles.yaml` 32,
`dotnet.yaml` 18 (12 + 5 + 1), `dotnet_lang.yaml` 37, `python.yaml` 16 (9 + 6 + 1),
`python_lang.yaml` 25 — **128**.

> **"128" is not shorthand for "115 YAML IDs."** The 13 additional rows are unkeyed entries, and
> they are carried through this migration as first-class requirements, marked `UNKEYED` in the
> matrices below.

---

## 3. Applicability matrix

Scope is taken from the authoritative source text and the repository context — **never inferred
from the existence of a similar concept in another language** (Phase 9 brief §5, §6).

Scope vocabulary used: `language-independent`, `.NET / C#`, `Python`, `TypeScript / Angular`,
`Electron`, `repository/process`, `documentation`, `architecture/governance`, `database`,
`deployment/runtime`.

Enforcement vocabulary: `mechanical`, `partial`, `procedural`, `currently-unenforced`,
`not-applicable` — defined in §5.

### 3.1 `principles.yaml` — 32 rules, all `language-independent`

Every rule below applies to **all** stacks, including `apps/web` and `apps/desktop`, because
`principles.yaml` is language-agnostic by construction. Destination for all: `10-principles.md`.

| Source rule ID | Requirement | Scope | Destination | Enforcement | Status | Semantic preservation | Notes |
|---|---|---|---|---|---|---|---|
| principles#P1 | Single reason to change | language-independent | `10-principles.md` P-1 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P2 | Open/closed | language-independent | `10-principles.md` P-2 | procedural | MIGRATED_TO_RULE | preserved | — |
| principles#P3 | Substitutability | language-independent | `10-principles.md` P-3 | procedural | MIGRATED_TO_RULE | preserved | — |
| principles#P4 | Interface segregation | language-independent | `10-principles.md` P-4 | procedural | MIGRATED_TO_RULE | preserved | — |
| principles#P5 | Dependency inversion | language-independent | `10-principles.md` P-5 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| principles#P6 | One authoritative representation | language-independent | `10-principles.md` P-6 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P7 | Simplicity | language-independent | `10-principles.md` P-7 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P8 | No speculative capability | language-independent | `10-principles.md` P-8 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P9 | Tell, don't ask | language-independent | `10-principles.md` P-9 | procedural | MIGRATED_TO_RULE | preserved | — |
| principles#P10 | Composition over inheritance | language-independent | `10-principles.md` P-10 | procedural | MIGRATED_TO_RULE | preserved | — |
| principles#P11 | Fail fast | language-independent | `10-principles.md` P-11 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P12 | Law of Demeter | language-independent | `10-principles.md` P-12 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP | preserved | EG-7 |
| principles#P13 | Separation of concerns | language-independent | `10-principles.md` P-13 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| principles#P14 | Least astonishment | language-independent | `10-principles.md` P-14 | procedural | MIGRATED_TO_RULE | preserved | — |
| principles#P15 | Command/query separation | language-independent | `10-principles.md` P-15 | procedural | MIGRATED_TO_RULE | preserved | — |
| principles#P16 | Single level of abstraction | language-independent | `10-principles.md` P-16 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P17 | Least privilege | language-independent | `10-principles.md` P-17 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved — Phase 7 narrowing corrected; restored to repository-wide scope | restored |
| principles#P18 | Information hiding | language-independent | `10-principles.md` P-18 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P19 | Program to an interface | language-independent | `10-principles.md` P-19 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P20 | Illegal states unrepresentable | language-independent | `10-principles.md` P-20 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P21 | Idempotent retryable operations | language-independent | `10-principles.md` P-21 | procedural | MIGRATED_TO_RULE | preserved | — |
| principles#P22 | Leave it cleaner | language-independent | `10-principles.md` P-22 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP | preserved | EG-8 |
| principles#P23 | Convention over configuration | language-independent | `10-principles.md` P-23 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P24 | High cohesion, low coupling | language-independent | `10-principles.md` P-24 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| principles#P25 | Immutable by default | language-independent | `10-principles.md` P-25 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P26 | Explicit injected dependencies | language-independent | `10-principles.md` P-26 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| principles#P27 | Externalized configuration | language-independent | `10-principles.md` P-27 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| principles#P28 | Stateless services | language-independent | `10-principles.md` P-28 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P29 | Logs as an event stream | language-independent | `10-principles.md` P-29 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P30 | No swallowed errors | language-independent | `10-principles.md` P-30 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| principles#P31 | Deterministic resource release | language-independent | `10-principles.md` P-31 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| principles#P32 | Explicit contracts | language-independent | `10-principles.md` P-32 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |

### 3.2 `dotnet.yaml` — 18 rows (12 keyed + 5 unkeyed toolchain + 1 unkeyed baseline)

Scope for every row: **`.NET / C#`** — except `P-DN-4`, `P-DN-5` and `P-DN-6`, which state
conventions identical to their Python counterparts and are therefore `repository/process` and
`documentation` (see §3.6).

| Source rule ID | Requirement | Scope | Destination | Enforcement | Status | Semantic preservation | Notes |
|---|---|---|---|---|---|---|---|
| dotnet.yaml#baseline *(unkeyed)* | .NET baseline is net10.0 (LTS Nov 2025 - Nov 2028) | .NET / C# | `20-dotnet.md` §20.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| dotnet.yaml#toolchain.analyzers *(unkeyed)* | EnableNETAnalyzers=true + AnalysisLevel=latest-Recommended -> Directory.Build.props | .NET / C# | `20-dotnet.md` §20.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| dotnet.yaml#toolchain.formatter *(unkeyed)* | dotnet format, driven by a committed .editorconfig | .NET / C# | `20-dotnet.md` §20.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| dotnet.yaml#toolchain.style_in_build *(unkeyed)* | EnforceCodeStyleInBuild=true so IDExxxx rules run at build | .NET / C# | `20-dotnet.md` §20.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| dotnet.yaml#toolchain.warnings *(unkeyed)* | TreatWarningsAsErrors=true; CodeAnalysisTreatWarningsAsErrors not set false | .NET / C# | `20-dotnet.md` §20.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED + DEVIATION | preserved | DV-7 |
| dotnet.yaml#toolchain.packages *(unkeyed)* | ManagePackageVersionsCentrally=true; Directory.Packages.props is the single version source | .NET / C# | `20-dotnet.md` §20.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| dotnet.yaml#P-DN-S1 | <Nullable>enable</Nullable> (realizes DN6) | .NET / C# | `20-dotnet.md` §20.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| dotnet.yaml#P-DN-S2 | <TreatWarningsAsErrors>true</TreatWarningsAsErrors> (realizes DN7) | .NET / C# | `20-dotnet.md` §20.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| dotnet.yaml#P-DN-S3 | <EnableNETAnalyzers> + <AnalysisLevel> (realizes DN23) | .NET / C# | `20-dotnet.md` §20.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| dotnet.yaml#P-DN-S4 | <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild> | .NET / C# | `20-dotnet.md` §20.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved — the switch itself is migrated verbatim; its `realizes` pointer is defective | D-1 |
| dotnet.yaml#P-DN-S5 | <Deterministic> + <ContinuousIntegrationBuild> (CI only), reproducible builds | .NET / C# | `20-dotnet.md` §20.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| dotnet.yaml#P-DN-1 | PascalCase types+files; _camelCase private fields; one top-level type per file | .NET / C# | `20-dotnet.md` §20.11 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved — 'one top-level type per file' has no analyzer and is review-gated | — |
| dotnet.yaml#P-DN-1b | Consistent whitespace, brace and using-directive ordering | .NET / C# | `20-dotnet.md` §20.11 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| dotnet.yaml#P-DN-2 | tests/ parallel to src/; <Project>.Tests; Method_State_Expected | .NET / C# (tests) | `40-testing.md` §40.2 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| dotnet.yaml#P-DN-3 | Test projects inherit the same strictness as src (no relaxed ruleset) | .NET / C# (tests) | `40-testing.md` §40.2 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| dotnet.yaml#P-DN-4 | Commits / versioning: Conventional Commits + SemVer | repository/process (language-independent) | `10-principles.md` §10.5 C-1, C-2 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP | preserved — DROPPED RULE RECOVERED (Phase 7 §4.3); the convention itself is now stated | EG-1 |
| dotnet.yaml#P-DN-5 | ADR: MADR in docs/adr/, sequential numbering, status field | architecture/governance (language-independent) | `10-principles.md` §10.5 C-6 -> `70-adr.md` | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved and strengthened — four-digit kebab filenames, closed status vocabulary, human-acceptance gate | — |
| dotnet.yaml#P-DN-6 | README / docs: Diataxis; C4 diagrams; quickstart + ADR pointer | documentation (language-independent) | `10-principles.md` §10.5 C-3, C-4, C-5 | procedural | MIGRATED_TO_RULE | preserved — DROPPED RULE RECOVERED (Phase 7 §4.3) | — |

### 3.3 `dotnet_lang.yaml` — 37 rules, all `.NET / C#`

**None of these has a Python, TypeScript, Angular or Electron equivalent unless an authoritative
source establishes one, and no such equivalent was manufactured** (Phase 9 brief §6; see
`21-python.md` §21.9 for the explicit non-equivalence list). Destination for all: `20-dotnet.md`.

| Source rule ID | Requirement | Scope | Destination | Enforcement | Status | Semantic preservation | Notes |
|---|---|---|---|---|---|---|---|
| lang/dotnet#DN1 | DateTimeOffset.UtcNow / TimeProvider; never DateTime.Now | .NET / C# | `20-dotnet.md` DN-1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED + DEVIATION | preserved | DV-3 |
| lang/dotnet#DN2 | await Task.Delay, never Thread.Sleep | .NET / C# | `20-dotnet.md` DN-2 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/dotnet#DN3 | ILogger, never Console.WriteLine | .NET / C# | `20-dotnet.md` DN-3 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED + DEVIATION | preserved | DV-3 |
| lang/dotnet#DN4 | Await; never .Result / .Wait() / .GetAwaiter().GetResult() | .NET / C# | `20-dotnet.md` DN-4 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/dotnet#DN5 | async Task, not async void | .NET / C# | `20-dotnet.md` DN-5 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP | preserved | EG-3 |
| lang/dotnet#DN6 | Nullable reference types enabled project-wide | .NET / C# | `20-dotnet.md` DN-6 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/dotnet#DN7 | Treat warnings as errors | .NET / C# | `20-dotnet.md` DN-7 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED + DEVIATION | preserved | DV-7 |
| lang/dotnet#DN8 | ConfigureAwait(false) in library code | .NET / C# | `20-dotnet.md` DN-8 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP + DEVIATION | preserved | DV-1 / UD-2 |
| lang/dotnet#DN9 | Forward the CancellationToken to every async callee | .NET / C# | `20-dotnet.md` DN-9 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/dotnet#DN10 | Catch specific exception types; never swallow | .NET / C# | `20-dotnet.md` DN-10 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/dotnet#DN11 | Seal classes not designed for inheritance | .NET / C# | `20-dotnet.md` DN-11 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN12 | Properties, not visible instance fields | .NET / C# | `20-dotnet.md` DN-12 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN13 | System.Text.Json for new serialization | .NET / C# | `20-dotnet.md` DN-13 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP + DEVIATION | preserved | DV-3 / EG-2 |
| lang/dotnet#DN14 | Bind config to IOptions<T>; no IConfiguration["..."] | .NET / C# | `20-dotnet.md` DN-14 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP + DEVIATION | preserved | DV-3 / EG-2 |
| lang/dotnet#DN15 | Dispose owned IDisposable resources | .NET / C# | `20-dotnet.md` DN-15 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN16 | Validate arguments at public boundaries | .NET / C# | `20-dotnet.md` DN-16 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED + DEVIATION | preserved | DV-6 |
| lang/dotnet#DN17 | Return IReadOnlyList<T>/IEnumerable<T> from public APIs | .NET / C# | `20-dotnet.md` DN-17 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN18 | Specify StringComparison / IFormatProvider | .NET / C# | `20-dotnet.md` DN-18 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN19 | No unstructured control flow (goto) | .NET / C# | `20-dotnet.md` DN-19 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP | preserved | EG-4 |
| lang/dotnet#DN20 | Records / readonly structs for value types | .NET / C# | `20-dotnet.md` DN-20 | procedural | MIGRATED_TO_RULE | preserved | — |
| lang/dotnet#DN21 | Every suppression is scoped and justified | .NET / C# | `20-dotnet.md` DN-21 | procedural | MIGRATED_TO_RULE | preserved — Phase 7 loss corrected; the engineering requirement is now stated alongside the governance gate. Source text recovered from raw YAML (defect D-3) | EG-5 / D-3 |
| lang/dotnet#DN22 | [LibraryImport] over [DllImport] | .NET / C# | `20-dotnet.md` DN-22 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN23 | Enable .NET analyzers; pin AnalysisLevel | .NET / C# | `20-dotnet.md` DN-23 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/dotnet#DN24 | Parameterize all SQL | .NET / C# | `20-dotnet.md` DN-24 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN25 | No weak or broken cryptographic algorithms | .NET / C# | `20-dotnet.md` DN-25 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN26 | Rethrow preserving the stack; never throw ex; | .NET / C# | `20-dotnet.md` DN-26 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED + DEVIATION | preserved | DV-5 |
| lang/dotnet#DN27 | Non-constant fields should not be visible | .NET / C# | `20-dotnet.md` DN-27 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN28 | Standard C# naming style | .NET / C# | `20-dotnet.md` DN-28 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/dotnet#DN29 | Enforce consistent formatting in the build | .NET / C# | `20-dotnet.md` DN-29 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/dotnet#DN30 | Constant log template with named placeholders | .NET / C# | `20-dotnet.md` DN-30 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN31 | LoggerMessage source generation on hot paths | .NET / C# | `20-dotnet.md` DN-31 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP + DEVIATION | preserved | DV-2 |
| lang/dotnet#DN32 | PascalCase structured-logging placeholders | .NET / C# | `20-dotnet.md` DN-32 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN33 | Concrete types where dispatch is provably avoidable | .NET / C# | `20-dotnet.md` DN-33 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN34 | Never disable TLS certificate validation | .NET / C# | `20-dotnet.md` DN-34 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN35 | No deprecated TLS/SSL protocol versions | .NET / C# | `20-dotnet.md` DN-35 | partial | MIGRATED_PARTIALLY_ENFORCED + DEVIATION | preserved | DV-4 |
| lang/dotnet#DN36 | Guard platform-specific APIs with an OS check | .NET / C# | `20-dotnet.md` DN-36 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED + DEVIATION | preserved | DV-5 |
| lang/dotnet#DN37 | Remove dead conditional code | .NET / C# | `20-dotnet.md` DN-37 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP + DEVIATION | preserved | DV-4 |

### 3.4 `python.yaml` — 16 rows (9 keyed + 6 unkeyed toolchain + 1 unkeyed baseline)

Scope for every row: **`Python`** — except `P-PY-4`, `P-PY-5` and `P-PY-6` (see §3.6).

| Source rule ID | Requirement | Scope | Destination | Enforcement | Status | Semantic preservation | Notes |
|---|---|---|---|---|---|---|---|
| python.yaml#baseline *(unkeyed)* | Python baseline is py312 (requires-python >= 3.12) | Python | `21-python.md` §21.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| python.yaml#toolchain.linter *(unkeyed)* | Ruff; select = [E,F,B,I,UP,S,PTH,SIM,ASYNC,DTZ] written explicitly | Python | `21-python.md` §21.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved and strengthened — `N` additionally selected, which the source contemplates | — |
| python.yaml#toolchain.formatter *(unkeyed)* | ruff format; quote-style double | Python | `21-python.md` §21.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED + DEVIATION | preserved — behaviour holds by Ruff default; the setting is not written explicitly | DV-8 |
| python.yaml#toolchain.import_sort *(unkeyed)* | Import sorting via Ruff `I`; no standalone isort | Python | `21-python.md` §21.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| python.yaml#toolchain.type_checker *(unkeyed)* | mypy --strict (or pyright strict), run as a CI gate | Python | `21-python.md` §21.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| python.yaml#toolchain.security *(unkeyed)* | Security linting via Ruff `S` (flake8-bandit); no separate Bandit run | Python | `21-python.md` §21.6 (+ `80-security-ops.md` §80.4) | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| python.yaml#toolchain.packaging *(unkeyed)* | PEP 621 [project] metadata + a committed pinned lockfile | Python | `21-python.md` §21.1 (+ `80-security-ops.md` §80.4) | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| python.yaml#P-PY-S1 | [tool.mypy] strict = true (realizes PY3) | Python | `21-python.md` §21.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| python.yaml#P-PY-S2 | select includes S, ASYNC, B, DTZ, PTH (realizes PY22) | Python | `21-python.md` §21.1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| python.yaml#P-PY-S3 | ruff check + ruff format --check as FAILING CI steps; no blanket ignore; suppression only via a justified per-line # noqa | Python | `21-python.md` §21.1 (+ `40-testing.md` §40.1) | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED + DEVIATION | preserved — `ignore = []` committed in both projects | DV-9 |
| python.yaml#P-PY-1 | snake_case modules+functions; PascalCase classes; PEP 8 | Python | `21-python.md` §21.7 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved and strengthened — `N` selected, making naming mechanical rather than reviewed | — |
| python.yaml#P-PY-2 | tests/ package; pytest; test_*.py; descriptive names | Python (tests) | `40-testing.md` §40.3 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| python.yaml#P-PY-3 | modern typing (list[int], X \| None); annotate public APIs | Python | `21-python.md` §21.2 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| python.yaml#P-PY-4 | Commits / versioning: Conventional Commits + SemVer | repository/process (language-independent) | `10-principles.md` §10.5 C-1, C-2 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP | preserved — DROPPED RULE RECOVERED (Phase 7 §4.3) | EG-1 |
| python.yaml#P-PY-5 | ADR: MADR in docs/adr/, sequential numbering, status field | architecture/governance (language-independent) | `10-principles.md` §10.5 C-6 -> `70-adr.md` | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved and strengthened | — |
| python.yaml#P-PY-6 | README / docs: Diataxis; C4 diagrams; quickstart + ADR pointer | documentation (language-independent) | `10-principles.md` §10.5 C-3, C-4, C-5 | procedural | MIGRATED_TO_RULE | preserved — DROPPED RULE RECOVERED (Phase 7 §4.3) | — |

### 3.5 `python_lang.yaml` — 25 rules, all `Python`

Destination for all: `21-python.md`.

| Source rule ID | Requirement | Scope | Destination | Enforcement | Status | Semantic preservation | Notes |
|---|---|---|---|---|---|---|---|
| lang/python#PY1 | No mutable default arguments | Python | `21-python.md` PY-1 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY2 | No bare except | Python | `21-python.md` PY-2 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY3 | Annotated public surface; strict type checker gates the build | Python | `21-python.md` PY-3 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY4 | Use logging; print is banned | Python | `21-python.md` PY-4 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP + DEVIATION | preserved | DV-10 / UD-5 |
| lang/python#PY5 | f-strings over % and str.format | Python | `21-python.md` PY-5 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY6 | assert is not runtime validation | Python | `21-python.md` PY-6 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY7 | pathlib.Path over os.path | Python | `21-python.md` PY-7 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY8 | No eval/exec on untrusted input | Python | `21-python.md` PY-8 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY9 | Resources acquired in a context manager | Python | `21-python.md` PY-9 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY10 | subprocess argument list, never shell=True on untrusted input | Python | `21-python.md` PY-10 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY11 | PEP 8 layout enforced by linter and formatter | Python | `21-python.md` PY-11 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY12 | No unused imports/variables, no undefined names | Python | `21-python.md` PY-12 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY13 | flake8-bugbear (B) family enabled | Python | `21-python.md` PY-13 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY14 | raise ... from when translating | Python | `21-python.md` PY-14 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY15 | No literal credentials in source | Python | `21-python.md` PY-15 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY16 | No unsafe deserialization of untrusted data | Python | `21-python.md` PY-16 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY17 | Explicit timeout on every outbound HTTP call | Python | `21-python.md` PY-17 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY18 | No weak hash algorithms in security contexts | Python | `21-python.md` PY-18 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY19 | No insecure temporary files | Python | `21-python.md` PY-19 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY20 | is / is not for None | Python | `21-python.md` PY-20 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY21 | Modern generic and union syntax (PEP 585/604) | Python | `21-python.md` PY-21 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY22 | Ruff adopted with an explicit selected set, running in CI | Python | `21-python.md` PY-22 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY23 | No blocking calls inside an async function | Python | `21-python.md` PY-23 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY24 | Timezone-aware datetimes only | Python | `21-python.md` PY-24 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| lang/python#PY25 | Parameterize SQL | Python | `21-python.md` PY-25 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved — gate is narrower than the rule (S608 is a string-shape heuristic, not full taint dataflow); recorded honestly as partial | — |

### 3.6 Consolidated language-independent conventions — the duplication decision

Six source rules are **three requirements stated twice**, once in each profile pack, word for word:

| Requirement | .NET source | Python source | Single destination |
|---|---|---|---|
| Conventional Commits + SemVer | `dotnet.yaml#P-DN-4` | `python.yaml#P-PY-4` | `10-principles.md` §10.5 **C-1**, **C-2** |
| MADR ADRs in `docs/adr/` | `dotnet.yaml#P-DN-5` | `python.yaml#P-PY-5` | `10-principles.md` §10.5 **C-6** → `70-adr.md` |
| Diátaxis + C4 + quickstart/ADR pointer | `dotnet.yaml#P-DN-6` | `python.yaml#P-PY-6` | `10-principles.md` §10.5 **C-3**, **C-4**, **C-5** |

Per Phase 9 brief §6 — *"when a language-independent requirement clearly applies to multiple stacks,
preserve it once as a common rule rather than duplicating unrelated variants"* — each is preserved
**once**, in the repository-wide file, carrying **both** source IDs. Duplicating them into
`20-dotnet.md` and `21-python.md` would have been a defect under the §21 coverage invariant.

**Placement decision.** `10-principles.md` is the repository-wide, language-independent rule file in
the target structure; §10.5 is a distinctly labelled section within it so that a convention is not
mistaken for one of the P1–P32 design principles. No new rule file was created, because the Phase 9
brief warns against creating content merely because a filename was proposed.

### 3.7 `docs/migration/phase-9-baseline-input.md` — 39 items, `BL-01`…`BL-39`

| Phase 9 ID | Requirement | Scope | Destination | Enforcement | Status | Semantic preservation | Notes |
|---|---|---|---|---|---|---|---|
| BL-01 | Application architecture / layering: Modular monolith | .NET / C#; architecture | `20-dotnet.md` §20.2 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| BL-02 | DI: constructor injection as the sole pattern via built-in MS DI / IServiceProvider; anti-patterns: Service Locator, BuildServiceProvider in configuration | .NET / C# | `20-dotnet.md` §20.2 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| BL-03 | Module composition: logical boundaries | .NET / C#; architecture | `20-dotnet.md` §20.2 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| BL-04 | API style and routing: REST / Minimal APIs | .NET / C# | `20-dotnet.md` §20.3 | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-05 | API versioning: URI segment | .NET / C# | `20-dotnet.md` §20.3 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-06 | OpenAPI / contract emission: code-first (built-in OpenApi) | .NET / C# | `20-dotnet.md` §20.3 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| BL-07 | Contract conventions: camelCase JSON; plural resource nouns; kebab-case multi-word segments; HTTP verbs carry the action | .NET / C# | `20-dotnet.md` §20.3 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-08 | Pagination keyset/cursor (opaque cursor + limit, stable monotonic ordering); typed query-string filters, no OData; ?sort=field / -field, whitelisted fields only | .NET / C# | `20-dotnet.md` §20.3 | procedural | MIGRATED_TO_RULE | **narrowed — source is truncated.** Every legible requirement is migrated in full; the offset/limit clause is unreadable in the source and could not be migrated | D-2 / UD-4 |
| BL-09 | Data access: EF Core 10 + Npgsql | .NET / C#; database | `20-dotnet.md` §20.4 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| BL-10 | Migrations: exactly one versioned migration mechanism, executed as a gated job in the CI/deploy step before revision activation, never at application startup; Alembic under `ragcore/migrations/`; the .NET deployable owns no migrations and applies no DDL | .NET / C#; Python; database; deployment/runtime | `20-dotnet.md` §20.4 + `50-database.md` §50.7 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | **amended by explicit human decision — Phase 10.** The EF attribution is withdrawn; the requirement it carried is preserved | CF-1 / UD-3 **CLOSED** — `phase-9-baseline-input.md` App. A.1 |
| BL-11 | Transaction and concurrency model: optimistic only, no lock anywhere | .NET / C#; database | `20-dotnet.md` §20.4 | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-12 | Isolation: Read Committed default, Serializable on invariant transactions | .NET / C#; database | `20-dotnet.md` §20.4 | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-13 | Data lifecycle: soft-delete + global query filter + audit columns | .NET / C#; database | `20-dotnet.md` §20.4 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-14 | Query conventions: AsNoTracking() on read paths; all queries parameterized; N+1 prevention; compiled queries | .NET / C#; database | `20-dotnet.md` §20.4 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-15 | Secrets: Key Vault refs via managed identity | deployment/runtime; repository-wide | `80-security-ops.md` §80.3 (+ `20-dotnet.md` §20.5) | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-16 | Configuration layering: appsettings.json -> appsettings.{Env}.json -> env vars -> ACA secretref env vars (last); later providers override earlier | .NET / C# | `20-dotnet.md` §20.5 | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-17 | Strongly-typed configuration: Options pattern with BindConfiguration + ValidateDataAnnotations + ValidateOnStart; raw string-key access banned | .NET / C# | `20-dotnet.md` §20.5 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP + DEVIATION | preserved — the ban is DN-14, whose gate is absent | DV-3 / EG-2 |
| BL-18 | Input validation: .NET 10 built-in validation | .NET / C# | `20-dotnet.md` §20.3 | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-19 | Error / result model: Result + exceptions, IExceptionHandler -> ProblemDetails | .NET / C# | `20-dotnet.md` §20.3 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-20 | Structured logging: Microsoft.Extensions.Logging + OTel | .NET / C# | `20-dotnet.md` §20.6 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| BL-21 | Telemetry: OTel + Azure Monitor Distro | .NET / C#; deployment/runtime | `20-dotnet.md` §20.6 | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-22 | Logger source-generation: LoggerMessage source-gen | .NET / C# | `20-dotnet.md` §20.6 | currently-unenforced | MIGRATED_ENFORCEMENT_GAP + DEVIATION | preserved — same rule as DN-31; CA1848 is bound to `suggestion` | DV-2 |
| BL-23 | Cancellation: propagate CancellationToken endpoint-down to every blocking I/O; honour at every awaitable boundary; never swallow OperationCanceledException | .NET / C# | `20-dotnet.md` §20.7 | mechanical | MIGRATED_AND_MECHANICALLY_ENFORCED | preserved | — |
| BL-24 | Context propagator: W3C Trace Context (OTel default); baggage limited to an explicit allowlist; no ad-hoc propagation headers | .NET / C# | `20-dotnet.md` §20.6 | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-25 | Health checks: /health/live (Predicate => false), /health/ready (tagged ready, incl. PostgreSQL), optional /health/startup | .NET / C#; deployment/runtime | `20-dotnet.md` §20.6 | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-26 | Middleware order: exception handler -> correlation -> request logging -> trace context -> auth -> validation -> endpoint | .NET / C# | `20-dotnet.md` §20.6 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-27 | Correlation IDs: X-Correlation-Id accepted if well-formed else generated; echoed on every response; bound into logging scope and OTel baggage | .NET / C# | `20-dotnet.md` §20.6 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-28 | Outbound resilience: Http.Resilience standard handler (Polly v8) | .NET / C# | `20-dotnet.md` §20.8 | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-29 | Idempotency: idempotency-key filter + Postgres store + outbound dedup keys | .NET / C#; database | `20-dotnet.md` §20.8 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-30 | Concurrency/consistency: async rules + Container Apps Jobs for singletons, no distributed lock | .NET / C#; deployment/runtime | `20-dotnet.md` §20.7 + `80-security-ops.md` §80.5 | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-31 | Outbound interceptor chain: DelegatingHandler chain via IHttpClientFactory, resilience innermost | .NET / C# | `20-dotnet.md` §20.8 | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-32 | Outbound HTTP clients: typed clients via IHttpClientFactory, one per adapter, base address + default headers at registration, pooled handler reuse, no manual new HttpClient() | .NET / C# | `20-dotnet.md` §20.8 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-33 | Outbox pattern: transactional outbox in PostgreSQL | .NET / C#; database | `20-dotnet.md` §20.8 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-34 | Transport / broker: Azure Service Bus Standard | deployment/runtime | `80-security-ops.md` §80.5 (+ `20-dotnet.md` §20.8) | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-35 | ACL / Adapter: port-and-adapter per dependency; port owned by the integrating module; implementation in module infrastructure | .NET / C#; architecture | `20-dotnet.md` §20.2 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-36 | Provider abstraction: one adapter per concrete provider; domain-shaped port only; no provider-neutral super-abstraction; swap later if a real second provider appears | .NET / C#; architecture | `20-dotnet.md` §20.2 | procedural | MIGRATED_TO_RULE | preserved | — |
| BL-37 | Container runtime: HTTP probes + explicit limits + 25s drain | deployment/runtime | `80-security-ops.md` §80.5 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |
| BL-38 | Build mode: .NET SDK container publish | deployment/runtime | `80-security-ops.md` §80.5 | not-applicable | NOT_APPLICABLE_WITH_REASON + CONFLICT | **preserved as written, not met by the implementation.** The repository uses a hand-written multi-stage Dockerfile; and BL-38 cannot be satisfied literally alongside BL-39 (no chiseled SDK image exists) | DV-11 / CF-2 |
| BL-39 | Dockerfile + base-image hardening: chiseled aspnet:10.0-noble base, multi-stage, non-root UID 1654, shell-less/no package manager, digest-pinned, read-only root fs where feasible, base-image policy documented in-repo | deployment/runtime | `80-security-ops.md` §80.5 | partial | MIGRATED_PARTIALLY_ENFORCED | preserved | — |

### 3.8 TypeScript / Angular / Electron

```text
TYPESCRIPT/ANGULAR/ELECTRON-SPECIFIC BASELINE NOT DEFINED
```

| Source | TS/Angular/Electron rules found |
|---|---|
| `principles.yaml` | none (language-agnostic; applies in full) |
| `dotnet.yaml`, `dotnet_lang.yaml` | none — scoped `language in [dotnet, csharp]` |
| `python.yaml`, `python_lang.yaml` | none — scoped `language == python` |
| `docs/migration/phase-9-baseline-input.md` | **none.** The block is .NET / data-access / observability / container-runtime scoped. The SPA client appears once (`BL-07`) as the *rationale* for .NET emitting camelCase JSON — a statement about the .NET contract, not a TypeScript rule. |

Destination: `.claude/rules/22-web-typescript.md`, which carries (a) the scope statement, (b) the
`principles.yaml` rules that apply in full, and (c) this finding. **No TypeScript baseline was
invented.** The existing `apps/web` and `apps/desktop` CI gates are recorded as
`EXISTING IMPLEMENTATION/REPOSITORY CONVENTION — NOT BASELINE AUTHORITY`. Open decision: **UD-1**.

---

## 4. Semantic preservation

Per-rule verdicts are the *Semantic preservation* column in §3. This is the roll-up. Anything other
than `preserved` is explained.

| Verdict | Count | Which |
|---|---|---|
| **preserved** | 160 | every rule not listed below |
| **preserved and strengthened** | 4 | `P-DN-5`, `P-PY-5` (ADR requirements strengthened by `70-adr.md`); `P-PY-1` and `python.yaml#toolchain.linter` (`N` selected, making naming mechanical) |
| **narrowed** | 1 | `BL-08` — explained below |
| **altered** | 0 | — |
| **missing** | 0 | — |
| **conflicting (migrated, not reconciled)** | 1 | `BL-38` — explained below and in §9 |
| **amended by explicit human decision (Phase 10)** | 1 | `BL-10` — the EF attribution withdrawn, the requirement preserved; §4.2 |
| **Total** | **167** | |

### 4.1 The one narrowing — `BL-08`

The source line reads, verbatim:

> *"Default: keyset/cursor pagination for large or growing collections … using an opaque cursor +
> limit, stable ordering by a monotonic key. **Offset/limitOutbound resilience pipeline**"*

The sentence describing offset/limit pagination is **truncated in the source and runs into the next
heading**. Whether offset/limit is permitted, and under what condition, cannot be read from the
authoritative text.

Everything legible — the keyset/cursor default, the opaque cursor + limit mechanism, stable
monotonic ordering, typed per-endpoint query-string filters, the explicit ban on a generic
OData-style expression language, and the `?sort=field` / `?sort=-field` whitelisted-fields grammar —
is migrated **in full** to `20-dotnet.md` §20.3.

**The truncated clause was not reconstructed, guessed, or filled from general knowledge.** Recorded
as defect **D-2**, decision **UD-4**.

### 4.2 The two conflicts — `BL-10` (closed), `BL-38` (open)

Both were migrated **as written** into the rule files in Phase 9, each carrying an explicit conflict
notice and an explicit statement of which rule governs in the meantime. Neither was silently
reconciled, and neither caused application code or a test to change.

**`BL-10` — closed in Phase 10 by explicit human decision.** The baseline input was amended to
withdraw the **EF attribution** while preserving the requirement the item actually carried: *one
versioned migration mechanism, executed as a gated job in the CI/deploy step, never at application
startup.* The amendment therefore changes the item's **mechanism attribution and abstraction
level**, not its obligation:

| | Before | After |
|---|---|---|
| Named mechanism | EF Migrations, produced as a bundle from the .NET side | Alembic, under `ragcore/migrations/` |
| Execution point | a CI/deploy step | a gated job in the CI/deploy step, **before revision activation**, never at application startup |
| Abstraction level | a .NET framework choice | a repository- and deployment-level rule about schema ownership and execution point |
| Scope | `.NET / C#`, database | `.NET / C#` (owns none), Python (owns it), database, deployment/runtime |
| Rule in force | `50-database.md` (the conflict notice said so) | `50-database.md` — **unchanged** |

The semantic scope is **narrowed in one respect and widened in another, deliberately**: the EF
requirement is withdrawn (narrowing), and the "never at application startup" and
"before revision activation" qualifiers — already binding under `50-database.md` §50.7 and
`80-security-ops.md` §80.6 — are now stated in the input too (widening the *text*, not the
*obligation*). No obligation that was in force before the amendment stopped being in force, and
none was newly created. Full record: `docs/migration/phase-9-baseline-input.md` Appendix A.1.

**`BL-38` — still open.** Conflict **CF-2**, decision **UD-6**. Unchanged by Phase 10. See §9.

### 4.3 Defects that could have caused silent loss

| Defect | Effect if unnoticed | Handling |
|---|---|---|
| **D-3** — `dotnet_lang.yaml:307` — `text: Every #pragma warning disable / SuppressMessage is scoped and carries a justification.` is **unquoted**, so a YAML parser truncates it at `#` to `"Every"` | DN-21 would have migrated as the single word "Every" — a total loss of the requirement | The full text was recovered from the **raw source line**, not the parsed value, and DN-21 is migrated complete. Defect recorded; **source not edited** |
| **D-1** — `dotnet.yaml#P-DN-S4` declares `realizes: lang/dotnet#DN19`, but DN19 is the `goto` rule; the switch actually realizes DN-28/DN-29 | A reader could conclude `goto` is build-enforced, or that formatting is not | Both DN-19 and DN-28/DN-29 are migrated in full and independently, so no requirement is lost either way. Pointer defect recorded; **source not edited** |

---

## 5. Enforcement

### 5.1 Vocabulary

| Label | Means | Evidence required |
|---|---|---|
| `mechanical` | a gate **fails the build or CI today** on a violation | the analyzer/lint rule is **selected or bound**, at a **failing severity**, in a committed config, **and** the gate runs |
| `partial` | a gate covers **part** of the rule, or covers it by a narrower mechanism than the source names | as above, for the covered part |
| `procedural` | no gate; the rule is applied by Claude and reviewed | — |
| `currently-unenforced` | the rule exists and the **current configuration does not enforce it** | verified absence |
| `not-applicable` | the rule does not apply, or cannot be applied as written | reason recorded |

> **"Mechanical" requires real evidence.** A rule was **not** marked mechanical because a related
> analyzer exists. `AnalysisLevel=latest-Recommended` switches the CA family *on*; it does not bind
> a per-rule severity. Where the source requires `severity = error` and `.editorconfig` does not
> bind it, the rule is `partial`, not `mechanical` — that distinction accounts for most of the
> `partial` rows in §3.3.

### 5.2 Roll-up

Counted directly from the §3 matrices — 167 rows, 167 distinct rule ids, no duplicates.

| Enforcement | Count | Share |
|---|---|---|
| `mechanical` | 79 | 47% |
| `partial` | 47 | 28% |
| `procedural` | 26 | 16% |
| `currently-unenforced` | 14 | 8% |
| `not-applicable` | 1 | 1% |
| **Total** | **167** | 100% |

The `mechanical` share is high because the Python stack is almost entirely gated by Ruff and mypy
(24 of 25 `lang/python#*` rules) and because the .NET strictness switches are all set. It is **not**
evenly distributed: 14 of the 37 `lang/dotnet#*` rules are `mechanical`, and 15 are `partial`
precisely because their CA severities are unbound (**DV-4**).

### 5.3 Re-verified enforcement claims (Phase 9 brief §15)

Phase 7 found the Phase 2 matrix overstated enforcement. Each named case was re-checked against the
committed configuration in this phase.

| Rule | Phase 2 matrix claimed | Verified in Phase 9 | Phase 9 records |
|---|---|---|---|
| `lang/dotnet#DN8` | `Y` — "CA2007 severity=error" | `dotnet/.editorconfig:84` → `dotnet_diagnostic.CA2007.severity = none` | **`currently-unenforced`**. Deliberate baseline relaxation, no ADR. **DV-1 / UD-2** |
| `lang/dotnet#DN31` | `Y` — "CA1848 severity=error" | `dotnet/.editorconfig:94` → `severity = suggestion` | **`currently-unenforced`**. A suggestion is **not** raised to an error by `TreatWarningsAsErrors`. **DV-2** |
| `lang/dotnet#DN16` | `Y` — "CA1062 severity=error" | `dotnet/.editorconfig:92` → `severity = warning` | **`mechanical`**, but by a different mechanism than the baseline states — build-failing only via `TreatWarningsAsErrors`. **DV-6** (low severity, mechanism fragility) |
| `lang/python#PY4` | `N` | `T20` absent from `select` in **both** `ragcore/pyproject.toml` and `integrations/pyproject.toml` | **`currently-unenforced`**, matrix was correct. **DV-10 / UD-5** |

**No configuration was changed to satisfy the baseline** (Phase 9 brief §13, §15). Every difference
is recorded as a deviation in §8.

### 5.4 Enforcement gaps

A rule needing a gate that does not exist. **None was built in this phase** (Phase 9 brief §24) —
building one is a separate human decision, and several would themselves be governance decisions.

| ID | Gap | Affects | What the source names |
|---|---|---|---|
| **EG-1** | No commit-message check and no release/versioning tooling | `C-1`, `C-2` (`P-DN-4`, `P-PY-4`) | "a commit-message CI check + release tooling" |
| **EG-2** | `Microsoft.CodeAnalysis.BannedApiAnalyzers` is not referenced in `dotnet/Directory.Packages.props`, and no `BannedSymbols.txt` exists | `DN-13`, `DN-14`, and C# credential literals | BannedApiAnalyzers RS0030 + `BannedSymbols.txt` |
| **EG-3** | `Microsoft.VisualStudio.Threading.Analyzers` not referenced | `DN-5` | VSTHRD100 at `severity = error` |
| **EG-4** | No custom Roslyn/structural check for `goto` | `DN-19` | a check failing on `GotoStatementSyntax`; the source states review is **not** acceptable here |
| **EG-5** | No analyzer requiring a non-empty `Justification` on `SuppressMessage` | `DN-21` | a custom analyzer, named as the "mechanical upgrade path" |
| **EG-6** | No Python dependency-vulnerability audit step in `.github/workflows/security.yml` (.NET, web and desktop each have one) | `80-security-ops.md` §80.4 | — (repository symmetry, not a named source rule) |
| **EG-7** | No lint or architecture check for graph-navigation call chains | `principles#P12` | "flag method-call chains that navigate beyond the immediate collaborator" |
| **EG-8** | No analyzer/lint warning-count baseline ratchet | `principles#P22` | "a warning-count baseline ratchet fails the build if a modified file introduces net-new warnings" |

`DN-1`, `DN-3` and `principles#P26` are **not** gaps: the source names BannedApiAnalyzers, which is
absent, but `dotnet/tests/Synthia.ArchitectureTests/BannedApiTests.cs` and
`ServiceResolutionTests.cs` enforce them as genuine build-failing gates. That substitution is
recorded as **DV-3** (mechanism differs from the source) with enforcement `mechanical`, because the
outcome the source requires is achieved.

---

## 6. Traceability

### 6.1 The mechanism

Phase 7 found **zero** baseline IDs referenced anywhere under `.claude/`
(`docs/migration/phase-7-validation.md` §4.4). That is corrected.

- Every rule migrated from a keyed YAML ID carries `Source: <original id>` in its rule file, using
  the source's own identifier verbatim — `principles#P17`, `lang/dotnet#DN8`, `lang/python#PY23`,
  `dotnet.yaml#P-DN-S4`, `python.yaml#toolchain.linter`.
- Every unkeyed toolchain/baseline entry carries its Phase 2 row identifier
  (`dotnet.yaml#toolchain.warnings`, `python.yaml#baseline`).
- Every baseline-block item carries its Phase 9 migration ID (`BL-01`…`BL-39`), mapped here in §3.7.
- The full original YAML structure is **not** embedded in any rule file; the identifier plus this
  document is the traceability mechanism.

### 6.2 The two audit questions

**"Where did this Claude rule originate?"** → the rule's own `Source:` line names the pack and ID.

**"Where is this original baseline requirement represented?"** → §3 above, one row per requirement,
naming the destination file and section.

### 6.3 Checkable

`.claude/hooks/test_guards.py` asserts the traceability invariants mechanically, so a future edit
cannot silently drop an ID:

- every one of the 115 keyed IDs, the 13 unkeyed row IDs and the 39 `BL-*` IDs appears in this
  document;
- every migrated baseline ID appears in at least one `.claude/rules/*.md` file;
- the language rule files declare their scope;
- the recovered rules (`Conventional Commits`, `SemVer`, `Diátaxis`, `C4`) are present as
  requirements;
- no `BL-*` ID was written back into a source YAML;
- the root `CLAUDE.md` names all three architecture documents, every rule file, and the four gates.

---

## 7. Dropped-rule recovery

Phase 7 §4.3 named four requirements as dropped. Each is recovered with its **actual engineering
content**, not merely as an ADR trigger.

| Dropped rule | Authoritative source located | Recovered to | Proof |
|---|---|---|---|
| **Conventional Commits** | `dotnet.yaml#P-DN-4` / `python.yaml#P-PY-4` — `default: "Conventional Commits + SemVer."`, citation `https://www.conventionalcommits.org/en/v1.0.0/` | `10-principles.md` §10.5 **C-1** | The commit-message grammar is stated in full: the `<type>[scope][!]: <description>` form, the conventional type set, `!` / `BREAKING CHANGE:` for breaking changes, and the description style |
| **SemVer** | same entries, `default` field | `10-principles.md` §10.5 **C-2** | `MAJOR.MINOR.PATCH` stated with the bump rule for each position, tied to the `feat`/`fix`/breaking commits of C-1 |
| **Diátaxis** | `dotnet.yaml#P-DN-6` / `python.yaml#P-PY-6` — `default: "Diataxis structure; C4 diagrams; quickstart + ADR pointer."`, citation `https://diataxis.fr/` | `10-principles.md` §10.5 **C-3** | The four document kinds are named and defined, with the instruction to declare which kind a document is |
| **C4** | same entries | `10-principles.md` §10.5 **C-4** | The four levels are named, with the instruction that a diagram states its level |
| *(same entries, third clause)* | quickstart + ADR pointer | `10-principles.md` §10.5 **C-5** | Stated as a README requirement |

**Why the previous placement failed, and why this one does not.** Phase 7's objection was precise:
`70-adr.md` §70.2 B(6) says *changing* a commit or versioning convention needs an ADR, but never
stated **what** the convention is — a gate with nothing behind it. And `90-functional-knowledge.md`
governs only `docs/functional/implemented.md`, a different document with a different purpose, so it
could never carry a general Diátaxis/C4 documentation requirement.

Both problems are structural, and both are fixed by placing the **requirement** in the
repository-wide rule file while leaving the **gate** where it was. Both now exist; neither
substitutes for the other.

### 7.1 The same correction, applied to two more Phase 7 findings

| Phase 7 finding | Correction |
|---|---|
| `principles#P17` (least privilege) survived only as the DB principal separation in `50-database.md` — a repository-wide principle narrowed to one domain instance | Restored to repository-wide in `10-principles.md` **P-17**, with the operational surfaces enumerated in `80-security-ops.md` §80.2 (code visibility, managed identity, Key Vault, Service Bus, container runtime, CI tokens, renderer privileges). `50-database.md` is now explicitly **one instance**, not the whole extent |
| `lang/dotnet#DN21` — the positive obligation (every suppression scoped and justified) was replaced by a meta-gate (an unjustified pragma requires an ADR) | Both are stated: the engineering requirement in `20-dotnet.md` **DN-21**, the governance gate unchanged in `70-adr.md` §70.2 B(4). `20-dotnet.md` DN-21 names the distinction explicitly |
| Language scoping unanchored — no file carried the scoping statement | Every language file opens with a **Scope** table naming the paths it governs and the paths it does not (`20-dotnet.md`, `21-python.md`, `22-web-typescript.md`), and states that no rule may be carried to another stack by analogy |
| No traceability — zero baseline IDs under `.claude/` | §6 above; mechanically asserted in `test_guards.py` |

---

## 8. Deviations

Implementation or configuration differing from the authoritative baseline, discovered during this
migration. Per Phase 9 brief §13 and `00-authority.md` §00.7: **recorded, baseline preserved,
nothing repaired, no rule downgraded, no application code touched.**

| ID | Deviation | Evidence | Baseline says | Severity |
|---|---|---|---|---|
| **DV-1** | `CA2007` disabled | `dotnet/.editorconfig:84` → `severity = none`, commented "off deliberately, not by oversight" | `DN-8`: `severity = error` for library projects | **High** — a deliberate baseline relaxation with no ADR, itself an ADR trigger (`70-adr.md` §70.2 B(1)). Decision **UD-2** |
| **DV-2** | `CA1848` is a suggestion, not an error | `dotnet/.editorconfig:94` | `DN-31` / `BL-22`: `severity = error` | Medium — rule unenforced |
| **DV-3** | `BannedApiAnalyzers` absent; the bans it should carry are enforced (where at all) by architecture tests instead | `dotnet/Directory.Packages.props` has no reference; `BannedApiTests.cs` exists | `DN-1`, `DN-3`, `DN-13`, `DN-14`: RS0030 + `BannedSymbols.txt` | Mixed — `DN-1`/`DN-3` are covered by the substitute; `DN-13`/`DN-14` are covered by nothing (**EG-2**) |
| **DV-4** | ~15 CA rules the source requires at `severity = error` are not bound in `.editorconfig` and rely on whatever `latest-Recommended` enables | `dotnet/.editorconfig` binds only CA2007, CA2016, CA1849, CA1031, CA1062, CA1848, CA1707 | `DN-11, 12, 15, 17, 18, 22, 24, 25, 27, 30, 32, 33, 34, 35, 37` | Medium — recorded as `partial`, not `mechanical` |
| **DV-5** | `CA2200` and `CA1416` are build-failing only because they default to *warning* under `TreatWarningsAsErrors`; the explicit `severity = error` the source asks for is absent | `dotnet/.editorconfig` | `DN-26`, `DN-36` | Low — outcome correct, determinism weaker |
| **DV-6** | `CA1062` bound to `warning`, not `error` | `dotnet/.editorconfig:92` | `DN-16`: `severity = error` | Low — enforced today, but silently stops if `TreatWarningsAsErrors` is ever scoped down |
| **DV-7** | Project-wide `<NoWarn>$(NoWarn);CS1591</NoWarn>` alongside `<GenerateDocumentationFile>true</GenerateDocumentationFile>` | `dotnet/Directory.Build.props` | `DN-21`: no file- or project-wide blanket disables; every suppression scoped and justified | Low–Medium — the one existing instance DN-21 reaches |
| **DV-8** | `quote-style` not written in either `[tool.ruff.format]` | `ragcore/pyproject.toml`, `integrations/pyproject.toml` | `python.yaml#toolchain.formatter`: `quote-style: double` emitted to `pyproject.toml` | Cosmetic — Ruff's default *is* `double`, so behaviour holds and `ruff format --check` gates it |
| **DV-9** | `per-file-ignores` entry beyond what the source sanctions: `"migrations/versions/*.py" = ["N999", "E501"]` | `ragcore/pyproject.toml` | `P-PY-S3`: never a blanket ignore; suppression only via a justified per-line `# noqa`. Adding to `per-file-ignores` is an ADR trigger (`70-adr.md` §70.2 B(2)) | Low — Alembic-generated module names are the stated reason; predates this migration |
| **DV-10** | `T20` absent from ruff `select` in both projects, so the `print` ban is unguarded | `ragcore/pyproject.toml`, `integrations/pyproject.toml` | `PY-4`: the source states `T20` **must be added to `select`** for the rule to fire | Medium. Decision **UD-5** |
| **DV-11** | The .NET image is built by a hand-written multi-stage Dockerfile, not `dotnet publish /t:PublishContainer` | `build/docker/dotnet.Dockerfile` | `BL-38`: ".NET SDK container publish" | Medium — but see **CF-2**: `BL-38` and `BL-39` cannot both be satisfied literally, and the Dockerfile states that reason inline |

**Deviations deliberately *not* acted on.** None of the above was repaired, and no test, analyzer
severity, lint selection or application file was changed to make a baseline claim true. Several
would be baseline changes requiring an ADR; the rest are the human decisions in §9.

---

## 9. Unresolved decisions, conflicts and defects

### 9.1 Genuine conflicts between authoritative sources

Per `00-authority.md` §00.6 and Phase 9 brief §22: **stopped, recorded, no winner chosen.**
Phase 10 closed **CF-1** — not by choosing a winner, but by a human amending the input that
was the outlier. **CF-2 remains open and unchosen.**

#### CF-1 — EF Migrations vs Alembic-owns-all-schema — **CLOSED (Phase 10)**

```text
STATUS: CLOSED by explicit human decision, Phase 10.
Closed by amending the baseline INPUT. No architecture changed. No rule in force changed.
No test, analyzer, configuration or application file was touched.
```

| | |
|---|---|
| **Source A (as recorded in Phase 9)** | `docs/migration/phase-9-baseline-input.md`, item `BL-10`: *"Migrations: EF Migrations bundle in CI/deploy step."* |
| **Source B** | `.claude/rules/50-database.md` §50.7 and **A2 §8.1**: Alembic under `ragcore/migrations/` is the single schema-migration mechanism; *"The .NET side owns **no** migrations"* |
| **Exact conflict** | A required an EF Migrations bundle produced and run from the .NET side. B forbids the .NET side from owning any migration at all. They could not both hold. |
| **Resolution** | **Source A amended.** The human decision supplied in the Phase 10 brief states that PostgreSQL schema migrations remain owned and executed by the Python/RagCore Alembic path, and that there is no requirement to move them into .NET/EF Core. The baseline block was amended accordingly — option (i) of UD-3. |
| **Which side won** | Neither was chosen by Claude. A human decided, and the decision confirmed the model **A2 and `50-database.md` already stated**. Phase 9's "in force meanwhile: B" is now simply "in force: B", with the input agreeing. |
| **Amendment record** | `docs/migration/phase-9-baseline-input.md` Appendix A.1 — original wording, replacement wording, reason, authority, classification, and the ADR determination |
| **Phase record** | `docs/migration/phase-10-baseline-reconciliation.md` |
| **ADR required?** | **No.** Assessed against every `70-adr.md` §70.2 trigger in Appendix A.2. The amendment introduces no architecture change and contradicts no migrated baseline rule — it removes a contradiction with one. |
| **Rule files updated** | `20-dotnet.md` `BL-10` (conflict notice → closure notice; `NoMigrationTests` still named as the live gate), `21-python.md` §21.9 (`BL-10` removed from the no-Python-counterpart list, since the amended item applies to `ragcore/**` directly), `50-database.md` §50.7 (closure note; **section text unchanged**) |
| **Decision** | **UD-3 — CLOSED** |

#### CF-2 — SDK container publish vs chiseled base image

| | |
|---|---|
| **Source A** | `BL-38`: *"Build mode: .NET SDK container publish."* |
| **Source B** | `BL-39`: production images use `mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled`, built **multi-stage** (SDK image builds, chiseled runtime image runs). |
| **Exact conflict** | Both are items of the *same* authoritative source. `dotnet publish /t:PublishContainer` produces an image from an SDK-resolved base; **Microsoft does not publish a chiseled SDK image**, so the literal SDK-publish path cannot produce the chiseled runtime image B mandates. B's own text acknowledges this by describing a multi-stage build. |
| **Affected stack** | deployment/runtime |
| **Impact** | Low operationally — the repository satisfies B and documents why in `build/docker/dotnet.Dockerfile`. The unresolved question is whether `BL-38` is superseded by `BL-39`, or describes a different artifact. |
| **Human decision required** | **UD-6** — confirm which of `BL-38` / `BL-39` governs, or restate `BL-38` as "SDK-publish semantics realized through a multi-stage Dockerfile". |

### 9.2 Editorial defects in authoritative sources

Not conflicts; not repaired here. `00-authority.md` §00.6: *"an editorial defect needs a human
editorial correction, not an ADR."*

| ID | Defect | Location | Consequence |
|---|---|---|---|
| **D-1** | `P-DN-S4` declares `realizes: lang/dotnet#DN19`, but DN19 is the `goto` rule; `EnforceCodeStyleInBuild` realizes DN-28/DN-29, as the pack's own inline comment says | `dotnet.yaml:77` | None to coverage — both rules migrated independently. Recorded in `20-dotnet.md` §20.1 |
| **D-2** | `BL-08`'s offset/limit sentence is truncated and runs into the next heading: *"Offset/limitOutbound resilience pipeline"* | `docs/migration/phase-9-baseline-input.md:17` | One requirement is unreadable and was **not** reconstructed. Decision **UD-4** |
| **D-3** | `DN21`'s `text:` scalar is unquoted and begins `Every #pragma warning disable …`, so a YAML parser truncates it at `#` to the single word `"Every"` | `dotnet_lang.yaml:307` | Would have silently destroyed the rule. Recovered from the raw source line; the *parsed* value is unusable for this entry |

### 9.3 Human decisions required

| ID | Decision | Blocks | Instrument |
|---|---|---|---|
| **UD-1** | TypeScript / Angular / Electron baseline: *principles-only*, *a separately supplied TS baseline*, or *deliberately ungoverned* | Blocker **B-4**; `22-web-typescript.md` beyond its current scope statement | Confirmation (option 1) or ADR (options 2, 3) |
| **UD-2** | `CA2007` / `DN-8`: accept the relaxation by ADR, or restore `severity = error` for library projects | DV-1 | ADR (`70-adr.md` §70.2 B(1)) or a configuration change |
| ~~**UD-3**~~ | ~~`BL-10` vs `50-database.md`/A2 schema ownership~~ — **CLOSED in Phase 10**: baseline block amended; Alembic/RagCore ownership confirmed; no ADR required | ~~CF-1~~ **closed** | Baseline-block amendment — taken |
| **UD-4** | The truncated `BL-08` offset/limit requirement | CF/D-2 | Editorial correction to the baseline block |
| **UD-5** | Whether to add `T20` to ruff `select`, making `PY-4` mechanical | DV-10 | A configuration change realizing the existing baseline (no ADR needed — it *strengthens* toward the baseline) |
| **UD-6** | `BL-38` vs `BL-39` build mode | CF-2, DV-11 | Editorial correction to the baseline block |
| **UD-7** | Whether to close any of the eight enforcement gaps **EG-1…EG-8**, and in what order | §5.4 | Each is a separate decision; some (EG-4, EG-5, EG-8) require building new analyzers/checks |

### 9.4 Carried forward, unchanged

- **OQ-5** (`docs/migration/phase-2-authority-model.md`) — whether A3's inline ADR-001…ADR-012 are
  authoritative as part of an authoritative document. `70-adr.md` §70.1 states the reading; the
  question remains open, and the two ADR numbering spaces must never be conflated.
- The conformance findings in `60-architecture-gates.md` §60.4 (graph state vocabulary vs A3 §6.2;
  EF Core / Alembic drift) — deferred, not resolved here.

---

## 10. Coverage invariant — verification

```text
Every authoritative baseline requirement
        v  has exactly one authoritative Claude representation
        v  with preserved semantics
        v  with explicit scope
        v  with traceability
        v  and honest enforcement status.
```

| Invariant clause | Status | How it is held |
|---|---|---|
| Every requirement represented | **held** — 167/167 | §3; mechanically asserted in `test_guards.py` |
| **Exactly one** representation (duplication is a defect) | **held** | §3.6 — the six duplicated profile rules are consolidated to three requirements in one file, carrying both source IDs. No rule text is duplicated between a rule file and a skill (`00-authority.md` §00.8) |
| Semantics preserved | **held**, with 1 narrowing and 2 conflicts explained | §4 |
| Explicit scope | **held** | Every rule file opens with a Scope table; every §3 row carries a Scope column |
| Traceability | **held** | §6 |
| Honest enforcement | **held** | §5, including the four re-verified Phase 7 cases in §5.3 |
| No cross-language equivalent invented | **held** | §3.3, §3.8; `21-python.md` §21.9 lists the explicit non-equivalences |
| Known dropped rules restored | **held** | §7 |
| Deviations recorded, not repaired | **held** | §8 — no configuration, test or application file changed |
| TypeScript baseline not invented | **held** | §3.8, `22-web-typescript.md` §22.1 |

### 10.1 Scoped duplication that is deliberate

Two cases where the same subject appears in more than one file. Neither is an independent
representation of the same rule:

1. **`principles#P17`** is stated once in `10-principles.md` P-17. `80-security-ops.md` §80.2
   enumerates the *operational surfaces* it reaches and explicitly does not restate it;
   `50-database.md` §50.7 is named as one instance. Unavoidable: a repository-wide principle with
   domain-specific application.
2. **`BL-30`** genuinely has two halves — async rules (.NET) and Container Apps Jobs
   (deployment/runtime). Each half is stated in the file that governs it, and each names the other.

Every other rule appears in exactly one place.

---

## 11. What this document does not do

- It does not become authority. `.claude/rules/` is the operative baseline
  (`00-authority.md` §00.3).
- It does not resolve a conflict, a defect or a deviation. Those are §9's human decisions.
- It does not close an enforcement gap, and it does not authorize closing one
  (Phase 9 brief §24).
- It does not retire Spec Kit. `.specify/**`, `specs/**` and the ten `speckit-*` skills are
  untouched by Phase 9.
- It does not declare readiness for retirement. Blocker **B-4** (UD-1) remains open, as does
  **CF-2**. **CF-1 was closed in Phase 10** — see
  `docs/migration/phase-10-baseline-reconciliation.md`.
