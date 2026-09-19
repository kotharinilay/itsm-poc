# Task completion checklist

Merge requires ALL gates pass with no new suppressions (constitution §Quality gate). Run the gates for every tree touched:

- ragcore/integrations (from that dir): `uv run ruff check .` → `uv run ruff format --check .` → `uv run mypy` → `uv run pytest -q`. `dev.sh python` runs both trees.
- dotnet: `dotnet build Synthia.sln -warnaserror`, `dotnet format Synthia.sln --verify-no-changes`, `dotnet test Synthia.sln`.
- web: `npm run lint`, `npx prettier --check .`, `npm run build`, `npm test`.
- desktop: `npx tsc -p tsconfig.json --noEmit`, `npx vitest run`.
- Any change near a deployable boundary, imports, or dependencies: `bash build/scripts/check-boundaries.sh`.
- All at once: `./build/scripts/dev.sh validate`.

Also:
- Schema change → new Alembic revision in `ragcore/migrations/versions/` (sequential `NNNN_name.py`); published views are versioned (`vw_*_v1`) — add new version, don't mutate.
- Contract change → update OpenAPI under `specs/001-platform-scaffold/contracts/` (`build/scripts/openapi_diff.py` / `openapi_validate.py`).
- Architectural decision changed → ADR in `docs/adr/` + update docs.
- Required test categories per change type: constitution §"Which change requires which category" (isolation, governance, approval, idempotency, concurrency, security markers).
- Commit: Conventional Commits with tree scope.
