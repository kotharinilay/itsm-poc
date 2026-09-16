using Microsoft.Extensions.DependencyInjection;
using Synthia.Persistence;

namespace Synthia.Modules.Tenancy;

/// <summary>
/// Registration surface for the Tenancy module. The composition root
/// (<c>Synthia.Api/Program.cs</c>) is the only caller; a module never registers another.
/// </summary>
public static class TenancyModuleRegistration
{
    /// <summary>Registers this module's services. Read-only: no write path exists here.</summary>
    /// <param name="services">The service collection owned by the composition root.</param>
    /// <returns>The same collection, for chaining.</returns>
    public static IServiceCollection AddTenancyModule(this IServiceCollection services)
    {
        ArgumentNullException.ThrowIfNull(services);

        services.AddSynthiaReadContext();

        services.AddScoped<ITenantRegistry, TenantRegistry>();
        services.AddScoped<TenantReadModel>();
        services.AddScoped<ITenantReadModel>(provider => provider.GetRequiredService<TenantReadModel>());
        services.AddScoped<IDashboardReadModel>(provider => provider.GetRequiredService<TenantReadModel>());

        return services;
    }
}
