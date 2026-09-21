using Microsoft.Extensions.Diagnostics.HealthChecks;

namespace Synthia.Api.Health;

/// <summary>
/// The two probes Container Apps calls, and the difference between them.
/// </summary>
/// <remarks>
/// <para>
/// <b>They answer different questions and must not be merged.</b> Liveness asks whether the
/// process should be restarted; readiness asks whether it should receive traffic. A liveness probe
/// that checks the database restarts every replica when the database has a bad minute, turning a
/// dependency blip into an outage.
/// </para>
/// <para>
/// Neither probe is an audience, so neither carries identity — see <c>AudienceRouting</c>.
/// </para>
/// </remarks>
internal static class HealthEndpoints
{
    /// <summary>The tag marking checks that belong to readiness.</summary>
    public const string ReadyTag = "ready";

    /// <summary>Maps the liveness and readiness probes.</summary>
    /// <param name="app">The application being built.</param>
    /// <returns>The same application, for chaining.</returns>
    public static WebApplication MapSynthiaHealth(this WebApplication app)
    {
        ArgumentNullException.ThrowIfNull(app);

        // Process-only, with no dependency checks (.claude/rules/20-dotnet.md BL-25). If this responds, the
        // process is running and the pipeline is intact; that is the whole claim.
        app.MapHealthChecks("/health/live", new()
        {
            Predicate = _ => false,
        })
        .WithName("HealthLive")
        .WithSummary("Liveness. Process-only; performs no dependency check.")
        .ExcludeFromDescription();

        // Database and critical dependency readiness. A replica failing this is taken out of
        // rotation, not restarted — which is the correct response to a dependency that is
        // temporarily unreachable.
        app.MapHealthChecks("/health/ready", new()
        {
            Predicate = registration => registration.Tags.Contains(ReadyTag),
        })
        .WithName("HealthReady")
        .WithSummary("Readiness. Covers the read database and critical dependencies.")
        .ExcludeFromDescription();

        return app;
    }

    /// <summary>
    /// Registers the checks readiness consults.
    /// </summary>
    /// <remarks>
    /// The connection string is resolved lazily, from the container, rather than read eagerly here.
    /// Eager reading put this registration <i>ahead</i> of options validation, so a deployment
    /// missing the setting failed with "Value cannot be null. (Parameter 'connectionString')"
    /// instead of the message naming the setting — which is the opposite of what fail-fast
    /// configuration is for (quickstart V17).
    /// </remarks>
    /// <param name="services">The service collection owned by the composition root.</param>
    /// <param name="configurationSection">The section holding the read principal's settings.</param>
    /// <returns>The same collection, for chaining.</returns>
    public static IServiceCollection AddSynthiaHealthChecks(
        this IServiceCollection services,
        string configurationSection)
    {
        ArgumentNullException.ThrowIfNull(services);

        services.AddHealthChecks()
            .AddNpgSql(
                provider => provider.GetRequiredService<IConfiguration>()
                    .GetSection(configurationSection)["ConnectionString"] ?? string.Empty,
                name: "read-database",
                failureStatus: HealthStatus.Unhealthy,
                tags: [ReadyTag]);

        return services;
    }
}
