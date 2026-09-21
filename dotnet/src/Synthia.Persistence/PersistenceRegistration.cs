using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace Synthia.Persistence;

/// <summary>
/// Registers the read context. Called by each module that reads; idempotent by design.
/// </summary>
/// <remarks>
/// <para>
/// Modules are the only projects that may reference persistence (plan §Dependency direction), so
/// registration happens through them rather than from <c>Synthia.Api</c> — the composition root
/// deliberately cannot reach past a module into the database, which is how a "quick query" in an
/// endpoint stops being possible.
/// </para>
/// <para>
/// Six modules call this and one context results. The guard is explicit rather than relying on
/// <c>TryAdd</c> semantics elsewhere, because a second registration would mean a second connection
/// pool and a second tenant filter to keep honest.
/// </para>
/// </remarks>
public static class PersistenceRegistration
{
    /// <summary>
    /// Registers <see cref="SynthiaReadContext"/> against the published views.
    /// </summary>
    /// <param name="services">The service collection owned by the composition root.</param>
    /// <returns>The same collection, for chaining.</returns>
    public static IServiceCollection AddSynthiaReadContext(this IServiceCollection services)
    {
        ArgumentNullException.ThrowIfNull(services);

        if (services.Any(descriptor => descriptor.ServiceType == typeof(SynthiaReadContext)))
        {
            return services;
        }

        services.AddOptions<ReadDatabaseOptions>()
            .BindConfiguration(ReadDatabaseOptions.Section)
            .ValidateDataAnnotations()
            .ValidateOnStart();

        services.AddDbContext<SynthiaReadContext>((provider, builder) =>
        {
            ReadDatabaseOptions options = provider.GetRequiredService<IOptions<ReadDatabaseOptions>>().Value;

            builder.UseNpgsql(
                options.ConnectionString,
                npgsql => npgsql.CommandTimeout(options.CommandTimeoutSeconds));

            // AsNoTracking is the default rather than a per-query decision (.claude/rules/20-dotnet.md §20.4
            // access). Nothing here is ever written back, so a change tracker would be pure cost —
            // and a tracked read model is an invitation to try.
            builder.UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking);

            builder.EnableSensitiveDataLogging(options.EnableSensitiveDataLogging);
        });

        return services;
    }
}
