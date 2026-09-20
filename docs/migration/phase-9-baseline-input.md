\- Application architecture / layering: Modular monolith

\- Dependency injection conventions: Constructor injection as the sole pattern, using the built-in Microsoft.Extensions.DependencyInjection container. constructor injection + the built-in IServiceProvider as the framework-native default. Anti-Patterns: Service Locator Pattern, Do Not Call BuildServiceProvider in Configuration.

\- Module composition: Logical Boundaries

\- API style and routing: REST / Minimal APIs

\- API versioning: URI segment

\- OpenAPI / contract emission: Code-first (built-in OpenApi)

\- Request / response contract conventions: Casing: camelCase JSON (System.Text.Json default for .NET). Idiomatic for the .NET stack and the JS/TS SPA client.

Naming: resource-oriented plural nouns (/api/v1/permits, /api/v1/master-cards, /api/v1/lockout-tags); kebab-case multi-word path segments; HTTP verbs carry the action.

\- Pagination, filtering, sorting: Default: keyset/cursor pagination for large or growing collections — the permit register (PRM-01), global search (ADM-15), and reporting result sets (RPT-\*) — using an opaque cursor + limit, stable ordering by a monotonic key. Offset/limitOutbound resilience pipeline

Filtering: typed query-string parameters per endpoint (e.g. ?status=Issued&unit=...&from=...&to=...) matching the advanced-filter requirements. No generic OData-style expression language.

Sorting: ?sort=field / ?sort=-field (leading - = descending), whitelisted fields only.

\- Data access: EF Core 10 + Npgsql

\- Migrations: The platform schema is owned by exactly one versioned migration mechanism, executed as a gated job in the CI/deploy step before the new application revision is activated — never at application startup. In this repository that mechanism is Alembic, under `ragcore/migrations/`. The .NET deployable owns no migrations and applies no DDL; it reads through published views that the same migration history creates and versions. [AMENDED — Phase 10, see Appendix A]

\- Transaction and concurrency model: Optimistic only (no lock anywhere)

\- Isolation level: Read Committed default, Serializable on invariant txns

\- Data lifecycle (soft-delete, audit columns, retention): Soft-delete + global query filter + audit columns

\- Query conventions: Read paths use AsNoTracking(), All queries are parameterized, N+1 prevention, Compiled queries

\- Secrets management (where secrets live, how they reach the app): Key Vault refs via managed identity

\- Configuration layering: Standard .NET host layering — appsettings.json (defaults) → appsettings.{Environment}.json (env-specific) → environment variables (deployment/ACA) → in last position, ACA secretref: env vars for secret material. Later providers override earlier keys; env vars win over files; secrets arrive through the same env-var channel.

\- Strongly-typed configuration: Bind each config section to a POCO options class via the .NET Options pattern (builder.Services.AddOptions().BindConfiguration("Section").ValidateDataAnnotations().ValidateOnStart()). Consume through IOptions / IOptionsSnapshot / IOptionsMonitor. Raw string-key config access (Configuration\["Foo:Bar"\]) in application/domain code is banned

\- Input validation: .NET 10 built-in validation

\- Error / result model: Result + exceptions, IExceptionHandler→ProblemDetails

\- Structured logging: Microsoft.Extensions.Logging + OTel

\- Telemetry: OTel + Azure Monitor Distro

\- Logger source-generation: LoggerMessage source-gen

\- Cancellation: Propagate CancellationToken through every async call from the endpoint signature down to every blocking I/O (EF Core, Npgsql, HttpClient, ERP-sync). Honour it at every awaitable boundary; never swallow OperationCanceledException. Justification: idiomatic .NET, prevents wasted work on client disconnect / shutdown, required for clean ACA scale-in.

\- Context propagator: Use the standard W3C Trace Context propagation (OpenTelemetry default). Baggage limited to a small, explicit allowlist (correlation id; tenant/site id only if needed). Do not add ad-hoc propagation headers.

\- Health checks: Three separated endpoints via MapHealthChecks with tag predicates: /health/live (liveness — Predicate => false, process-only, no dependency checks), /health/ready (readiness — tagged ready, includes PostgreSQL via AddDbContextCheck/Npgsql check and critical dependencies), and optionally /health/startup for slow init.

\- Middleware order: (outermost → innermost): exception handler → correlation/request-id → request logging → trace context (OTel) → auth (authn then authz) → validation (edge) → endpoint. Error handler is outermost so it catches everything; correlation/trace established before logging; auth before tenant resolver.

\- Correlation / request IDs: Field name X-Correlation-Id (header) surfaced as RequestId/CorrelationId in logs. Rule: accept inbound X-Correlation-Id if present and well-formed; otherwise generate one. Echo it back in the response header on every request. Bind it into the logging scope and OTel baggage.

\- Outbound resilience pipeline: Http.Resilience standard handler (Polly v8)

\- Idempotency: Idempotency-key filter + Postgres store + outbound dedup keys

\- Concurrency and consistency rules: Async rules + Container Apps Jobs for singletons, no distributed lock

\- Outbound interceptor chain: DelegatingHandler chain via IHttpClientFactory, resilience innermost

\- Outbound HTTP client conventions: Style: Typed clients registered via IHttpClientFactory (services.AddHttpClient()), one typed client per §11 adapter/dependency, base address + default headers configured at registration, pooled HttpMessageHandler reuse (factory default — avoids socket exhaustion, PF5). No manual new HttpClient() anywhere.

\- Outbox pattern: Transactional outbox in PG

\- Transport / broker: Azure Service Bus Standard

\- Anti-Corruption Layer / Adapter: Port-and-adapter per dependency, port owned by integrating module, impl in module infrastructure

\- Provider abstraction and swap policy: One adapter per concrete provider; domain-shaped port only; no provider-neutral super-abstraction. Swap later if a real second provider appears

\- Container runtime config: HTTP probes + explicit limits + 25s drain

\- Build mode: .NET SDK container publish

\- Dockerfile structure + base-image hardening (preventive): Locked convention: Production images use the minimal, shell-less, package-manager-free Ubuntu chiseled base for .NET 10 — mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled (tag confirmed live on MCR; pin by digest in the pipeline, never a floating tag). Build is multi-stage (SDK image builds, chiseled runtime image runs) via the D13.3 SDK-publish path, which sets these by construction:

Non-root user by default (app, UID 1654) — hard rule; do not override to root.

Shell-less / no package manager in the final image (chiseled) — shrinks CVE surface.

Pin the base by digest, not latest or a floating major tag.

Read-only root filesystem where feasible.

Document the base-image policy in-repo (which family, why chiseled, how digests are bumped).

---

## Appendix A — Amendment record

This block is an **authoritative engineering-baseline source**
(`.claude/rules/00-authority.md` §00.3). It is therefore never edited silently. Every amendment
is recorded here, in full, with its authority.

### A.1 — `BL-10` Migrations (Phase 10)

| | |
|---|---|
| **Item** | `BL-10` — *Migrations* |
| **Amended in** | Phase 10, `docs/migration/phase-10-baseline-reconciliation.md` |
| **Resolves** | Conflict **CF-1**, decision **UD-3** (`docs/migration/phase-9-baseline-coverage.md` §9.1, §9.3) |
| **Instrument** | Explicit human decision, supplied in the Phase 10 brief — option (i) of UD-3: *confirm `BL-10` does not apply to this repository as written, and amend the baseline block* |

**Original wording**

> Migrations: EF Migrations bundle in CI/deploy step

**Approved replacement wording**

> Migrations: The platform schema is owned by exactly one versioned migration mechanism, executed
> as a gated job in the CI/deploy step before the new application revision is activated — never at
> application startup. In this repository that mechanism is Alembic, under `ragcore/migrations/`.
> The .NET deployable owns no migrations and applies no DDL; it reads through published views that
> the same migration history creates and versions.

**Reason for the amendment**

The original wording named **EF Migrations** as the schema-migration mechanism. That attribution
contradicted the platform's established schema-ownership model, under which the .NET deployable
owns no migrations at all. The contradiction was not a difference of opinion about what *should*
happen — it was an input that could not be implemented without deleting a live architecture test
(`40-testing.md` §40.1 forbids that outright) and introducing a second schema authority.

The amendment withdraws the **EF attribution only**. The requirement the item actually carries —
*one versioned migration mechanism, executed as a gated step in CI/deploy, never at application
startup* — is preserved unchanged, and is now stated at the abstraction level at which it is
genuinely true: a **repository- and deployment-level** rule about migration ownership and execution
point, not a RagCore implementation detail and not a .NET framework choice.

**Authority for the replacement**

| Source | What it establishes |
|---|---|
| **A2** `Synthia-OverallArchitecture-final.md` §11.4(5) | Database, index and schema migrations are *controlled* as a deliberate release step |
| **A2** §8.1 | Azure Postgres is the platform store whose schema is at issue |
| `.claude/rules/50-database.md` §50.7 | Alembic under `ragcore/migrations/` is the schema migration mechanism; the .NET side owns **no** migrations; no second migration tool, no second migration directory, no startup-time DDL |
| `.claude/rules/80-security-ops.md` §80.6 | Migrations run as a gated job *before* revision activation, and must be backward-compatible with the revision still serving |
| `ragcore/alembic.ini` | *"Alembic — the only tool that changes the platform schema"*; migrations run as a gated job, never at application startup |
| `.github/workflows/migrations.yml` | The gated job itself: single head, upgrade from base, models match DDL, every downgrade |
| `dotnet/tests/Synthia.ArchitectureTests/NoMigrationTests.cs` | The .NET deployable owns no schema; `Database.Migrate()`, `EnsureCreated()` and EF migration files are prohibited and mechanically gated |

`docs/adr/0003-database-migrations-and-rollback.md` records the same decision historically. Per
`.claude/rules/70-adr.md` §70.1 it is cited here as **history and evidence**, never as the authority
for the replacement text.

**Classification**

| Question | Answer |
|---|---|
| Was this an explicit human decision? | **Yes.** Supplied in the Phase 10 brief and not inferred from any other signal (`00-authority.md` §00.10) |
| Affected stacks | `.NET / C#` (`dotnet/**`), Python (`ragcore/**`), database, deployment pipeline |
| Architecture change? | **No.** Schema ownership, the store, the trust boundary and the deployment ordering are identical before and after |
| Engineering-baseline change? | **Yes** — to the baseline *input*, bringing it into agreement with the migrated rule already in force |
| ADR required? | **No** — see §A.2 |

### A.2 — Why this amendment requires no ADR

Assessed against `.claude/rules/70-adr.md` §70.2, trigger by trigger:

| Trigger | Applies? | Why |
|---|---|---|
| **A(1)–(7)** architecture change | No | No component, zone, trust boundary, tenant boundary, identity/authority semantic, topology or store changes. Schema ownership is the same after the amendment as before it |
| **A(8)** contradiction between two authoritative *architecture* documents | No | A1, A2 and A3 do not disagree with each other here. The outlier was a single line of the baseline **input** block, against which A2 and `50-database.md` already agreed |
| **B(1)–(5)** analyzer/lint/warning relaxation | No | No analyzer severity, Ruff selection, `noqa`, `pragma`, nullability or warning setting is touched |
| **B(6)** mandatory engineering convention changed | No | Layout, naming, dependency direction, test placement, commit and versioning conventions are untouched |
| **B(7)** contradicts a migrated baseline rule | No | The opposite: it **removes** a contradiction with `50-database.md`. `20-dotnet.md` `BL-10` already recorded that `50-database.md` governs, so no rule in force changes |
| **C** LangGraph architecture (`30-langgraph.md` §30.4) | No | No trigger on that list is touched. Checkpoint persistence, ownership and the `langgraph` schema exclusion are unchanged |
| **D(1)–(5)** database authorization boundary | No | No change to identity-bearing immutability, to roles/principals/grants, to where an invariant lives, or to checkpoint-persistence ownership |

**Determination: no ADR is required, and none was invented** (Phase 10 brief §2;
`70-adr.md` §70.2). The amendment changes no governed behaviour: it corrects an input to say what
the operative rule already said.

**What was deliberately *not* done.** No EF migration file, EF migration bundle, second migration
directory, second schema authority or startup DDL was introduced. No test was deleted, skipped,
loosened or narrowed. `NoMigrationTests` is untouched.

### A.3 — Amendments deliberately *not* made

| Item | Status | Why not amended here |
|---|---|---|
| `BL-08` | Truncated in this block (*"Offset/limitOutbound resilience pipeline"*), defect **D-2**, decision **UD-4** | The missing text cannot be recovered from any authoritative source. Reconstructing it would be invention. **Open** |
| `BL-38` / `BL-39` | Mutually unsatisfiable as written, conflict **CF-2**, decision **UD-6** | No human decision was supplied for it in this phase. **Open** |

