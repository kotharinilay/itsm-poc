using System.Reflection;

namespace Synthia.ArchitectureTests;

/// <summary>
/// The composition root is the only place registration happens (T035).
/// </summary>
/// <remarks>
/// Constructor injection only, via <c>Microsoft.Extensions.DependencyInjection</c>.
/// <c>BuildServiceProvider</c> MUST NEVER be called during application configuration — doing so
/// builds a second container whose singletons are not the ones the application will use, and
/// the resulting bug looks like a lifetime mystery rather than a wiring mistake.
/// </remarks>
public sealed class CompositionRootTests
{
    [Fact]
    public void Only_the_api_assembly_is_a_composition_root()
    {
        // A module registers its own services through its registration extension, invoked BY
        // the root. It never composes another module.
        Assembly[] nonRootAssemblies =
        [
            typeof(SharedKernel.AssemblyMarker).Assembly,
            typeof(Contracts.AssemblyMarker).Assembly,
            typeof(Persistence.AssemblyMarker).Assembly,
        ];

        foreach (Assembly assembly in nonRootAssemblies)
        {
            IEnumerable<string?> referenced = assembly.GetReferencedAssemblies().Select(a => a.Name);

            Assert.DoesNotContain(
                "Microsoft.Extensions.DependencyInjection",
                referenced,
                StringComparer.Ordinal);
        }
    }

    [Fact]
    public void Every_module_exposes_exactly_one_registration_extension()
    {
        (string Name, Assembly Assembly)[] modules =
        [
            ("Sessions", typeof(Modules.Sessions.AssemblyMarker).Assembly),
            ("Work", typeof(Modules.Work.AssemblyMarker).Assembly),
            ("Approvals", typeof(Modules.Approvals.AssemblyMarker).Assembly),
            ("Governance", typeof(Modules.Governance.AssemblyMarker).Assembly),
            ("Audit", typeof(Modules.Audit.AssemblyMarker).Assembly),
            ("Tenancy", typeof(Modules.Tenancy.AssemblyMarker).Assembly),
        ];

        foreach ((string name, Assembly assembly) in modules)
        {
            Type? registration = assembly.GetTypes()
                .SingleOrDefault(t => t.Name == $"{name}ModuleRegistration");

            Assert.True(
                registration is not null,
                $"Module {name} has no {name}ModuleRegistration. The composition root needs " +
                "exactly one entry point per module.");

            MethodInfo[] adders = registration!
                .GetMethods(BindingFlags.Public | BindingFlags.Static)
                .Where(m => m.Name == $"Add{name}Module")
                .ToArray();

            Assert.True(
                adders.Length == 1,
                $"Module {name} exposes {adders.Length} registration methods; expected exactly 1.");
        }
    }

    [Fact]
    public void No_type_outside_the_root_calls_BuildServiceProvider()
    {
        // Detected by name across every production assembly. The root itself does not call it
        // either — WebApplicationBuilder.Build() is the sanctioned path.
        Assembly[] assemblies =
        [
            typeof(Program).Assembly,
            typeof(SharedKernel.AssemblyMarker).Assembly,
            typeof(Contracts.AssemblyMarker).Assembly,
            typeof(Persistence.AssemblyMarker).Assembly,
            typeof(Observability.AssemblyMarker).Assembly,
        ];

        List<string> violations = [];

        foreach (Assembly assembly in assemblies)
        {
            foreach (Type type in assembly.GetTypes())
            {
                MethodInfo[] methods = type.GetMethods(
                    BindingFlags.Public | BindingFlags.NonPublic |
                    BindingFlags.Static | BindingFlags.Instance | BindingFlags.DeclaredOnly);

                if (methods.Any(m => m.Name.Contains("BuildServiceProvider", StringComparison.Ordinal)))
                {
                    violations.Add($"{assembly.GetName().Name}.{type.Name}");
                }
            }
        }

        Assert.True(violations.Count == 0, string.Join(", ", violations));
    }
}
