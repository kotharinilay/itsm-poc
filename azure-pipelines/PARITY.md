# CI/CD parity — `.github/workflows` to `azure-pipelines`

**Status: the Azure DevOps definitions exist and are statically validated. They have not been run.**
`.github/workflows/**` is therefore still the authoritative execution surface, and both exist on
purpose.

This file is the traceable mapping and the deletion criteria. It is updated when a pipeline is
actually run, not when one is written.

## 1. The twelve workflows, and where each one went

| # | GitHub workflow | What it gated | Azure DevOps replacement | Parity |
|---|---|---|---|---|
| 1 | `dotnet.yml` | restore, `-warnaserror` build, format check, `dotnet test` over the whole solution | `dotnet.yml` | **full** — same four steps, same order, same failure conditions |
| 2 | `ragcore.yml` | Ruff lint, Ruff format, `mypy --strict`, pytest, `uv sync --frozen` | `ragcore.yml` + `templates/use-uv.yml` + `templates/python-gates.yml` | **full** |
| 3 | `integrations.yml` | the same four gates from a separate lock, plus `check-boundaries.sh` in a second job | `integrations.yml` | **full** — both jobs preserved, still separate |
| 4 | `web.yml` | ESLint, Prettier, `tsc -b`, build, `npm test`, unconditional a11y sweep, CSP check | `web.yml` | **full** — the a11y and CSP steps stay unconditional |
| 5 | `desktop.yml` | typecheck, lint, Vitest security suite, the guard-fails-correctly verifier, build | `desktop.yml` | **full** — the meta-guard is preserved as a separate step |
| 6 | `migrations.yml` | PostgreSQL 17 service container, `pytest -m integration` with `SYNTHIA_TEST_DB_DSN`, then `-m "not integration"` | `migrations.yml` | **full** — service container declared under `resources.containers`, same DSN, both steps |
| 7 | `contracts.yml` | copy-aside baseline, emit from all three deployables, determinism re-emit, validate, guard verifier, breaking-change diff, stale check, artifact publish | `contracts.yml` | **full** — all nine steps, same order; `runner.temp` becomes `Agent.TempDirectory`, `upload-artifact` becomes `PublishPipelineArtifact@1` |
| 8 | `boundaries.yml` | `check-boundaries.sh`, `verify-boundary-guard.sh`, `verify-architecture-guards.sh` | `boundaries.yml` | **full** — both jobs, no path filter in either surface |
| 9 | `edge.yml` | `check-edge-path.sh`, `verify-edge-guard.sh`, the .NET and RagCore edge-trust suites | `edge.yml` | **full** — the deliberately-absent behavioural half stays absent, with its reason |
| 10 | `images.yml` | `smoke-images.sh` — build, start and inspect every image | `images.yml` | **full** |
| 11 | `security.yml` | Gitleaks over full history, .NET vulnerable packages, web and desktop `npm audit`, weekly schedule | `security.yml` | **full in coverage, different mechanism** — Gitleaks runs from the released binary rather than a marketplace action, with `--exit-code 1` and `fetchDepth: 0` so history is still scanned |
| 12 | `base-image-digests.yml` | monthly resolve, re-pin four Dockerfiles, scan all three base families, **open a pull request** | `base-image-digests.yml` | **partial, deliberately — see §2** |
| — | *(none)* | the governance guard suite had **no** workflow; `.claude/rules/40-testing.md` §40.6 requires it and only a local run enforced it | `governance.yml` | **new** — this is stricter than the GitHub surface, not weaker |

## 2. The one partial, stated plainly

**`base-image-digests.yml` no longer opens the pull request itself.**

The GitHub workflow used a marketplace action to create a branch and open a PR. Azure DevOps has no
first-party equivalent, and opening a PR needs a repository-scoped token this pipeline is
deliberately not granted — a scheduled pipeline that can write to the repository is a larger
change than the one it automates.

What the replacement does instead: resolves the three digests, re-pins all four Dockerfiles, scans
all three base families, publishes the re-pinned tree and the vulnerability diff as an artifact,
and then **fails** so the run is not silently green while a digest has moved.

```text
The CONTROL is unchanged: a digest reaches production only through a reviewed pull request
that passes the full gate. What is weaker is the AUTOMATION -- a person opens the PR.
```

Granting a token and restoring automatic PR creation is a human decision. Until it is taken, this
row is **partial** and the table says so rather than rounding it up.

## 3. Mechanism differences that are not coverage differences

| GitHub | Azure DevOps | Same assertion? |
|---|---|---|
| `actions/setup-dotnet@v4` | `UseDotNet@2` | yes — .NET 10 SDK either way |
| `actions/setup-node@v4` | `NodeTool@0` + `Cache@2` | yes — Node 22, npm cache preserved for the web pipeline |
| `astral-sh/setup-uv@v5` | `templates/use-uv.yml` (official install script) | yes — `uv sync --all-groups --frozen` in both |
| `services: postgres` | `resources.containers` + `services:` | yes — same image, env, health check and port |
| `actions/upload-artifact@v4` | `PublishPipelineArtifact@1` | yes |
| `${{ runner.temp }}` | `$(Agent.TempDirectory)` | yes |
| `gitleaks/gitleaks-action@v2` | pinned Gitleaks release binary, `--exit-code 1` | yes, with `fetchDepth: 0` preserved |
| `aquasecurity/trivy-action` | pinned Trivy install script | yes — same severities, same non-blocking `exit-code 0` at that step |
| `imjasonh/setup-crane` | pinned `go-containerregistry` release | yes |
| `peter-evans/create-pull-request` | **no equivalent** | **no — §2** |

## 4. Criteria for deleting `.github/`

All eight must hold. **Deletion before every one of them is met is prohibited**
(`CLAUDE.md` §12).

| # | Criterion | Status |
|---|---|---|
| 1 | Equivalent Azure DevOps pipelines exist | **met** — fourteen files, YAML-valid, every `script` block passes `bash -n` |
| 2 | The pipelines have executed successfully in Azure DevOps | **not met** — none has been run |
| 3 | Every gate in §1 has been observed passing on the Azure DevOps surface, including the three meta-guards that prove a guard fails on a planted violation | **not met** |
| 4 | Pull-request build validation is configured for the required set in `README.md` | **not met** |
| 5 | Branch policy is equivalent — no direct pushes to the default branch, each required pipeline enforced with its path filter | **not met** |
| 6 | Security and deployment controls remain covered, including the §2 partial being either accepted or closed | **not met** |
| 7 | No active process depends on `.github/` — no badge, no external automation, no documentation instructing a reader there | **not met** — `README.md` and several rule files still cite `.github/workflows/*.yml` as where a gate runs, correctly, because it is |
| 8 | The repository owner has the evidence above and says so | **not met** |

**Until criterion 8, `.github/workflows/**` stays.** It is not a duplicate to tidy away; it is the
surface that is currently running.

## 5. What this migration did not change

- **No gate was weakened, dropped or made conditional.** Every step that was unconditional on the
  GitHub surface is unconditional here — in particular the accessibility sweep, the CSP check and
  the three guard-fails-correctly verifiers.
- **No test was skipped, filtered or narrowed** to make a pipeline pass
  (`.claude/rules/40-testing.md` §40.1).
- **No gap was quietly closed.** `security.yml` still has no Python dependency-vulnerability step:
  that is **EG-6** in `docs/governance/open-items.md` §2, and adding one is a separate,
  human-directed decision — not something a CI/CD migration decides on its own.
