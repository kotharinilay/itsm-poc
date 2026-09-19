# Tech stack

- **Python 3.12** (pinned `>=3.12,<3.13`), `uv` + committed `uv.lock` per project (`ragcore/`, `integrations/` separate). Hatchling build. FastAPI, Pydantic v2 + pydantic-settings, SQLAlchemy async + asyncpg, psycopg3, Azure SDK (servicebus, identity, keyvault; `aiohttp` explicit for async transport), httpx, OpenTelemetry + azure-monitor.
  - RagCore only: LangGraph + `langgraph-checkpoint-postgres`, Alembic + alembic-utils, Redis (transient cache, never authoritative).
  - Integrations only: `mcp`. Must NOT add langgraph, model-provider SDKs, redis (architectural change).
  - Dev: ruff, mypy (strict), pytest + pytest-asyncio (`asyncio_mode=auto`), pytest-alembic, testcontainers[postgres].
- **.NET 10** (`net10.0`), central package management (`dotnet/Directory.Packages.props`), `Directory.Build.props` forces Nullable, TreatWarningsAsErrors, analyzers latest-Recommended, EnforceCodeStyleInBuild, InvariantGlobalization. Minimal APIs, built-in OpenAPI, ProblemDetails.
- **Web**: Angular 20 (standalone), TypeScript 5.9, Karma/Jasmine unit tests (ChromeHeadless), Playwright + axe e2e, ESLint 9 (angular-eslint), Prettier (width 100, single quotes).
- **Desktop**: Electron, ESM, tsc + esbuild (preload bundle), vitest, electron-builder (NSIS/Windows).
- **Infra**: Azure — Container Apps, APIM, Front Door/WAF, Service Bus, Key Vault, PostgreSQL, AI Gateway, SignalR, Entra ID (sole human IdP).
- Requires: .NET 10 SDK, Node 20+, uv, Git.
