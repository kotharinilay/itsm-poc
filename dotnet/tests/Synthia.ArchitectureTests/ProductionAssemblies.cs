using System.Reflection;

namespace Synthia.ArchitectureTests;

/// <summary>
/// The assemblies that ship.
/// </summary>
/// <remarks>
/// Resolved by type reference rather than by name string, so a project rename cannot silently
/// disable a rule that guards it — the same reasoning as <c>AssemblyMarker</c>.
/// </remarks>
internal static class ProductionAssemblies
{
    /// <summary>Every production assembly in this deployable.</summary>
    public static IReadOnlyList<Assembly> All { get; } =
    [
        typeof(Program).Assembly,
        typeof(SharedKernel.AssemblyMarker).Assembly,
        typeof(Contracts.AssemblyMarker).Assembly,
        typeof(Persistence.AssemblyMarker).Assembly,
        typeof(Observability.AssemblyMarker).Assembly,
        typeof(Modules.Sessions.AssemblyMarker).Assembly,
        typeof(Modules.Work.AssemblyMarker).Assembly,
        typeof(Modules.Approvals.AssemblyMarker).Assembly,
        typeof(Modules.Governance.AssemblyMarker).Assembly,
        typeof(Modules.Audit.AssemblyMarker).Assembly,
        typeof(Modules.Tenancy.AssemblyMarker).Assembly,
    ];
}
