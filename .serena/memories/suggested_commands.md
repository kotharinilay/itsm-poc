# Suggested commands

Platform: Windows. Bash tool = Git Bash (POSIX); PowerShell 5.1 also available (no `&&`).

## Orchestrator (same commands CI runs)
- `./build/scripts/dev.sh setup` — restore all toolchains (Windows alt: `pwsh ./build/scripts/dev.ps1 setup`).
- `./build/scripts/dev.sh validate` — every gate. Subsets: `dotnet | python | web | desktop | boundaries | lint | typecheck | build | test | clean | help`.
- `dev.sh python` (and setup/lint/typecheck/test/validate) cover both Python trees: ragcore and integrations, each from its own dir/lock file.

## Python (run from `ragcore/` or `integrations/`)
- `uv sync --all-groups`
- `uv run ruff check .` · `uv run ruff format --check .` (format: `uv run ruff format .`)
- `uv run mypy` (strict; files configured in pyproject)
- `uv run pytest -q` · by marker: `-m "isolation"`, `governance`, `approval`, `idempotency`, `concurrency`, `security`, `integration` (Testcontainers → Docker needed), `e2e`.

## .NET (from `dotnet/`)
- `dotnet build Synthia.sln -warnaserror` · `dotnet format Synthia.sln --verify-no-changes` · `dotnet test Synthia.sln`

## Web (from `apps/web/`)
- `npm run lint` · `npx prettier --check .` · `npm run build` (libs then 3 apps) · `npm test` · `npm run test:unit` (all projects) · `npm run e2e`

## Desktop (from `apps/desktop/`)
- `npx tsc -p tsconfig.json --noEmit` · `npx vitest run` (security suite) · `npm start`

## Boundary / guards (repo root, bash)
- `bash build/scripts/check-boundaries.sh`; `verify-*-guard.sh` scripts prove the guards catch planted violations.
