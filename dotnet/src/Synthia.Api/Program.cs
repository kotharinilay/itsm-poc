using Synthia.Modules.Approvals;
using Synthia.Modules.Audit;
using Synthia.Modules.Governance;
using Synthia.Modules.Sessions;
using Synthia.Modules.Tenancy;
using Synthia.Modules.Work;

// THE ONLY COMPOSITION ROOT for the .NET deployable (plan §Composition roots).
// Service Locator and BuildServiceProvider-during-configuration are prohibited and tested
// for by T035. Every dependency is constructor-injected from here.
//
// This deployable is READ-ONLY (ADR-0001). No write endpoint exists, and none may be added.
// Stage 5 adds identity, correlation and problem-details middleware plus the views routes.

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddSessionsModule()
    .AddWorkModule()
    .AddApprovalsModule()
    .AddGovernanceModule()
    .AddAuditModule()
    .AddTenancyModule();

WebApplication app = builder.Build();

// Liveness is process-only, with no dependency checks (constitution §Health).
// Readiness (/health/ready) arrives in Stage 10, where there is a database to be ready for.
app.MapGet("/health/live", () => Results.Ok(new { status = "live" }));

await app.RunAsync().ConfigureAwait(false);

/// <summary>Entry point marker, so <c>WebApplicationFactory</c> can locate this assembly.</summary>
public partial class Program
{
    private Program()
    {
    }
}
