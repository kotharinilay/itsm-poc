# Conventions

## Cross-cutting (constitution)
- Model proposes, deterministic governance (catalogue) decides — never let model output choose treatment/authority.
- Authority never taken from a message, header or client; identity `(tid, oid)` derived once at the edge. Roles `end_user`, `technician`, `senior_technician`, `administrator` are disjoint — intersect role sets, never rank them. Customer and staff authz are separate models.
- Tenant scoping on every query, cache key, message, telemetry.
- Comments explain WHY with spec/ADR/task refs (e.g. `(T296, ADR-0007)`, `FR-INTEG-007`, `Principle IV`). Match this dense rationale style; cite the requirement.
- Conventional Commits, scope = tree (`feat(integrations): …`, `refactor(ragcore): …`), imperative, descriptive body.
- No new suppressions; justified per-line `# noqa: <code>` only; ruff `ignore = []` stays empty.
- Scaffold honestly: placeholders are labelled; reference fixtures inert and excluded from prod config.

## Python
- Absolute imports only (`ban-relative-imports = "all"`). Ruff formatter authoritative, line 100.
- Full annotations, mypy strict, modern typing (`X | None`, `list[T]`). `pathlib`, `logging` (no `print`), no `assert` outside tests, no `shell=True`, never swallow `CancelledError`, no global mutable state.
- Hexagonal: `domain/` (pure policy) ← `application/` (use cases + `ports.py`) ← adapters (`persistence/`, `messaging/`, `egress/`, …). Wiring in `config/composition.py`; settings only via pydantic-settings in `config/settings.py`.
- FastAPI endpoints hold no business policy; DI via `Depends` (`api/deps.py`); Pydantic schemas at boundaries; problem-details errors; middleware: correlation, identity, provenance, problems.
- Package names reflect *whose system is at the other end* (AI Gateway = RagCore's `model/`; customer systems = Integrations Service).

## .NET
- Constructor injection only; no Service Locator, no `BuildServiceProvider` during config (tested). Single composition root `Synthia.Api/Program.cs`; modules expose `Add<X>Module()` registration.
- Middleware order fixed: exception → correlation → logging → trace → gateway provenance → authn → authz → validation → endpoint.
- CancellationToken propagated everywhere (CA2016 as error). camelCase JSON both deployables.

## Angular
- Standalone components, strict TS, kebab-case files, colocated `.spec.ts`, `inject()`. Auth/API client/realtime centralized in `platform-core`. WCAG 2.2 AA mandatory. No state-management framework without requirement. UI role gating is convenience only.
