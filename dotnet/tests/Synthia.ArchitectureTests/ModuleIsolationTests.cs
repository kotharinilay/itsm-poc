using System.Reflection;
using NetArchTest.Rules;

namespace Synthia.ArchitectureTests;

/// <summary>
/// Module boundaries (T032).
/// </summary>
/// <remarks>
/// <b>Boundaries are mandatory even when responsibilities deploy together</b>
/// (.claude/rules/10-principles.md P-24). Module boundaries inside the monolith are enforced by architecture tests, not
/// convention — this file is that enforcement.
/// <para>
/// The declaration-level checks read <c>.csproj</c> files via <see cref="ProjectGraph"/> rather
/// than reflecting over compiled metadata. See that type for why: a declared-but-unused reference
/// is invisible to reflection, and that is the state a breach passes through on its way in.
/// </para>
/// </remarks>
public sealed class ModuleIsolationTests
{
    private static readonly string[] _moduleNames =
    [
        "Synthia.Modules.Sessions",
        "Synthia.Modules.Work",
        "Synthia.Modules.Approvals",
        "Synthia.Modules.Governance",
        "Synthia.Modules.Audit",
        "Synthia.Modules.Tenancy",
    ];

    [Fact]
    public void No_module_declares_a_reference_to_another_module()
    {
        IReadOnlyDictionary<string, FileInfo> projects = ProjectGraph.AllProjects();
        List<string> violations = [];

        foreach (string module in _moduleNames)
        {
            Assert.True(projects.ContainsKey(module), $"Module project {module} not found.");

            foreach (string referenced in ProjectGraph.DeclaredReferences(projects[module]))
            {
                if (_moduleNames.Contains(referenced, StringComparer.Ordinal))
                {
                    violations.Add($"{module} -> {referenced}");
                }
            }
        }

        Assert.True(
            violations.Count == 0,
            "A module declares a reference to another module. Modules meet through " +
            "Synthia.Contracts, never directly:\n  " + string.Join("\n  ", violations));
    }

    [Fact]
    public void Every_module_project_exists_and_references_only_contracts_and_persistence()
    {
        // The positive form of the rule. Stating what a module MAY reference catches a new
        // dependency that the negative rule above would not — a module reaching into
        // Synthia.Api, for instance, which is not a module but is still an inversion.
        string[] permitted =
        [
            "Synthia.Contracts",
            "Synthia.Persistence",
            "Synthia.SharedKernel",
        ];

        IReadOnlyDictionary<string, FileInfo> projects = ProjectGraph.AllProjects();
        List<string> violations = [];

        foreach (string module in _moduleNames)
        {
            foreach (string referenced in ProjectGraph.DeclaredReferences(projects[module]))
            {
                if (!permitted.Contains(referenced, StringComparer.Ordinal))
                {
                    violations.Add($"{module} -> {referenced}");
                }
            }
        }

        Assert.True(
            violations.Count == 0,
            "A module references something outside {Contracts, Persistence, SharedKernel}:\n  " +
            string.Join("\n  ", violations));
    }

    [Fact]
    public void No_module_uses_a_type_from_another_module()
    {
        // The compiled-metadata check, kept as a second layer. It catches an actually-used
        // reference that reached the assembly by some route other than a ProjectReference —
        // a transitive package, say. It does NOT catch a declared-but-unused reference, which is
        // what the .csproj check above is for. Neither test makes the other redundant.
        Assembly[] moduleAssemblies =
        [
            typeof(Modules.Sessions.AssemblyMarker).Assembly,
            typeof(Modules.Work.AssemblyMarker).Assembly,
            typeof(Modules.Approvals.AssemblyMarker).Assembly,
            typeof(Modules.Governance.AssemblyMarker).Assembly,
            typeof(Modules.Audit.AssemblyMarker).Assembly,
            typeof(Modules.Tenancy.AssemblyMarker).Assembly,
        ];

        List<string> violations = [];

        foreach (Assembly module in moduleAssemblies)
        {
            string[] otherModules = moduleAssemblies
                .Where(other => other != module)
                .Select(other => other.GetName().Name!)
                .ToArray();

            foreach (AssemblyName referenced in module.GetReferencedAssemblies())
            {
                if (otherModules.Contains(referenced.Name, StringComparer.Ordinal))
                {
                    violations.Add($"{module.GetName().Name} -> {referenced.Name}");
                }
            }
        }

        Assert.True(violations.Count == 0, string.Join("\n  ", violations));
    }

    [Fact]
    public void Shared_kernel_is_the_dependency_floor()
    {
        // If SharedKernel grows a reference to Contracts or Persistence the direction has
        // inverted, and every other rule here becomes unenforceable.
        IReadOnlyDictionary<string, FileInfo> projects = ProjectGraph.AllProjects();

        IReadOnlyList<string> references = ProjectGraph.DeclaredReferences(projects["Synthia.SharedKernel"]);

        Assert.True(
            references.Count == 0,
            "Synthia.SharedKernel must reference nothing. It references: " +
            string.Join(", ", references));
    }

    [Fact]
    public void The_composition_root_does_not_reach_past_modules_into_persistence()
    {
        // A direct reference is how a "quick query" ends up in an endpoint, bypassing the module
        // that owns the data and the tenant filter that goes with it.
        IReadOnlyDictionary<string, FileInfo> projects = ProjectGraph.AllProjects();

        IReadOnlyList<string> apiReferences = ProjectGraph.DeclaredReferences(projects["Synthia.Api"]);

        Assert.DoesNotContain("Synthia.Persistence", apiReferences, StringComparer.Ordinal);
    }

    [Fact]
    public void Contracts_carries_no_open_implementation_type()
    {
        // Synthia.Contracts holds cross-module abstractions and DTOs. A service implementation
        // there would be a shared mutable dependency between modules that are supposed to be
        // isolated — the exact coupling the project split exists to prevent.
        TestResult result = Types.InAssembly(typeof(Contracts.AssemblyMarker).Assembly)
            .That()
            .AreClasses()
            .And()
            .AreNotAbstract()
            .And()
            .DoNotHaveNameEndingWith("Marker")
            .Should()
            .BeSealed()
            .GetResult();

        Assert.True(
            result.IsSuccessful,
            "Contracts holds an unsealed implementation type:\n  " +
            string.Join("\n  ", result.FailingTypeNames ?? []));
    }
}
