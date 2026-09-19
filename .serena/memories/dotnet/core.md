# .NET modular monolith (`dotnet/`) — READ-ONLY (ADR-0001)

Exposes no write endpoint, ever. Reads PostgreSQL only through RagCore-owned versioned views.

- `Synthia.sln`; `src/Synthia.Api/Program.cs` = the only composition root (Endpoints, Authorization, Middleware, Contracts/OpenAPI, Paging, Querying, Health).
- `src/Modules/Synthia.Modules.{Sessions,Work,Approvals,Governance,Audit,Tenancy}` — read models + `*ModuleRegistration.cs` (`Add<X>Module()`), `AssemblyMarker.cs`.
- `Synthia.Persistence` — `SynthiaReadContext`, `Views/`, conventions; Api must not reference its options type directly (dependency direction rule).
- `Synthia.Contracts` (read models, boundaries, errors, paging), `Synthia.SharedKernel` (identity: `RequestScope` split into read/writer interfaces for tenant/principal/correlation), `Synthia.Observability`.
- Tests: ArchitectureTests (dependency/composition-root rules), AuthorizationTests, TenantIsolationTests, ContractTests, per-module tests.
