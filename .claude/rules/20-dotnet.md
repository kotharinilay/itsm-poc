# 20 — .NET / C# engineering rules

## Scope

**This file governs `.NET / C#` code only.**

| Governs | Does not govern |
|---|---|
| `dotnet/**` — every project in `Synthia.sln`, including `dotnet/tests/**` | `ragcore/**`, `integrations/**` (Python — `.claude/rules/21-python.md`) |
| Any future `.csproj`/`.fsproj`/`.vbproj` in this repository | `apps/web/**`, `apps/desktop/**` (TypeScript/Angular/Electron — `.claude/rules/22-web-typescript.md`) |
| `dotnet/Directory.Build.props`, `dotnet/Directory.Packages.props`, `dotnet/.editorconfig` | `build/docker/**` and `.github/workflows/**` (`.claude/rules/80-security-ops.md`) |

Source scoping is the packs' own: `dotnet.yaml` and `dotnet_lang.yaml` both declare
`applied_when: language in [dotnet, csharp]`. **Nothing in this file is evidence of a Python,
TypeScript, Angular or Electron requirement**, and no rule here may be carried to another stack by
analogy (`.claude/rules/00-authority.md` §00.5).

Repository-wide principles in `.claude/rules/10-principles.md` apply to `dotnet/**` **in addition**
to everything here. This file states the .NET mechanism; it never relaxes the principle.

**Traceability.** Every rule carries `Source:`. Full mapping:
`docs/migration/phase-9-baseline-coverage.md`.

**Enforcement** vocabulary: `mechanical` | `partial` | `procedural` | `currently-unenforced`.
It states what gates the rule **today**, verified against `dotnet/Directory.Build.props`,
`dotnet/.editorconfig` and `.github/workflows/dotnet.yml`. A rule whose enforcement is
`currently-unenforced` is **still binding** — the gap is recorded, not an exemption.

---

## 20.1 Platform baseline and build strictness

### Target framework
**The .NET baseline is `net10.0`** (current LTS, Nov 2025 – Nov 2028). Projects target it via
`Directory.Build.props`; a project does not pin its own `TargetFramework`.
*Source: `dotnet.yaml#baseline` · Enforcement: mechanical (`Directory.Build.props`
`<TargetFramework>net10.0</TargetFramework>`)*

### The five strictness switches
These are emitted to `dotnet/Directory.Build.props` and apply to **every** project. They are the
switches that turn the rest of this file into build failures.

| # | Source | Switch | Realizes | Enforcement |
|---|---|---|---|---|
| **S1** | `dotnet.yaml#P-DN-S1` | `<Nullable>enable</Nullable>` | DN-6 | mechanical — set |
| **S2** | `dotnet.yaml#P-DN-S2` | `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>` | DN-7 | mechanical — set, plus `<CodeAnalysisTreatWarningsAsErrors>true</CodeAnalysisTreatWarningsAsErrors>` |
| **S3** | `dotnet.yaml#P-DN-S3` | `<EnableNETAnalyzers>true</EnableNETAnalyzers>` + `<AnalysisLevel>latest-Recommended</AnalysisLevel>` | DN-23 | mechanical — set |
| **S4** | `dotnet.yaml#P-DN-S4` | `<EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>` | (see note) | mechanical — set |
| **S5** | `dotnet.yaml#P-DN-S5` | `<Deterministic>true</Deterministic>` + `<ContinuousIntegrationBuild>true</ContinuousIntegrationBuild>` (CI only) | — (reproducible builds) | mechanical — set, CI-conditioned |

> **Recorded source defect (not repaired here).** `dotnet.yaml` records `P-DN-S4`
> (`EnforceCodeStyleInBuild`) as `realizes: lang/dotnet#DN19`, but `DN19` is the `goto` rule.
> `EnforceCodeStyleInBuild` is what makes the IDExxxx style rules build-failing, i.e. **DN-28 and
> DN-29**, and the pack's own inline comment says exactly that ("makes IDExxxx style rules
> (naming/formatting) build-failing; see P-DN-1"). This is an editorial defect in the source
> pointer, recorded as **D-1** in `docs/migration/phase-9-baseline-coverage.md` §9. Both DN-19 and
> DN-28/DN-29 are migrated in full below, so no requirement is lost either way. **The source is not
> edited under this phase.**

### Toolchain
These five entries carry **no `id:` field in the source**; their identifiers are the Phase 2 matrix
row ids, preserved here (`docs/migration/phase-9-baseline-coverage.md` §2).

| Source | Requirement | Emitted to | Enforcement |
|---|---|---|---|
| `dotnet.yaml#toolchain.analyzers` | `EnableNETAnalyzers=true`, `AnalysisLevel=latest-Recommended` | `Directory.Build.props` | mechanical |
| `dotnet.yaml#toolchain.formatter` | `dotnet format`, driven by a committed `.editorconfig` | `.editorconfig` | mechanical (`dotnet format --verify-no-changes` in `.github/workflows/dotnet.yml`) |
| `dotnet.yaml#toolchain.style_in_build` | `EnforceCodeStyleInBuild=true` | `Directory.Build.props` | mechanical |
| `dotnet.yaml#toolchain.warnings` | `TreatWarningsAsErrors=true`; `CodeAnalysisTreatWarningsAsErrors` is **not** set false, so CA findings block the build too | `Directory.Build.props` | mechanical |
| `dotnet.yaml#toolchain.packages` | `ManagePackageVersionsCentrally=true` — `Directory.Packages.props` is the single source of package versions | `Directory.Packages.props` | mechanical (also `CentralPackageTransitivePinningEnabled=true`) |

### DN-6 — Nullable reference types enabled project-wide
Set `<Nullable>enable</Nullable>` so every reference type is non-nullable unless declared `T?`.
**Resolve, do not silence, the resulting flow warnings.** CS8600/CS8602/CS8618 are compiler
diagnostics, active only under `<Nullable>enable</Nullable>`, and become errors under S2.
*Source: `lang/dotnet#DN6` · core · Enforcement: mechanical*

### DN-7 — Treat warnings as errors
`<TreatWarningsAsErrors>true</TreatWarningsAsErrors>` so analyzer and compiler warnings (including
the CS nullable codes and any CA raised to warning) fail the build.
*Source: `lang/dotnet#DN7` · core · Enforcement: mechanical*
> `Directory.Build.props` carries `<NoWarn>$(NoWarn);CS1591</NoWarn>` (missing XML doc comment)
> alongside `<GenerateDocumentationFile>true</GenerateDocumentationFile>`. Recorded as deviation
> **DV-7** in `docs/migration/phase-9-baseline-coverage.md` §8: it is a project-wide suppression of
> one compiler warning, which DN-21 would require to be scoped and justified.

### DN-23 — Analyzers on, analysis level pinned
`<EnableNETAnalyzers>true</EnableNETAnalyzers>` and `<AnalysisLevel>latest-Recommended</AnalysisLevel>`
so the analyzer baseline is current and reproducible across machines and CI. This is the meta-switch
that turns the CA family on; **per-rule severities still have to be bound in `.editorconfig`.**
*Source: `lang/dotnet#DN23` · core · Enforcement: mechanical*

---

## 20.2 Application architecture and composition

### BL-1 — Modular monolith
**The application architecture is a modular monolith.** One deployable .NET application composed of
modules with enforced internal boundaries — not a distributed set of services, and not an
unstructured single assembly.
*Source: `BL-01` · Enforcement: mechanical (`ModuleIsolationTests`, `BoundaryOwnershipTests`,
`.github/workflows/boundaries.yml`)*
> Platform topology — which deployables exist, and that RagCore and the Integrations Service are
> separate from this monolith — is owned by **A2**, not by this file.

### BL-2 — Dependency injection
**Constructor injection is the sole injection pattern, using the built-in
`Microsoft.Extensions.DependencyInjection` container and the built-in `IServiceProvider` as the
framework-native default.**

Banned anti-patterns, named explicitly by the source:
- **Service Locator** — resolving from a container, static accessor or ambient singleton inside
  business code instead of receiving the collaborator as a constructor parameter.
- **`BuildServiceProvider` in configuration** — do not call `IServiceCollection.BuildServiceProvider()`
  while configuring services; it creates a second container and a second set of singletons.

Do not introduce a third-party container.
*Source: `BL-02`; realizes `principles#P26` · Enforcement: mechanical for the service-locator ban
(`ServiceResolutionTests`, `CompositionRootTests`, `BannedApiTests.No_production_type_uses_a_service_locator`);
partial for the `BuildServiceProvider` ban*

### BL-3 — Module composition: logical boundaries
**Modules are composed as logical boundaries** — enforced by project/namespace structure and
architecture tests — not as separately deployed physical units.
*Source: `BL-03` · Enforcement: mechanical*

### BL-35 — Anti-corruption layer / adapter
**One port-and-adapter per external dependency. The port is owned by the integrating module; the
implementation lives in that module's infrastructure.** External vendor types never cross into the
domain.
*Source: `BL-35`; realizes `principles#P5`, `principles#P19` · Enforcement: partial (layering suites
gate the direction; per-dependency port ownership is review)*

### BL-36 — Provider abstraction and swap policy
**One adapter per concrete provider; a domain-shaped port only; no provider-neutral
super-abstraction.** Do not build a generic abstraction over a class of providers on the assumption
a second one will appear. **Swap later if a real second provider appears.**
*Source: `BL-36`; realizes `principles#P8` · Enforcement: procedural*

---

## 20.3 API surface and contracts

### BL-4 — API style and routing
**REST, implemented with Minimal APIs.** Not MVC controllers, not RPC.
*Source: `BL-04` · Enforcement: procedural*

### BL-5 — API versioning
**URI segment versioning** — the version is a path segment: `/api/v1/...`.
*Source: `BL-05` · Enforcement: partial (`ApimRoutingTests`)*

### BL-6 — OpenAPI / contract emission
**Code-first, using the built-in `OpenApi` support.** The contract is generated from the code, not
hand-maintained and not the source of the code.
*Source: `BL-06` · Enforcement: mechanical (`.github/workflows/contracts.yml`)*

### BL-7 — Request/response contract conventions
- **Casing:** camelCase JSON — the `System.Text.Json` default for .NET. Idiomatic for the .NET stack
  and for the TypeScript SPA client.
- **Naming:** resource-oriented **plural nouns** — `/api/v1/permits`, `/api/v1/master-cards`,
  `/api/v1/lockout-tags`.
- **Path segments:** kebab-case for multi-word segments.
- **HTTP verbs carry the action** — the action is never a segment in the path.

*Source: `BL-07` · Enforcement: partial (contract workflow diffs the emitted OpenAPI; the naming
grammar itself is review)*

### BL-8 — Pagination, filtering, sorting
- **Pagination, default:** keyset/cursor pagination for large or growing collections — the permit
  register (PRM-01), global search (ADM-15) and reporting result sets (RPT-\*) — using an **opaque
  cursor + limit**, with **stable ordering by a monotonic key**.
- **Filtering:** typed query-string parameters per endpoint
  (`?status=Issued&unit=...&from=...&to=...`), matching the advanced-filter requirements.
  **No generic OData-style expression language.**
- **Sorting:** `?sort=field` / `?sort=-field` (leading `-` = descending), **whitelisted fields
  only**.

*Source: `BL-08` · Enforcement: procedural*
> **Recorded source defect (not repaired here).** The source line for offset/limit pagination is
> truncated mid-sentence and runs into the next heading: *"Offset/limitOutbound resilience
> pipeline"*. What offset/limit pagination is permitted for — and whether it is permitted at all —
> **cannot be read from the source.** Recorded as **D-2** in
> `docs/migration/phase-9-baseline-coverage.md` §9; a human decision is required. Everything legible
> above is migrated in full.

### BL-18 — Input validation
**Use the .NET 10 built-in validation.** Do not add a third-party validation framework.
*Source: `BL-18`; realizes `principles#P11`, `principles#P20` · Enforcement: procedural*

### BL-19 — Error / result model
**`Result` + exceptions, with `IExceptionHandler` → `ProblemDetails`.**
Expected, modelled failures are returned as a `Result`; exceptional failures throw. An
`IExceptionHandler` converts an unhandled exception into an RFC `ProblemDetails` response at the
boundary. No raw exception detail reaches a client.
*Source: `BL-19`; realizes `principles#P30` · Enforcement: partial*

---

## 20.4 Data access and persistence

### BL-9 — Data access technology
**EF Core 10 + Npgsql.**
*Source: `BL-09` · Enforcement: mechanical (`Directory.Packages.props` pins the versions centrally;
`DataAccessDisciplineTests`)*

### BL-10 — Migrations — ⚠ CONFLICT, UNRESOLVED
The baseline block states: **"Migrations: EF Migrations bundle in CI/deploy step."**

This **conflicts** with `.claude/rules/50-database.md` §50.7 and with A2 §8.1, which establish that
**Alembic under RagCore is the single schema-migration mechanism and the .NET side owns no
migrations** — an invariant mechanically enforced by
`dotnet/tests/Synthia.ArchitectureTests/NoMigrationTests.cs`.

Per `.claude/rules/00-authority.md` §00.6 this is **recorded, not resolved.** It is conflict
**CF-1** in `docs/migration/phase-9-baseline-coverage.md` §9.

**Until a human resolves it, the governing rule in force is `.claude/rules/50-database.md`:** do not
introduce EF Core migrations, a second migration tool, a second migration directory, or startup-time
DDL. `50-database.md` is a mandatory governance rule with an accepted procedure and a live
mechanical gate; the baseline block is an unreconciled input. **Do not weaken or delete
`NoMigrationTests` to satisfy `BL-10`.**
*Source: `BL-10` · Enforcement: the **opposite** requirement is mechanically enforced*

### BL-11 — Transaction and concurrency model
**Optimistic concurrency only. No lock anywhere.** No pessimistic row locks, no `SELECT … FOR
UPDATE`, no application-level lock table. Conflicts are detected on write and retried or surfaced.
*Source: `BL-11` · Enforcement: procedural*

### BL-12 — Isolation level
**Read Committed by default; Serializable on invariant-bearing transactions.** Raise the isolation
level only for a transaction that enforces an invariant that Read Committed cannot hold.
*Source: `BL-12` · Enforcement: procedural*

### BL-13 — Data lifecycle
**Soft-delete + a global query filter + audit columns.** A delete marks the row; the global query
filter excludes soft-deleted rows from normal reads; audit columns record creation and modification.
Retention is realized on that basis.
*Source: `BL-13` · Enforcement: partial*
> Which stores exist, and their classification, residency and lifecycle, are owned by **A2 §8.1**.
> Schema changes that realize this go through `.claude/rules/50-database.md` first, in full.

### BL-14 — Query conventions
1. **Read paths use `AsNoTracking()`.**
2. **All queries are parameterized** (see DN-24 — never concatenate input into SQL).
3. **N+1 prevention** — project or eager-load deliberately; do not lazy-load in a loop.
4. **Compiled queries** on hot paths.

*Source: `BL-14`; (2) realizes `secure-coding#SC4` via DN-24 · Enforcement: partial
(`DataAccessDisciplineTests`; CA2100/CA3001 for the SQL half)*

### DN-24 — Parameterize all SQL
Use parameters (`cmd.Parameters.Add…`, Dapper `new { id }`, or EF LINQ / `FromSqlInterpolated`).
**Never string-concatenate user input into command text.** EF raw SQL uses interpolated
`FromSqlInterpolated`, **not** `FromSqlRaw($"...{input}...")`.
*Source: `lang/dotnet#DN24` · core · satisfies `secure-coding#SC4`, `anti-patterns#A25` ·
Enforcement: partial — CA2100 and CA3001 are **off by default** and are **not** bound in
`dotnet/.editorconfig`; they are active only if `latest-Recommended` enables them. The source
requires `severity = error` for both. Recorded as **DV-4**.*

---

## 20.5 Configuration and secrets

### BL-16 — Configuration layering
**Standard .NET host layering, in this order:**

```text
appsettings.json (defaults)
  → appsettings.{Environment}.json (env-specific)
    → environment variables (deployment / ACA)
      → ACA `secretref:` env vars for secret material   (last)
```

Later providers override earlier keys; environment variables win over files; **secrets arrive
through the same env-var channel** rather than a separate mechanism.
*Source: `BL-16`; realizes `principles#P27` · Enforcement: procedural*

### BL-17 — Strongly-typed configuration
**Bind each config section to a POCO options class via the .NET Options pattern:**

```csharp
builder.Services
    .AddOptions<MyOptions>()
    .BindConfiguration("Section")
    .ValidateDataAnnotations()
    .ValidateOnStart();
```

Consume through `IOptions<T>` / `IOptionsSnapshot<T>` / `IOptionsMonitor<T>`.
**Raw string-key configuration access (`Configuration["Foo:Bar"]`) in application/domain code is
banned.**
*Source: `BL-17`, `lang/dotnet#DN14` · Enforcement: see DN-14*

### DN-14 — No `IConfiguration["..."]` in app/domain code
Define a typed options class, register it with validation, and inject `IOptions<T>`. **No string-key
`IConfiguration["Key"]` reads outside the composition root.**
*Source: `lang/dotnet#DN14` · core · satisfies `anti-patterns#A14` · Enforcement:
**currently-unenforced** — the source's mechanism is `BannedApiAnalyzers` (RS0030) banning
`IConfiguration.get_Item` via `BannedSymbols.txt`. `Microsoft.CodeAnalysis.BannedApiAnalyzers` is
**not referenced** in `dotnet/Directory.Packages.props`, and no architecture test covers it.
Recorded as **DV-3 / EG-2**.*

### BL-15 — Secrets management
**Secrets live in Azure Key Vault and reach the app as Key Vault references resolved via managed
identity.** No secret in source, in an image, in a committed settings file, or in a build argument.
*Source: `BL-15`; realizes `principles#P27`, `principles#P17` · Enforcement: partial
(`AzureIdentityTests`, `.github/workflows/security.yml`) — see `.claude/rules/80-security-ops.md`
§80.3, which owns the repository-wide secret-handling policy*

---

## 20.6 Observability

### BL-20 / DN-3 — Structured logging
**`Microsoft.Extensions.Logging` + OpenTelemetry.** Inject `ILogger<T>` and emit structured events.
**`Console.WriteLine` is banned in application and library code**; reserve `Console.*` for the
composition-root / CLI entrypoint only.
*Source: `BL-20`, `lang/dotnet#DN3`; realizes `principles#P29` · Enforcement: mechanical via
`BannedApiTests.No_production_type_writes_to_the_console`. Note the source's named mechanism
(`BannedApiAnalyzers` RS0030) is **absent**; the architecture test is this repository's substitute
and is a genuine build-failing gate. Recorded as **DV-3**.*

### DN-30 — Constant message template, named placeholders
Pass a constant message template plus arguments —
`_logger.LogInformation("Order {OrderId} placed for {UserId}", orderId, userId)` — so the log keeps
its structure and placeholder/value correlation. **Never build the template with `+` concatenation
or `$"..."` interpolation**; that loses the structured fields.
*Source: `lang/dotnet#DN30` · satisfies `principles#P29` · Enforcement: partial — CA2254 is on by
default as a **suggestion**; the source requires `severity = error` and it is **not** bound in
`.editorconfig`. Recorded as **DV-4**.*

### DN-32 — PascalCase structured-logging placeholders
Name log placeholders in PascalCase (`{OrderId}`, `{UserName}`), not camelCase, so they become
consistent property names in structured-log sinks and are queryable across aggregated logs.
*Source: `lang/dotnet#DN32` · satisfies `principles#P29` · Enforcement: partial — CA1727 is off by
default and **not** bound in `.editorconfig`. Recorded as **DV-4**.*

### BL-22 / DN-31 — LoggerMessage source generation
For frequently hit log statements define a `[LoggerMessage(Level = ..., Message = "...")]` `partial`
method instead of calling `_logger.LogInformation(...)` directly. The source generator avoids boxing
value types and re-parsing the template on every call.
*Source: `BL-22`, `lang/dotnet#DN31` · satisfies `performance#PF11` · Enforcement:
**currently-unenforced** — `dotnet/.editorconfig:94` sets `dotnet_diagnostic.CA1848.severity =
suggestion`. The baseline requires `error`. **A suggestion is not raised to an error by
`TreatWarningsAsErrors`.** Recorded as **DV-2** — this is one of the enforcement claims Phase 7
found overstated in the Phase 2 matrix, independently re-verified in Phase 9.*

### BL-21 — Telemetry
**OpenTelemetry + the Azure Monitor Distro.**
*Source: `BL-21` · Enforcement: procedural*

### BL-24 — Context propagator
**Standard W3C Trace Context propagation (the OpenTelemetry default).** Baggage is limited to a
small, explicit allowlist — correlation id, and tenant/site id only if needed. **Do not add ad-hoc
propagation headers.**
*Source: `BL-24` · Enforcement: procedural*

### BL-27 — Correlation / request IDs
- Field name: **`X-Correlation-Id`** (header), surfaced as `RequestId`/`CorrelationId` in logs.
- **Accept** an inbound `X-Correlation-Id` if present and well-formed; **otherwise generate one.**
- **Echo it back** in the response header on **every** request.
- **Bind it** into the logging scope and into OTel baggage.

*Source: `BL-27` · Enforcement: partial*

### BL-25 — Health checks
**Three separated endpoints via `MapHealthChecks` with tag predicates:**

| Endpoint | Purpose | Contents |
|---|---|---|
| `/health/live` | liveness | `Predicate => false` — process-only, **no dependency checks** |
| `/health/ready` | readiness | tagged `ready`; includes PostgreSQL (`AddDbContextCheck`/Npgsql check) and critical dependencies |
| `/health/startup` | slow init | optional |

*Source: `BL-25` · Enforcement: procedural*

### BL-26 — Middleware order
**Outermost → innermost, in exactly this order:**

```text
exception handler
  → correlation / request-id
    → request logging
      → trace context (OTel)
        → auth (authn, then authz)
          → validation (edge)
            → endpoint
```

The error handler is outermost so it catches everything; correlation and trace context are
established before logging; **auth comes before the tenant resolver.**
*Source: `BL-26` · Enforcement: partial (`EdgeTrustPolicyTests`)*

---

## 20.7 Async, cancellation and concurrency

### BL-23 / DN-9 — Propagate `CancellationToken` everywhere
**Thread the `CancellationToken` through every async call, from the endpoint signature down to every
blocking I/O** — EF Core, Npgsql, `HttpClient`, ERP-sync. Honour it at every awaitable boundary.
**Never swallow `OperationCanceledException`.**
Rationale from the source: idiomatic .NET, prevents wasted work on client disconnect or shutdown,
and is required for clean ACA scale-in.
*Source: `BL-23`, `lang/dotnet#DN9` · core · Enforcement: mechanical —
`dotnet/.editorconfig:86` binds `dotnet_diagnostic.CA2016.severity = error`*

### DN-4 — Await; never `.Result` / `.Wait()` / `.GetAwaiter().GetResult()`
Make the caller `async` and `await` the task. These block a pool thread and deadlock under a
captured context.
*Source: `lang/dotnet#DN4` · core · satisfies `performance#PF1` · Enforcement: mechanical —
`CA1849.severity = error` catches them inside a `Task`-returning method, and
`BannedApiTests.No_production_code_reads_a_tasks_Result` covers the rest*

### DN-2 — `await Task.Delay`, never `Thread.Sleep`
Inside an `async` method use `await Task.Delay(n, cancellationToken)` so the thread returns to the
pool instead of blocking.
*Source: `lang/dotnet#DN2` · core · satisfies `performance#PF1` · Enforcement: mechanical
(`CA1849.severity = error`, plus `BannedApiTests.No_production_type_depends_on_Thread`)*

### DN-5 — `async Task`, not `async void`
Declare async methods as `async Task` / `async Task<T>` so callers can await and observe exceptions.
`async void` is permitted **only** for a genuine `EventHandler` signature.
*Source: `lang/dotnet#DN5` · Enforcement: **currently-unenforced** — the source's mechanism is
VSTHRD100 from `Microsoft.VisualStudio.Threading.Analyzers`, which is **not** referenced in
`Directory.Packages.props`. Recorded as **EG-3**.*

### DN-8 — `ConfigureAwait(false)` in library code
In reusable **library** code write `await SomethingAsync().ConfigureAwait(false)` so continuations do
not marshal back to a captured synchronization context. Not required in ASP.NET Core app code (no
ambient context).
*Source: `lang/dotnet#DN8` · Enforcement: **currently-unenforced** — `dotnet/.editorconfig:84` sets
`dotnet_diagnostic.CA2007.severity = none`, commented "off deliberately, not by oversight". The
baseline requires `severity = error` **for library projects**.*
> **Deviation DV-1, open.** This is a deliberate relaxation of a baseline rule with no ADR behind
> it, which is itself an ADR trigger under `.claude/rules/70-adr.md` §70.2 B(1). Phase 9 **records**
> it and **does not** change the configuration (`.claude/rules/00-authority.md` §00.7). The baseline
> stands: write `ConfigureAwait(false)` in library code. Resolving the deviation — either an ADR
> accepting the relaxation, or restoring the severity — is a human decision.

### BL-30 — Concurrency and consistency rules
**Async rules (above) + Container Apps Jobs for singleton work. No distributed lock.** Work that
must run exactly once runs as a Container Apps Job, not as a leader election or a lock in the
application.
*Source: `BL-30` · Enforcement: procedural · see also `.claude/rules/80-security-ops.md` §80.5 for
the runtime half*

### DN-27 — No mutable visible statics
Make shared static state `const` or `static readonly` (and deeply immutable). A mutable
`public static` field is a thread-safety hazard and hidden global coupling — encapsulate it behind a
method or an injected singleton.
*Source: `lang/dotnet#DN27` · satisfies `anti-patterns#A28`, `principles#P28` · Enforcement: partial
— CA2211 is on by default as a **suggestion**; the source requires `error`, not bound in
`.editorconfig`. Recorded as **DV-4**.*

---

## 20.8 Outbound calls and messaging

### BL-32 — Outbound HTTP client conventions
- **Typed clients** registered via `IHttpClientFactory` (`services.AddHttpClient<T>()`).
- **One typed client per adapter/dependency.**
- **Base address and default headers configured at registration.**
- **Pooled `HttpMessageHandler` reuse** (the factory default — avoids socket exhaustion, `PF5`).
- **No manual `new HttpClient()` anywhere.**

*Source: `BL-32` · Enforcement: partial*

### BL-28 — Outbound resilience pipeline
**`Microsoft.Extensions.Http.Resilience` standard handler (Polly v8).**
*Source: `BL-28` · Enforcement: procedural*

### BL-31 — Outbound interceptor chain
**A `DelegatingHandler` chain via `IHttpClientFactory`, with resilience innermost.**
*Source: `BL-31` · Enforcement: procedural*

### BL-29 — Idempotency
**An idempotency-key filter + a Postgres store + outbound dedup keys.**
*Source: `BL-29`; realizes `principles#P21` · Enforcement: partial (an idempotency record table
exists — `ragcore/migrations/versions/0015_idempotency_record.py`)*
> Signed, idempotent **execution inside the graph** is A3 / ADR-011 and is governed by
> `.claude/rules/30-langgraph.md` §30.4(9). Changing it is a LangGraph architecture change, not an
> application detail.

### BL-33 — Outbox pattern
**A transactional outbox in PostgreSQL.**
*Source: `BL-33` · Enforcement: partial (`ragcore/migrations/versions/0014_outbox_message.py`)*

### BL-34 — Transport / broker
**Azure Service Bus Standard.** See `.claude/rules/80-security-ops.md` §80.5; platform topology is
owned by **A2**.
*Source: `BL-34` · Enforcement: procedural*

### DN-17 — Return read-only collection types from public APIs
Type public return values and properties as `IReadOnlyList<T>` / `IReadOnlyCollection<T>` /
`IEnumerable<T>`. Do not expose `List<T>` (mutable, over-broad) or `T[]` (a property returning an
array reallocates and leaks internal state).
*Source: `lang/dotnet#DN17` · satisfies `principles#P18`, `principles#P25` · Enforcement: partial —
CA1002 and CA1819 are off by default and **not** bound in `.editorconfig`. Recorded as **DV-4**.*

### DN-22 — `[LibraryImport]` over `[DllImport]`
Declare native interop with `[LibraryImport("lib")]` on a `partial` method so marshalling is
source-generated and AOT-compatible, instead of the reflection-based `[DllImport]`.
*Source: `lang/dotnet#DN22` · Enforcement: partial — SYSLIB1054 is informational by default; the
source requires `severity = error`, not bound. Recorded as **DV-4**.*

### DN-36 — Guard platform-specific APIs
Wrap calls to `[SupportedOSPlatform]`/`[UnsupportedOSPlatform]`-annotated APIs in an
`OperatingSystem.IsWindows()` (etc.) guard, or annotate your own API to forward the requirement. Do
not call a platform-specific API from platform-neutral code paths.
*Source: `lang/dotnet#DN36` · Enforcement: mechanical — CA1416 is on by default as a **warning** for
.NET 5+, so it is already build-failing under DN-7. The source additionally asks for an explicit
`severity = error` for determinism; that binding is absent. Recorded as **DV-5** (low impact).*

---

## 20.9 Types, encapsulation and correctness

### DN-1 — `DateTimeOffset.UtcNow` or an injected `TimeProvider`; never `DateTime.Now`
For a timestamp write `DateTimeOffset.UtcNow`. For anything testable, inject `TimeProvider`
(.NET 8+) and call `_timeProvider.GetUtcNow()`. `DateTime.Now` / `DateTime.Today` bind to machine-
local time and are unmockable.
*Source: `lang/dotnet#DN1` · Enforcement: mechanical via
`BannedApiTests.No_production_type_depends_on_DateTime_directly`. The source's named mechanism
(BannedApiAnalyzers RS0030) is absent; the architecture test is the substitute. Recorded as
**DV-3**.*

### DN-10 — Catch specific exception types
Catch the narrowest exception you can handle (`catch (SqlException)`), act on it, and rethrow or
translate. A top-level `catch (Exception)` is allowed **only** at a process/request boundary that
logs and re-signals — **never an empty or swallowing catch**.
*Source: `lang/dotnet#DN10` · core · satisfies `anti-patterns#A15`, `principles#P30` · Enforcement:
mechanical — `dotnet/.editorconfig:90` binds `CA1031.severity = error`, plus
`BannedApiTests.No_production_catch_of_Exception_swallows_it`*

### DN-26 — Rethrow preserving the stack
Use bare `throw;` to rethrow, or `throw new WrapperException("...", ex)` to wrap with the inner
preserved. **Never `throw ex;`** — it resets the stack trace to the rethrow site.
*Source: `lang/dotnet#DN26` · core · satisfies `anti-patterns#A30`, `principles#P30` · Enforcement:
mechanical — CA2200 is on by default as a **warning**, therefore build-failing under DN-7. The
source additionally asks for `severity = error`; binding absent (**DV-5**).*

### DN-15 — Dispose owned resources
Wrap owned disposables in `using var x = ...;` (or `await using` for `IAsyncDisposable`). In a
finalizable type call `GC.SuppressFinalize(this)` from `Dispose()`. Undisposed owned resources leak
handles and connections.
*Source: `lang/dotnet#DN15` · satisfies `principles#P31` · Enforcement: partial — CA2000 is off by
default and not bound; CA1816 is on as a suggestion. The source requires `error` for both. Recorded
as **DV-4**.*

### DN-16 — Validate arguments at public boundaries
At the top of a public method, guard inputs:
`ArgumentNullException.ThrowIfNull(order);`, `ArgumentOutOfRangeException.ThrowIfNegative(qty);`.
Fail fast before the value propagates.
*Source: `lang/dotnet#DN16` · satisfies `secure-coding#SC2`, `principles#P11` · Enforcement:
mechanical **by a different mechanism than the baseline states** — `dotnet/.editorconfig:92` sets
`CA1062.severity = warning`, which is build-failing only because `TreatWarningsAsErrors=true`. The
baseline requires `severity = error`.*
> **Deviation DV-6, open (low severity).** The rule *is* gated today, so Phase 7's concern is about
> the mechanism, not the outcome: if `TreatWarningsAsErrors` were ever scoped down, DN-16 would
> stop being enforced silently. Recorded; configuration not changed.

### DN-12 — Properties, not visible instance fields
Replace `public int Count;` with `public int Count { get; private set; }` (or an init-only/readonly
property). Public fields break encapsulation and binary versioning.
*Source: `lang/dotnet#DN12` · satisfies `principles#P18` · Enforcement: partial — CA1051 off by
default, not bound (**DV-4**). The source notes the fix is **breaking**.*

### DN-11 — Seal classes not designed for inheritance
Declare concrete classes `sealed` unless a subclass is a designed extension point. This gives the
JIT devirtualization headroom and states intent.
*Source: `lang/dotnet#DN11` · satisfies `principles#P17`, `principles#P10` · Enforcement: partial —
CA1852 seals **internal** types only and is off by default/not bound; sealing **public** types is
convention with no in-box analyzer (**DV-4**).*

### DN-20 — Records / readonly structs for value types
Model value-like domain types as `record` / `readonly record struct` with `init`-only or `required`
members, giving value equality and immutability by construction (C# 11+).
*Source: `lang/dotnet#DN20` · satisfies `principles#P25` · Enforcement: procedural — the source
records that no in-box analyzer selects record-vs-class*

### DN-18 — Explicit `StringComparison` / `IFormatProvider`
Pass an explicit comparison — `s.Equals(other, StringComparison.Ordinal)`,
`s.StartsWith(x, StringComparison.OrdinalIgnoreCase)` — and an `IFormatProvider`
(`value.ToString(CultureInfo.InvariantCulture)`) for machine-facing formatting.
*Source: `lang/dotnet#DN18` · Enforcement: partial — CA1305, CA1307 and CA1310 are off by default
and not bound (**DV-4**). Note `Directory.Build.props` sets `<InvariantGlobalization>true</InvariantGlobalization>`,
which changes runtime behaviour but does **not** discharge the rule.*

### DN-13 — `System.Text.Json` for new serialization
Serialize with `System.Text.Json` (`JsonSerializer`, `[JsonPropertyName]`, source-gen
`JsonSerializerContext` for AOT). Pull in `Newtonsoft.Json` **only** for a capability STJ lacks, and
**document why**.
*Source: `lang/dotnet#DN13` · Enforcement: **currently-unenforced** — the source's mechanism is a
BannedApiAnalyzers ban on the `Newtonsoft.Json` namespace; the package is absent and no architecture
test covers it. Recorded as **DV-3 / EG-2**.*

### DN-33 — Concrete types where dispatch is provably avoidable
When a local, field, parameter or return can be typed as the concrete class instead of an
interface/abstract base **without changing behavior**, do so — it removes virtual/interface dispatch
and enables inlining. Applies **only** where the analyzer proves the dispatch is avoidable; keep
abstractions at genuine seams per `principles#P19`.
*Source: `lang/dotnet#DN33` · satisfies `performance#PF11` · Enforcement: partial — CA1859 is on by
default as a suggestion; the source requires `error`, not bound (**DV-4**)*

### DN-37 — Remove dead conditional code
Do not leave conditionals (null checks, comparisons) that dataflow analysis proves are always `true`
or always `false`, nor the unreachable branch they guard. Delete the dead branch or fix the logic
that made it unreachable.
*Source: `lang/dotnet#DN37` · satisfies `principles#P7`, `principles#P8` · Enforcement:
currently-unenforced — CA1508 is off by default and not bound. The source notes it performs
expensive dataflow analysis and may need scoping (**DV-4**).*

### DN-19 — No unstructured control flow (`goto`)
Express control flow with loops, `break`/`continue`, early return, or pattern-matched `switch`
expressions. **Do not use `goto`** — the rare documented `switch`-fallthrough case is the only
exception.
*Source: `lang/dotnet#DN19` · Enforcement: **currently-unenforced** — the source is explicit that no
in-box analyzer covers `goto` and that this must be discharged by a **custom Roslyn/structural
check failing on `GotoStatementSyntax`** (`pr_review` is explicitly **not** acceptable for an
`absent`-mode rule). No such check exists. Recorded as **EG-4**.*

---

## 20.10 Cryptography and transport security

### DN-25 — No weak or broken cryptographic algorithms
Use `SHA256`/`SHA512` for hashing, `Aes` (AES-GCM) for symmetric encryption, and a KDF
(`Rfc2898DeriveBytes`/PBKDF2, or Argon2 via a vetted package) for passwords. **Never MD5, SHA1, DES,
TripleDES or RC2** for security-sensitive work.
*Source: `lang/dotnet#DN25` · core · satisfies `secure-coding#SC22` · Enforcement: partial — CA5350
and CA5351 are off by default and not bound (**DV-4**)*

### DN-34 — Never disable TLS certificate validation
Do not assign a certificate-validation callback that returns `true` unconditionally. Validate the
chain (`sslPolicyErrors == SslPolicyErrors.None`); if a custom trust is genuinely needed, scope it to
a specific host and a pinned thumbprint — **never globally accept every certificate**.
*Source: `lang/dotnet#DN34` · core · satisfies `secure-coding#SC30` · Enforcement: partial — CA5359
off by default, not bound (**DV-4**)*

### DN-35 — No deprecated TLS/SSL protocol versions
Do not set `ServicePointManager.SecurityProtocol` or an `SslProtocols` value to `Ssl3`, `Tls`,
`Tls11` (or the raw integers). Prefer `SslProtocols.None` / the `SecurityProtocolType` default so
the OS negotiates a current version (TLS 1.2/1.3).
*Source: `lang/dotnet#DN35` · core · satisfies `secure-coding#SC30` · Enforcement: partial — CA5364
and CA5397 off by default, not bound (**DV-4**)*

---

## 20.11 Style, naming and suppressions

### DN-28 / P-DN-1 — C# naming
PascalCase for types, methods, properties and public members; camelCase for parameters and locals;
`_camelCase` for private instance fields; `I`-prefixed interfaces; **one top-level type per file**.
The exact scheme is codified in `dotnet/.editorconfig`.
*Source: `lang/dotnet#DN28`, `dotnet.yaml#P-DN-1` · Enforcement: mechanical —
`dotnet_diagnostic.IDE1006.severity = error` plus the naming rules, made build-failing by
`EnforceCodeStyleInBuild`. One documented relaxation: `CA1707.severity = none` under `tests/**`
only, for sentence-style test method names — naming only, never a correctness analyzer.*
> "One top-level type per file" has no analyzer behind it and is review-gated.

### DN-29 / P-DN-1b — Formatting
A single committed `.editorconfig` formatting section owns indentation, spacing, new-lines and
`using` ordering, and the build enforces it, so formatting is never a review topic.
*Source: `lang/dotnet#DN29`, `dotnet.yaml#P-DN-1b` · Enforcement: mechanical —
`dotnet_diagnostic.IDE0055.severity = error`, plus `dotnet format --verify-no-changes` in
`.github/workflows/dotnet.yml`*

### DN-21 — Every suppression is scoped and justified
**Every `#pragma warning disable` / `SuppressMessage` is scoped and carries a justification.**

- Suppress **narrowly and locally**: re-enable with `#pragma warning restore`, or use
  `[SuppressMessage(..., Justification = "why")]` with a **non-empty** justification.
- **No file-wide or project-wide blanket disables.**

*Source: `lang/dotnet#DN21` · Enforcement: procedural — the source records that no in-box analyzer
exists and names a custom analyzer requiring a non-empty `Justification` as the mechanical upgrade
path (**EG-5**).*
> This is the **engineering requirement**. It is distinct from, and not replaced by, the governance
> gate in `.claude/rules/70-adr.md` §70.2 B(4), which says that *adding an unjustified suppression*
> requires an ADR. Phase 7 found the gate present and the requirement missing
> (`docs/migration/phase-7-validation.md` §4.4); both are now stated.
> `Directory.Build.props`'s project-wide `NoWarn` of CS1591 is the one existing instance that this
> rule would reach — recorded as **DV-7**, not repaired here.

---

## 20.12 Tests

Test-project rules — identical strictness, layout and naming — are in
`.claude/rules/40-testing.md` §40.2 (`dotnet.yaml#P-DN-2`, `#P-DN-3`). They are not duplicated here.
