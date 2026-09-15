# Stage 1 Implementation Notes

**Date**: 2026-09-16 · **Scope**: Phase 1 (T001–T022) plus the Electron security foundation
(T050–T056). No business use case, no product behaviour.

Recorded because an unrecorded decision is re-litigated (constitution Principle X). **None of these
changes architecture**; each is an implementation choice made inside the frozen plan, or a version
forced by the environment.

## Deviations from the frozen plan

| # | Plan says | Built | Why |
|---|---|---|---|
| 1 | "Angular standalone components" (version unpinned) | **Angular 20.3** | The current CLI requires Node `^24.15.0`; this machine runs 24.14.1. Angular 20 is the newest line supporting it. **Revisit when:** Node is upgraded — then move to the current line. |
| 2 | Python 3.12 (`py312`) | `requires-python = ">=3.12,<3.13"` | uv resolved 3.13 against a bare `>=3.12`, which would have diverged from the 3.12 container base (R-012). Constrained so the dev interpreter matches the image. |
| 3 | T007: `dotnet/Synthia.sln` | `.sln`, not `.slnx` | .NET 10 generates `.slnx` by default. The frozen task names `.sln`, and broader tooling support agrees; `--format sln` was passed deliberately. |
| 4 | Five CI workflows (T014–T018) | **Seven** | `desktop.yml` and `security.yml` were added. The plan's five predate the Electron security suite being in scope, and secret scanning (T019) had no workflow to live in. |
| 5 | T022: "Plant a deliberate cross-tree reference and confirm the script fails, then remove it" | `build/scripts/verify-boundary-guard.sh`, run in CI | A one-off manual check proves the guard worked once. Making it a script means a change that weakens the guard is caught by the thing that proves it. |

## Versions changed by a gate, not by choice

Three dependency versions were raised because a gate refused the original. Recording them so the
next person does not "simplify" them back:

- **OpenTelemetry 1.13.1 → 1.18.0.** `NU1902` under `TreatWarningsAsErrors` — `OpenTelemetry.Api`
  1.13.1 carries GHSA-g94r-2vxg-569j. `OpenTelemetry.Api` is now pinned explicitly because it
  arrived transitively.
- **Electron 33 → 44.** Electron 33 is out of support and `npm audit` reported 7 vulnerabilities
  including one critical. The constitution requires a currently supported release.
- **vitest 2 → 5 (with vite 8).** vitest 2's transitive `vite`/`esbuild` carried the remaining
  advisories. Both desktop trees now audit clean at zero.

`Microsoft.Extensions.Options.DataAnnotations` was removed from `Synthia.Api` — `NU1510`, it is
framework-provided on `net10.0`.

## Additions the task list did not name

- **`.gitattributes`.** Git was normalising every file to CRLF on checkout. Harmless for Markdown,
  fatal for `build/scripts/*.sh` in a Linux CI container. `*.sh text eol=lf` prevents a class of
  failure that would otherwise appear only on the first CI run.
- **`ragcore/src/ragcore/config/composition.py`.** Named as the RagCore composition root in plan
  §Composition roots; it did not exist as a task because that section was written during the
  2026-09-16 remediation, after the task list was generated.

## A guard that silently stopped guarding

The first `check-boundaries.sh` switched between ripgrep and grep depending on what was installed.
The two disagreed: **it passed three of four planted violations.** It was caught only because T022
requires proving the guard fails.

It was rewritten to a single portable `find` + `grep` path with no fallback, and now rejects all
four classes. The lesson is recorded in the script's own header, because the tempting "optimisation"
is to add the fast path back.

## Deferred — deliberately not built

| Area | Why | Lands at |
|---|---|---|
| Shared contracts, domain types, architecture tests | Phase 2 (T023–T037). `TenantId`, `StaffRole`, set-intersection, NetArchTest suites | Stage 2 |
| Angular feature shells, a11y sweep | Phase 3 (T038–T049). The workspace builds and lints; no feature exists | Stage 3 |
| .NET middleware, routing, endpoints | Phase 5 (T057–T081). The host starts and serves `/health/live` only | Stage 5 |
| FastAPI application, LangGraph skeleton | Phase 6 (T068–T081). Packages and the composition root exist; no app object | Stage 6 |
| Alembic, every table and view | Phase 7 (T082–T113). `migrations/` holds a README stating ownership | Stage 7 |
| Desktop script execution | ADR-0004 open items — script signing, destructive taxonomy | Blocked |
| UC-01 through UC-12 | No product definitions; gated behind both golden paths | Stage 14 |

**No business use case was implemented.** The IPC channel allow-list holds two informational
channels (`app:getVersion`, `app:getPlatform`), and the security suite asserts that no channel name
contains a word implying authority or script execution — so the absence is tested, not just claimed.
