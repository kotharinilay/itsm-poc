using System.Reflection;
using NetArchTest.Rules;

namespace Synthia.ArchitectureTests;

/// <summary>
/// APIs the constitution prohibits outright (T034).
/// </summary>
/// <remarks>
/// Most of these are also analyzer-enforced at build time. They are asserted again here because
/// an analyzer can be suppressed at a call site with a pragma and a plausible reason, and a
/// test cannot be suppressed without deleting it — which is visible in a diff.
/// </remarks>
public sealed class BannedApiTests
{
    private static readonly Assembly[] _productionAssemblies =
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
    public void No_production_type_depends_on_DateTime_directly()
    {
        // DateTimeOffset throughout, from DateTimeOffset.UtcNow or an injected TimeProvider.
        // DateTime.Now is prohibited: it silently reads the machine's local zone, which in a
        // container is UTC in production and something else on the developer's laptop.
        foreach (Assembly assembly in _productionAssemblies)
        {
            TestResult result = Types.InAssembly(assembly)
                .That().DoNotHaveNameEndingWith("Marker")
                .ShouldNot().HaveDependencyOn("System.DateTime")
                .GetResult();

            Assert.True(
                result.IsSuccessful,
                $"{assembly.GetName().Name} depends on DateTime. Use DateTimeOffset or an " +
                "injected TimeProvider:\n  " +
                string.Join("\n  ", result.FailingTypeNames ?? []));
        }
    }

    [Fact]
    public void No_production_type_depends_on_Thread()
    {
        // Thread.Sleep in an async path blocks a pool thread. Covered by CA1849 at build time;
        // asserted here so a pragma cannot quietly re-enable it.
        foreach (Assembly assembly in _productionAssemblies)
        {
            TestResult result = Types.InAssembly(assembly)
                .That().DoNotHaveNameEndingWith("Marker")
                .ShouldNot().HaveDependencyOn("System.Threading.Thread")
                .GetResult();

            Assert.True(result.IsSuccessful, string.Join(", ", result.FailingTypeNames ?? []));
        }
    }

    [Fact]
    public void No_production_type_uses_a_service_locator()
    {
        // IServiceProvider MUST NOT be injected into a business service for dynamic
        // resolution. It is framework plumbing; a type that holds one has hidden its
        // dependencies from its constructor, which is where they are supposed to be visible.
        List<string> violations = [];

        foreach (Assembly assembly in _productionAssemblies)
        {
            if (assembly == typeof(Program).Assembly)
            {
                // The composition root legitimately touches the provider. It is the one place.
                continue;
            }

            foreach (Type type in assembly.GetTypes())
            {
                foreach (ConstructorInfo ctor in type.GetConstructors())
                {
                    if (ctor.GetParameters().Any(p => p.ParameterType == typeof(IServiceProvider)))
                    {
                        violations.Add($"{assembly.GetName().Name}.{type.Name}");
                    }
                }
            }
        }

        Assert.True(
            violations.Count == 0,
            "Service Locator detected. Constructor-inject the dependency instead:\n  " +
            string.Join("\n  ", violations));
    }

    [Fact]
    public void No_production_type_writes_to_the_console()
    {
        // Structured logging through Microsoft.Extensions.Logging. Console.WriteLine bypasses
        // the correlation scope and the redaction that keeps secrets out of log sinks.
        foreach (Assembly assembly in _productionAssemblies)
        {
            TestResult result = Types.InAssembly(assembly)
                .That().DoNotHaveNameEndingWith("Marker")
                .ShouldNot().HaveDependencyOn("System.Console")
                .GetResult();

            Assert.True(result.IsSuccessful, string.Join(", ", result.FailingTypeNames ?? []));
        }
    }
}
