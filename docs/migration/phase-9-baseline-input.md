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

\- Migrations: EF Migrations bundle in CI/deploy step

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