using Microsoft.Extensions.Options;
using Synthia.Api.Authorization;
using Synthia.Api.Configuration;
using Synthia.Api.Endpoints;
using Synthia.Api.Errors;
using Synthia.Api.Health;
using Synthia.Api.Http;
using Synthia.Api.Middleware;
using Synthia.Modules.Approvals;
using Synthia.Modules.Audit;
using Synthia.Modules.Governance;
using Synthia.Modules.Sessions;
using Synthia.Modules.Tenancy;
using Synthia.Modules.Work;
using Synthia.Observability;
using Synthia.SharedKernel.Identity;

// THE ONLY COMPOSITION ROOT for the .NET deployable (plan §Composition roots).
// Service Locator and BuildServiceProvider-during-configuration are prohibited and tested for by
// CompositionRootTests. Every dependency is constructor-injected from here.
//
// This deployable is READ-ONLY (ADR-0001). No write endpoint exists, and none may be added.

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

// Configuration sources, in the order the constitution fixes: appsettings.json, then
// appsettings.{Environment}.json, then environment variables — all established by CreateBuilder —
// then secret references from Key Vault, added last so a secret always wins over a placeholder.
KeyVaultOptions keyVault = builder.AddSynthiaKeyVault();

builder.Services.AddSynthiaConfiguration();
builder.Services.AddSynthiaObservability(builder.Configuration);
builder.Services.AddSynthiaHttpDefaults();

// One object behind six interfaces: three read halves the application consumes, three write halves
// only the identity middleware is given. See RequestScope for why the split is a control.
builder.Services.AddScoped<RequestScope>();
builder.Services.AddScoped<ITenantScope>(provider => provider.GetRequiredService<RequestScope>());
builder.Services.AddScoped<ITenantScopeWriter>(provider => provider.GetRequiredService<RequestScope>());
builder.Services.AddScoped<IPrincipalScope>(provider => provider.GetRequiredService<RequestScope>());
builder.Services.AddScoped<IPrincipalScopeWriter>(provider => provider.GetRequiredService<RequestScope>());
builder.Services.AddScoped<ICorrelationScope>(provider => provider.GetRequiredService<RequestScope>());
builder.Services.AddScoped<ICorrelationScopeWriter>(provider => provider.GetRequiredService<RequestScope>());

builder.Services
    .AddSessionsModule()
    .AddWorkModule()
    .AddApprovalsModule()
    .AddGovernanceModule()
    .AddAuditModule()
    .AddTenancyModule();

builder.Services.AddExceptionHandler<ProblemDetailsExceptionHandler>();
builder.Services.AddProblemDetails();

// camelCase in both directions, on both deployables (contracts §README).
builder.Services.ConfigureHttpJsonOptions(options => JsonConventions.Apply(options.SerializerOptions));

// Built-in OpenAPI, generated from the application contracts rather than hand-maintained.
builder.Services.AddOpenApi();

// The section name rather than IOptions<ReadDatabaseOptions>. That options type belongs to
// Synthia.Persistence, and the composition root deliberately cannot reference it (plan §Dependency
// direction) — reaching past a module into the database is exactly what that rule prevents.
builder.Services.AddSynthiaHealthChecks("ReadDatabase");

WebApplication app = builder.Build();

// MIDDLEWARE ORDER IS FIXED BY THE CONSTITUTION and is not a matter of taste:
//   exception handling -> correlation -> request logging -> trace context -> authentication
//   -> authorization -> validation -> endpoint.
//
// Correlation and trace context are established BEFORE request logging, which is what makes every
// record of a request carry its identifier — including the record of the request failing.
// Authentication runs before tenant resolution and authorization.
app.UseExceptionHandler();
app.UseMiddleware<CorrelationMiddleware>();
app.UseMiddleware<IdentityContextMiddleware>();

app.MapSynthiaHealth();
app.MapCustomerViewEndpoints();
app.MapStaffViewEndpoints();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

LogStartup(app, keyVault);

await app.RunAsync().ConfigureAwait(false);

static void LogStartup(WebApplication app, KeyVaultOptions keyVault)
{
    ILogger logger = app.Services.GetRequiredService<ILoggerFactory>().CreateLogger("Synthia.Api");
    IOptions<ContainerAppsOptions> runtime = app.Services.GetRequiredService<IOptions<ContainerAppsOptions>>();

    // Whether a vault is in use, never the vault's address. The URI is not a secret, but it names
    // an attack surface, and a start-up banner is the most widely copied line in any log.
    StartupLog.Ready(logger, keyVault.IsConfigured, runtime.Value.ShutdownTimeoutSeconds);
}

/// <summary>Start-up log messages.</summary>
internal static partial class StartupLog
{
    /// <summary>Records that the process finished configuring itself.</summary>
    /// <param name="logger">The logger.</param>
    /// <param name="keyVaultConfigured">Whether secrets resolve through a vault.</param>
    /// <param name="shutdownTimeoutSeconds">The drain period this process will honour.</param>
    [LoggerMessage(
        EventId = 1301,
        Level = LogLevel.Information,
        Message = "Synthia read-only monolith ready. KeyVaultConfigured={KeyVaultConfigured}, " +
                  "ShutdownTimeoutSeconds={ShutdownTimeoutSeconds}.")]
    public static partial void Ready(ILogger logger, bool keyVaultConfigured, int shutdownTimeoutSeconds);
}

/// <summary>Entry point marker, so <c>WebApplicationFactory</c> can locate this assembly.</summary>
public partial class Program
{
    private Program()
    {
    }
}
