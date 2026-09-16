using Microsoft.Extensions.DependencyInjection;
using Synthia.Persistence;

namespace Synthia.Modules.Approvals;

/// <summary>
/// Registration surface for the Approvals module. The composition root
/// (<c>Synthia.Api/Program.cs</c>) is the only caller; a module never registers another.
/// </summary>
public static class ApprovalsModuleRegistration
{
    /// <summary>Registers this module's services. Read-only: no write path exists here.</summary>
    /// <param name="services">The service collection owned by the composition root.</param>
    /// <returns>The same collection, for chaining.</returns>
    public static IServiceCollection AddApprovalsModule(this IServiceCollection services)
    {
        ArgumentNullException.ThrowIfNull(services);

        services.AddSynthiaReadContext();
        services.AddScoped<IApprovalReadModel, ApprovalReadModel>();

        return services;
    }
}
