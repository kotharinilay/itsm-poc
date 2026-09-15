using Microsoft.Extensions.DependencyInjection;

namespace Synthia.Modules.Sessions;

/// <summary>
/// Registration surface for the Sessions module. The composition root
/// (<c>Synthia.Api/Program.cs</c>) is the only caller; a module never registers another.
/// </summary>
public static class SessionsModuleRegistration
{
    /// <summary>Registers this module's services. Read-only: no write path exists here.</summary>
    /// <param name="services">The service collection owned by the composition root.</param>
    /// <returns>The same collection, for chaining.</returns>
    public static IServiceCollection AddSessionsModule(this IServiceCollection services)
    {
        ArgumentNullException.ThrowIfNull(services);

        // Stage 5 wires read models over vw_*_v1 views. Nothing is registered at Stage 1.
        return services;
    }
}
