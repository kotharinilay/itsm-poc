using Microsoft.Extensions.DependencyInjection;

namespace Synthia.Modules.Governance;

/// <summary>
/// Registration surface for the Governance module. The composition root
/// (<c>Synthia.Api/Program.cs</c>) is the only caller; a module never registers another.
/// </summary>
/// <remarks>
/// <b>This module registers nothing yet, and that is the honest state.</b> The catalogue has a
/// published view — <c>vw_governance_catalogue_v1</c>, mapped in <c>SynthiaReadContext</c> — but no
/// route in the frozen API contracts reads it, and the catalogue holds only inert reference
/// fixtures until Stage 11 seeds them.
/// <para>
/// Nothing decided here in any case: <b>deterministic governance lives in RagCore and the model
/// only proposes</b> (A3 §6.3). This module is a read model for a catalogue,
/// never a place a treatment is chosen. Its read surface arrives when a route needs one.
/// </para>
/// </remarks>
public static class GovernanceModuleRegistration
{
    /// <summary>Registers this module's services. Read-only: no write path exists here.</summary>
    /// <param name="services">The service collection owned by the composition root.</param>
    /// <returns>The same collection, for chaining.</returns>
    public static IServiceCollection AddGovernanceModule(this IServiceCollection services)
    {
        ArgumentNullException.ThrowIfNull(services);

        return services;
    }
}
