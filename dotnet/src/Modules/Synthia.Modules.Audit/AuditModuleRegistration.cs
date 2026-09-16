using Microsoft.Extensions.DependencyInjection;
using Synthia.Persistence;

namespace Synthia.Modules.Audit;

/// <summary>
/// Registration surface for the Audit module. The composition root
/// (<c>Synthia.Api/Program.cs</c>) is the only caller; a module never registers another.
/// </summary>
public static class AuditModuleRegistration
{
    /// <summary>Registers this module's services. Read-only: no write path exists here.</summary>
    /// <param name="services">The service collection owned by the composition root.</param>
    /// <returns>The same collection, for chaining.</returns>
    public static IServiceCollection AddAuditModule(this IServiceCollection services)
    {
        ArgumentNullException.ThrowIfNull(services);

        services.AddSynthiaReadContext();
        services.AddScoped<IAuditReadModel, AuditReadModel>();

        return services;
    }
}
