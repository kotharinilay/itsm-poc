namespace Synthia.ArchitectureTests;

/// <summary>
/// Where dynamic service resolution is permitted, and where it is not.
/// </summary>
/// <remarks>
/// <para>
/// <b>Service Locator is prohibited</b>, and <c>IServiceProvider</c> MUST NOT be injected into a
/// <i>business service</i> for dynamic resolution (.claude/rules/20-dotnet.md BL-2). A type that
/// holds a provider has hidden its dependencies from its constructor, which is where they are
/// supposed to be visible.
/// </para>
/// <para>
/// <c>HttpContext.RequestServices</c> is a narrower thing and the rule does not reach it: it is the
/// framework's own per-request accessor, and ASP.NET Core fixes the signatures of middleware and
/// endpoint filters so that a singleton filter has no other way to reach a scoped service. What
/// matters is that the exception stays confined to that layer — a read model resolving its own
/// dependencies would be the real Service Locator, wearing the framework's clothes.
/// </para>
/// </remarks>
public sealed class ServiceResolutionTests
{
    [Fact]
    public void Dynamic_resolution_happens_only_in_the_request_pipeline()
    {
        // Confined to the composition root's own pipeline types. A module or read model appearing
        // here would be a business service resolving its own dependencies.
        string[] permitted = ["RoleFilter.cs"];

        IReadOnlyList<string> users = SourceTree.ProductionFilesContaining("RequestServices");

        string[] unexpected = users
            .Where(file => !permitted.Contains(file, StringComparer.Ordinal))
            .ToArray();

        Assert.True(
            unexpected.Length == 0,
            "Dynamic service resolution appears outside the request pipeline. Constructor-inject " +
            "the dependency instead:\n  " + string.Join("\n  ", unexpected));
    }

    [Fact]
    public void No_module_or_read_model_resolves_its_own_dependencies()
    {
        // The positive statement of the same rule, scoped to where it matters most. Everything a
        // read model needs arrives through its constructor, which is what makes it testable without
        // a container and reviewable without tracing a provider call.
        string[] tells = ["GetRequiredService", "GetService(", "IServiceProvider"];

        List<string> offending = [];

        foreach (FileInfo file in SourceTree.ProductionFiles())
        {
            bool isModule = file.FullName.Contains(
                $"{Path.DirectorySeparatorChar}Modules{Path.DirectorySeparatorChar}",
                StringComparison.Ordinal);

            if (!isModule)
            {
                continue;
            }

            string code = SourceTree.CodeOf(file);

            foreach (string tell in tells)
            {
                // A module's registration extension legitimately resolves during composition — that
                // IS composition-root code, invoked by the root. Everything else in a module is not.
                if (code.Contains(tell, StringComparison.Ordinal) &&
                    !file.Name.EndsWith("ModuleRegistration.cs", StringComparison.Ordinal))
                {
                    offending.Add($"{file.Name} -> {tell}");
                }
            }
        }

        Assert.True(offending.Count == 0, string.Join("\n  ", offending));
    }
}
