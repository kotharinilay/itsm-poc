using Microsoft.Extensions.DependencyInjection;

namespace Synthia.Modules.Work;

/// <summary>
/// Registration surface for the Work module. The composition root
/// (<c>Synthia.Api/Program.cs</c>) is the only caller; a module never registers another.
/// </summary>
/// <remarks>
/// <b>This module registers nothing yet, and that is the honest state.</b> The Work context has a
/// published view — <c>vw_work_item_v1</c>, mapped in <c>SynthiaReadContext</c> because the view
/// contract is what this deployable implements — but neither <c>contracts/customer-api.md</c> nor
/// <c>contracts/staff-api.md</c> defines a route that reads it. Work state reaches the staff
/// surfaces today through the approval queue and the unexecuted surface, which the Approvals module
/// owns.
/// <para>
/// A read model here with no caller would be a capability built before a requirement needed it
/// (.claude/rules/10-principles.md P-8) and a scaffold pretending to be further along than it is
/// (.claude/rules/10-principles.md H-1). The module boundary exists and is enforced; its read
/// surface arrives with the
/// golden paths in Stages 12–13, where a route finally needs one.
/// </para>
/// </remarks>
public static class WorkModuleRegistration
{
    /// <summary>Registers this module's services. Read-only: no write path exists here.</summary>
    /// <param name="services">The service collection owned by the composition root.</param>
    /// <returns>The same collection, for chaining.</returns>
    public static IServiceCollection AddWorkModule(this IServiceCollection services)
    {
        ArgumentNullException.ThrowIfNull(services);

        return services;
    }
}
