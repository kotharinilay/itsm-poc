using Microsoft.Extensions.DependencyInjection;
using Synthia.Persistence;

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

        services.AddSynthiaReadContext();

        // One implementation, two audience-shaped interfaces. The split is not ceremony: it is
        // what stops a customer endpoint reaching a staff query by autocomplete, and it keeps each
        // audience's surface readable on its own.
        services.AddScoped<SessionReadModel>();
        services.AddScoped<ICustomerSessionReadModel>(provider => provider.GetRequiredService<SessionReadModel>());
        services.AddScoped<IStaffSessionReadModel>(provider => provider.GetRequiredService<SessionReadModel>());

        return services;
    }
}
