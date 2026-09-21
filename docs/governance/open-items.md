# Open governance items — deviations, enforcement gaps, defects and decisions

**Status: permanent and current.** This is the repository's register of everything that is *known
to be unfinished* in its governance: places where the implementation does not meet the engineering
baseline, rules whose gate does not exist, defects in a retired source that nobody has corrected,
and decisions that are a human's to take.

It exists because `.claude/rules/00-authority.md` §00.7 requires a deviation to be **recorded and
preserved**, never silently repaired and never used to rewrite the baseline. A register that lives
only in a migration diary is a register nobody reads.

## What this document is not

- **Not authority.** `.claude/rules/**` states the baseline; the three architecture documents state
  the architecture. An item here never relaxes either. An open deviation is *not* permission to
  extend it (`00-authority.md` §00.4).
- **Not a backlog.** Nothing here is scheduled. Each item names the instrument that would close it —
  a configuration change, an editorial correction, or an ADR — and stops there.
- **Not a record of what the code does.** That is `docs/functional/implemented.md`.

## How an item is closed

```text
Deviation (DV)        -> change the implementation to meet the rule, or change the rule by ADR
                         (70-adr.md §70.2 B). Never by editing this file.
Enforcement gap (EG)  -> build the gate. A separate, human-directed decision; a gap in the gate
                         is never a reduction in the requirement.
Source defect (D)     -> a human editorial correction. Not an ADR (00-authority.md §00.6).
Conflict (CF)         -> an ADR. Never by picking a winner (00-authority.md §00.6).
Decision (UD)         -> a human decides; the instrument is named per row.
```

Closing an item removes its row, in the same change that closes it. **Do not delete a row because
it is inconvenient, and do not mark one closed on Claude's own initiative.**

---

## 1. Deviations — implementation differs from the baseline

Recorded, baseline preserved, nothing repaired.

| ID | Deviation | Evidence | The baseline says | Severity |
|---|---|---|---|---|
| **DV-1** | `CA2007` disabled | `dotnet/.editorconfig` sets `severity = none`, commented "off deliberately, not by oversight" | `.claude/rules/20-dotnet.md` DN-8: `severity = error` for library projects | **High** — a deliberate baseline relaxation with no ADR, itself an ADR trigger (`70-adr.md` §70.2 B(1)). Decision **UD-2** |
| **DV-2** | `CA1848` is a suggestion, not an error | `dotnet/.editorconfig` | DN-31 / BL-22: `severity = error` | Medium — rule unenforced |
| **DV-3** | `BannedApiAnalyzers` absent; the bans it should carry are enforced, where at all, by architecture tests instead | `dotnet/Directory.Packages.props` has no reference; `dotnet/tests/Synthia.ArchitectureTests/BannedApiTests.cs` exists | DN-1, DN-3, DN-13, DN-14: RS0030 plus a `BannedSymbols.txt` | Mixed — DN-1/DN-3 are covered by the substitute; DN-13/DN-14 are covered by nothing (**EG-2**) |
| **DV-4** | About fifteen CA rules the baseline requires at `severity = error` are not bound in `.editorconfig` and rely on whatever `latest-Recommended` enables | `dotnet/.editorconfig` binds only CA2007, CA2016, CA1849, CA1031, CA1062, CA1848, CA1707 | DN-11, 12, 15, 17, 18, 22, 24, 25, 27, 30, 32, 33, 34, 35, 37 | Medium — recorded as `partial`, not `mechanical` |
| **DV-5** | `CA2200` and `CA1416` are build-failing only because they default to *warning* under `TreatWarningsAsErrors`; the explicit `severity = error` is absent | `dotnet/.editorconfig` | DN-26, DN-36 | Low — outcome correct, determinism weaker |
| **DV-6** | `CA1062` bound to `warning`, not `error` | `dotnet/.editorconfig` | DN-16: `severity = error` | Low — enforced today, but silently stops if `TreatWarningsAsErrors` is ever scoped down |
| **DV-7** | A project-wide `NoWarn` entry suppresses `CS1591` while `GenerateDocumentationFile` is true | `dotnet/Directory.Build.props` | DN-21: no file- or project-wide blanket disables; every suppression scoped and justified | Low–Medium — the one existing instance DN-21 reaches |
| **DV-8** | `quote-style` is not written in either `[tool.ruff.format]` | `ragcore/pyproject.toml`, `integrations/pyproject.toml` | `.claude/rules/21-python.md` §21.1 formatter row: `quote-style = "double"` emitted to `pyproject.toml` | Cosmetic — Ruff's default *is* `double`, so behaviour holds and `ruff format --check` gates it |
| **DV-9** | A `per-file-ignores` entry beyond what the baseline sanctions, for the Alembic versions directory | `ragcore/pyproject.toml` | P-PY-S3: never a blanket ignore; suppression only via a justified per-line `# noqa`. Adding to `per-file-ignores` is an ADR trigger (`70-adr.md` §70.2 B(2)) | Low — Alembic-generated module names are the stated reason, and it predates the current baseline |
| **DV-10** | `T20` absent from Ruff `select` in both projects, so the `print` ban is unguarded | `ragcore/pyproject.toml`, `integrations/pyproject.toml` | `.claude/rules/21-python.md` PY-4: `T20` must be in `select` for the rule to fire | Medium. Decision **UD-5** |
| **DV-11** | The .NET image is built by a hand-written multi-stage Dockerfile, not by the SDK container-publish target | `build/docker/dotnet.Dockerfile` | `.claude/rules/80-security-ops.md` BL-38: ".NET SDK container publish" | Medium — but see **CF-2**: BL-38 and BL-39 cannot both be satisfied literally, and the Dockerfile states that reason inline |
| **DV-12** | `apps/desktop` configures no formatter, so the frontend quality gate's "formatting passes" obligation has no desktop mechanism | `apps/desktop/package.json` has no Prettier script; `apps/web` runs `npx prettier --check .` | `.claude/rules/22-web-typescript.md` FE-SH-3 requires formatting to pass on **both** clients | Low — the other six obligations in that gate are mechanical on both clients. Closing it means adding a Prettier configuration and a failing CI step for `apps/desktop`, which is a configuration change realizing the existing rule and needs no ADR |

---

## 2. Enforcement gaps — a rule whose gate does not exist

A gap in the gate is **never** a reduction in the requirement. Building a gate is a separate,
human-directed decision (`.claude/rules/40-testing.md` §40.7).

| ID | Gap | Affects | What the rule asks for |
|---|---|---|---|
| **EG-1** | No commit-message check and no release/versioning tooling | `.claude/rules/10-principles.md` C-1, C-2 | a commit-message CI check plus release tooling |
| **EG-2** | `Microsoft.CodeAnalysis.BannedApiAnalyzers` is not referenced in `dotnet/Directory.Packages.props`, and no `BannedSymbols.txt` exists | DN-13, DN-14, and C# credential literals (`80-security-ops.md` §80.3) | BannedApiAnalyzers RS0030 plus a `BannedSymbols.txt` |
| **EG-3** | `Microsoft.VisualStudio.Threading.Analyzers` not referenced | DN-5 | VSTHRD100 at `severity = error` |
| **EG-4** | No custom Roslyn or structural check for `goto` | DN-19 | a check failing on `GotoStatementSyntax`. The rule states that review is **not** acceptable here (`40-testing.md` §40.5) |
| **EG-5** | No analyzer requiring a non-empty `Justification` on `SuppressMessage` | DN-21 | a custom analyzer |
| **EG-6** | No Python dependency-vulnerability audit step in the security pipeline; .NET, web and desktop each have one | `80-security-ops.md` §80.4 | repository symmetry, not a named rule |
| **EG-7** | No lint or architecture check for graph-navigation call chains | P-12 | a check flagging call chains that navigate beyond the immediate collaborator |
| **EG-8** | No analyzer or lint warning-count baseline ratchet | P-22 | a ratchet failing the build when a modified file introduces net-new warnings |
| **EG-10** | Nothing maps a changed file or a diff to the **test categories** `40-testing.md` §40.9 says it owes | TC-01…TC-15, CM-01…CM-12 | the obligation is applied by a reviewer, not by a gate |

> **EG-9 is deliberately absent.** `EG-10` is the id cited inside `.claude/rules/40-testing.md`
> §40.9 and inside the accepted `docs/adr/0011-required-test-categories-baseline.md`. Renumbering
> an id an accepted record cites would make that record wrong, so the id is preserved and no
> `EG-9` was invented to fill the hole.

DN-1, DN-3 and P-26 are **not** gaps: the baseline names BannedApiAnalyzers, which is absent, but
`dotnet/tests/Synthia.ArchitectureTests/BannedApiTests.cs` and `ServiceResolutionTests.cs` enforce
them as genuine build-failing gates. That substitution is **DV-3**, with enforcement `mechanical`,
because the outcome the rule requires is achieved.

---

## 3. Conflicts between authoritative sources — stopped, not chosen

`.claude/rules/00-authority.md` §00.6: record both sides, pick no winner, resolve by ADR.

### CF-2 — SDK container publish vs the chiseled base image

| | |
|---|---|
| **Source A** | `.claude/rules/80-security-ops.md` **BL-38**: build mode is ".NET SDK container publish". |
| **Source B** | `.claude/rules/80-security-ops.md` **BL-39**: production images use the chiseled .NET runtime base, built **multi-stage** — the SDK image builds, the chiseled runtime image runs. |
| **The conflict** | Both are items of the same baseline. The SDK container-publish target produces an image from an SDK-resolved base, and **no chiseled SDK image is published**, so the literal SDK-publish path cannot produce the image B mandates. B's own text acknowledges this by describing a multi-stage build. |
| **Affected** | the .NET deployment and runtime surface |
| **Impact** | Low operationally. The repository satisfies B, and `build/docker/dotnet.Dockerfile` states why inline. The open question is whether BL-38 is superseded by BL-39 or describes a different artifact. |
| **Decision required** | **UD-6** |

> **CF-1 is closed** and is not carried here. It was a contradiction between a retired baseline
> input and the Alembic-owns-all-schema rule, closed by a human amending the input. The rule in
> force never changed: `.claude/rules/50-database.md` §50.7 and A2 §8.1 still state that Alembic
> under `ragcore/migrations/` is the single schema mechanism and that the .NET side owns no
> migrations.

---

## 4. Defects in retired inputs — recorded, never reconstructed

These are defects in material that was migrated into `.claude/rules/**`. The inputs were retired and
survive only in git history; the defect matters because of what it means for the migrated rule.

| ID | Defect | Consequence today |
|---|---|---|
| **D-1** | The .NET input declared that `EnforceCodeStyleInBuild` realizes the `goto` rule, which it does not; it realizes DN-28/DN-29 | None to coverage — both rules are stated independently in `.claude/rules/20-dotnet.md` §20.1 |
| **D-2** | The baseline block's `BL-08` offset/limit sentence was truncated and ran into the next heading | One requirement is unreadable and was **not** reconstructed. Decision **UD-4** |
| **D-3** | A YAML parsing hazard destroyed the text of DN-21 in the retired pack | Recovered from the raw source line before retirement; `20-dotnet.md` DN-21 carries the full requirement |

---

## 5. Cross-stack citation gap — eight requirements stated only for .NET

Eight places in the **Python** tree state a requirement in prose whose only baseline statement is on
the **.NET** stack. Inventing a Python counterpart would be creating a requirement, which is an
engineering-baseline change under `.claude/rules/70-adr.md` §70.2 B(6).

| Where | The requirement | Stated only as |
|---|---|---|
| `integrations/src/integrations/api/app.py` (twice) | middleware ordering is load-bearing | `.claude/rules/20-dotnet.md` BL-26 |
| `integrations/src/integrations/api/middleware/correlation.py` | the same ordering rule | BL-26 |
| `integrations/src/integrations/api/middleware/problems.py` | the same ordering rule | BL-26 |
| `integrations/src/integrations/api/middleware/problems.py` | internal exception detail must never reach a client | BL-18 |
| `integrations/src/integrations/api/health.py` | readiness must not depend on an external customer system | BL-25 |
| `integrations/src/integrations/egress/http.py` | no one-off unmanaged HTTP clients | BL-32; `21-python.md` PY-17 covers only the timeout half |
| `ragcore/src/ragcore/persistence/repositories.py` | the generic-repository ban | BL-14 |

**Decision required — UD-8.** Either state these requirements for the Python stack, which is an
engineering-baseline change needing an ADR, or decide they are .NET-only and record that.
`.claude/rules/21-python.md` §21.9 lists the explicit non-equivalences and is the file that would
change. Each source file above points at this section, so the gap stays visible from the code.

---

## 5a. Preserved ambiguities in the frontend baseline — FE-AMB-1…3

Three requirements were migrated with an ambiguity their input carried. **The ambiguity is
preserved rather than resolved by invention**, because resolving one would state a requirement
nobody decided.

| ID | Requirement | The ambiguity | How the rule handles it |
|---|---|---|---|
| **FE-AMB-1** | `.claude/rules/24-electron.md` FE-EL-2 — Electron sandbox | the input qualified `sandbox=true` as **"where compatible"** | The rule states the **unconditional** form, because that is what `apps/desktop/src/main/window.ts` sets and `apps/desktop/tests/security.spec.ts` asserts. The qualifier is recorded here, neither silently dropped nor silently kept |
| **FE-AMB-2** | `.claude/rules/23-angular.md` FE-NG-10 — `bypassSecurityTrust*` | avoided "unless specifically justified, reviewed and constrained" — **the instrument of justification is not named** | The wording is preserved. No approval procedure was invented. The committed ESLint rule is absolute, so any use today needs a suppression, which `22-web-typescript.md` FE-SH-3 already governs |
| **FE-AMB-3** | `.claude/rules/23-angular.md` FE-NG-8 — the Angular workspace dependency direction | its only prose statement was a retiring, non-authoritative planning artifact, alongside `apps/web/eslint.config.js` as executable configuration | Stated as a rule so it survives that artifact's retirement with a current authoritative statement, and because it is the Angular realization of P-13/P-24. That its origin was a retiring artifact is recorded, not hidden |

Closing one means a human deciding the open half — for FE-AMB-1, whether the qualifier applies at
all; for FE-AMB-2, what the instrument of justification is. Either is an engineering-baseline
change under `.claude/rules/70-adr.md` §70.2 B(6).

---

## 6. Human decisions

| ID | Decision | Relates to | Instrument |
|---|---|---|---|
| **UD-2** | `CA2007` / DN-8: accept the relaxation by ADR, or restore `severity = error` for library projects | DV-1 | ADR (`70-adr.md` §70.2 B(1)), or a configuration change |
| **UD-4** | The truncated `BL-08` offset/limit requirement — restate it, or drop it deliberately | D-2 | An editorial decision recorded in `20-dotnet.md` |
| **UD-5** | Whether to add `T20` to Ruff `select`, making PY-4 mechanical | DV-10 | A configuration change realizing the existing baseline — **no ADR needed**, it strengthens toward the rule |
| **UD-6** | BL-38 vs BL-39 build mode | CF-2, DV-11 | An editorial decision, or an ADR if the rule itself changes |
| **UD-7** | Whether to close any enforcement gap in §2, and in what order | §2 | Each is a separate decision; EG-4, EG-5 and EG-8 require building new analyzers |
| **UD-8** | The eight cross-stack citations — state them for Python, or declare them .NET-only | §5 | ADR (`70-adr.md` §70.2 B(6)) |
| **UD-9** | `Synthia-Platform-Specification.md` is **retained as history**, because accepted records ADR-0001 to ADR-0008 and the ADR index open-item table cite it for their own rationale, and an accepted record is never rewritten (`70-adr.md` §70.6). Decide whether to retire it, which first requires re-homing **OQ-01** — the second-consequential-operation question, recorded only there | documentation surface | A human decision |
| **UD-11** | **The base-image re-pin no longer opens its own pull request.** GitHub Actions did this with a marketplace action; Azure DevOps has no first-party equivalent, and opening a PR needs a repository-scoped token the scheduled pipeline is deliberately not granted. `azure-pipelines/base-image-digests.yml` resolves, re-pins, scans, publishes an artifact and then **fails** so the run is not silently green. **The control is unchanged** — a digest still reaches production only through a reviewed PR that passes the full gate; the automation is weaker. **Do not grant a token to close this merely to make the migration look complete** | `azure-pipelines/base-image-digests.yml`, `azure-pipelines/PARITY.md` §2 | A human decides whether to grant a scoped token and restore automatic PR creation, or to accept the manual step permanently |
| **UD-12** | **The default branch has no protection.** `main` on the GitHub remote returns *Branch not protected*, so **no required status check is enforced today** and a direct push to `main` is possible. This is not a regression introduced by the pipeline work — it is the state the Azure DevOps branch policy was supposed to be made *equivalent to*, and there is nothing to be equivalent to. It makes `azure-pipelines/PARITY.md` criterion 5 unmeetable as written | GitHub repository settings; `azure-pipelines/README.md` §Branch policy | A repository administrator configures branch protection (or the Azure Repos equivalent) with the required set in `azure-pipelines/README.md`. Claude cannot and must not change repository settings |
| **UD-13** | **The scheduled secret scan is failing.** The `security` workflow run of 2026-09-21 (id `35599755535`) reports *Leaks detected* from Gitleaks, with a SARIF artifact attached to that run. The repository is **public**. The finding is recorded here rather than reproduced: a register is not the place to restate a candidate secret. The Azure DevOps replacement runs the same scan with `--exit-code 1`, so it would fail identically — parity is intact and the gate is working | `.github/workflows/security.yml`, `azure-pipelines/security.yml` | A human reviews the SARIF artifact, and either rotates and purges a real credential or records the finding as a false positive in a Gitleaks allow-list. **Until then the secret-scanning gate is red**, and no pipeline migration may be called complete on a red security gate |
| **UD-10** | **`docs/adr/0012` carries `Status: Proposed` although the decision was accepted.** The acceptance is real and recorded: the repository owner accepted it explicitly, in session, before any of it was implemented, and `.claude/rules/10-principles.md` §10.7 is implemented on that acceptance. `.claude/hooks/adr_structure_guard.py` (H5) deterministically blocks Claude from editing an existing record, which is the guard working as designed — **the fix is a human one-line edit**, plus the matching cell in `docs/adr/README.md`. Until then the record and the index agree on `Proposed`, so nothing is internally inconsistent; the status field simply under-reads the decision | `docs/adr/0012-…`, `docs/adr/README.md` | A human edits the status field. **Do not weaken or bypass H5 to do it** |

---

## 7. Conformance findings — implementation differs from architecture

Owned by `.claude/rules/60-architecture-gates.md` §60.4 and recorded in
`docs/functional/implemented.md` per §90.7. **Reported, never reconciled**; resolving one is an ADR
where it changes architecture.

| Finding | Recorded in |
|---|---|
| The implemented graph state vocabulary and node names do not match A3 §6.2 name for name | `.claude/rules/30-langgraph.md` §30.7 |
| The .NET side uses EF Core for data access while Alembic owns all schema, with no single mechanical check tying the two together | `.claude/rules/50-database.md` §50.7 |

---

## 8. Recorded test obligations that are not met

`.claude/rules/40-testing.md` §40.10 records two hard failures — **tenant context derived from an
untrusted client field**, and **authorization bypass** — that have no failing-then-passing test at
the backend, because the protection they tested was deferred and not replaced
(`docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md`, open item **D-01**).

```text
The obligation is unchanged.  It is simply NOT MET for that pair.
No test may be written that appears to meet it by asserting something weaker.
```

Closing it is a human decision: either the tests are written, or the deferred protection is
restored. Neither is done by recording it here.
