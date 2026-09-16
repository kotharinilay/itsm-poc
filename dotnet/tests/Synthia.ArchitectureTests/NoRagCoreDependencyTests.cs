using System.Reflection;

namespace Synthia.ArchitectureTests;

/// <summary>
/// The cross-deployable rule, asserted from inside the .NET stack (T033).
/// </summary>
/// <remarks>
/// <para>
/// RagCore and the monolith have <b>no application-level dependency in either direction</b> —
/// no API call, no library reference, no deployment coupling (ADR-0001). They meet at exactly
/// two places: PostgreSQL, through versioned views RagCore owns, and Service Bus, through
/// opaque triggers.
/// </para>
/// <para>
/// <c>build/scripts/check-boundaries.sh</c> checks the same rule over source text. This checks
/// it over compiled metadata. Both exist because they fail differently: the script catches a
/// string in a config file the compiler never sees, and this catches a reference that a
/// transitive package drags in.
/// </para>
/// </remarks>
public sealed class NoRagCoreDependencyTests
{
    private static readonly Assembly[] _platformAssemblies =
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

    [Fact]
    public void No_assembly_references_anything_named_ragcore()
    {
        List<string> violations = [];

        foreach (Assembly assembly in _platformAssemblies)
        {
            foreach (AssemblyName referenced in assembly.GetReferencedAssemblies())
            {
                if (referenced.Name?.Contains("ragcore", StringComparison.OrdinalIgnoreCase) == true)
                {
                    violations.Add($"{assembly.GetName().Name} -> {referenced.Name}");
                }
            }
        }

        Assert.True(
            violations.Count == 0,
            "A .NET assembly references RagCore. The two deployables meet only at PostgreSQL " +
            "and Service Bus:\n  " + string.Join("\n  ", violations));
    }

    [Fact]
    public void No_type_name_suggests_a_ragcore_client()
    {
        List<string> violations = [];

        foreach (Assembly assembly in _platformAssemblies)
        {
            foreach (Type type in assembly.GetTypes())
            {
                bool suspicious =
                    type.Name.Contains("RagCore", StringComparison.OrdinalIgnoreCase)
                    || type.Name.Contains("RagClient", StringComparison.OrdinalIgnoreCase);

                if (suspicious)
                {
                    violations.Add($"{assembly.GetName().Name}.{type.Name}");
                }
            }
        }

        Assert.True(violations.Count == 0, string.Join(", ", violations));
    }

    [Fact]
    public void The_monolith_defines_no_ef_migration_type()
    {
        // The monolith owns no schema (ADR-0001, ADR-0003). Alembic owns every migration, and
        // the monolith reads versioned views it does not own.
        List<string> violations = [];

        foreach (Assembly assembly in _platformAssemblies)
        {
            foreach (Type type in assembly.GetTypes())
            {
                bool isMigration = type.BaseType?.FullName is
                    "Microsoft.EntityFrameworkCore.Migrations.Migration"
                    or "Microsoft.EntityFrameworkCore.Infrastructure.ModelSnapshot";

                if (isMigration)
                {
                    violations.Add($"{assembly.GetName().Name}.{type.Name}");
                }
            }
        }

        Assert.True(
            violations.Count == 0,
            "The monolith defines an EF migration. It owns no schema:\n  " +
            string.Join("\n  ", violations));
    }
}
