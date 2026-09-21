# Task completion checklist

Merge requires ALL gates pass with no new suppressions (`.claude/rules/22-web-typescript.md` FE-SH-3 for the frontend; the per-stack rule files elsewhere). Run the gates for every tree touched:

- ragcore/integrations (from that dir): `uv run ruff check .` → `uv run ruff format --check .` → `uv run mypy` → `uv run pytest -q`. `dev.sh python` runs both trees.
- dotnet: `dotnet build Synthia.sln -warnaserror`, `dotnet format Synthia.sln --verify-no-changes`, `dotnet test Synthia.sln`.
- web: `npm run lint`, `npx prettier --check .`, `npm run build`, `npm test`.
- desktop: `npx tsc -p tsconfig.json --noEmit`, `npx vitest run`.
- Any change near a deployable boundary, imports, or dependencies: `bash build/scripts/check-boundaries.sh`.
- All at once: `./build/scripts/dev.sh validate`.

Also:
- Schema change → new Alembic revision in `ragcore/migrations/versions/` (sequential `NNNN_name.py`); published views are versioned (`vw_*_v1`) — add new version, don't mutate.
- Contract change → contracts are **code-first** (`.claude/rules/20-dotnet.md` BL-6); regenerate under `build/contracts/` and run `./build/scripts/dev.sh contracts` (`build/scripts/openapi_diff.py` / `openapi_validate.py`).
- Architectural decision changed → ADR in `docs/adr/` + update docs.
- Required test kinds: `.claude/rules/40-testing.md` §40.5, plus the gate rules' own obligations (30 §30.9, 50 §50.8). The retired constitution's per-change category matrix is **not** fully mirrored there — open finding D-11-2 in `docs/migration/phase-11-retirement-readiness.md`.
- Commit: Conventional Commits with tree scope.
