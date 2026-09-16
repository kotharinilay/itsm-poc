using System.Xml.Linq;

namespace Synthia.ArchitectureTests;

/// <summary>
/// The declared project-reference graph, read from the <c>.csproj</c> files themselves.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why not reflection.</b> <see cref="System.Reflection.Assembly.GetReferencedAssemblies"/>
/// reports the references the compiler actually <i>emitted</i>, and the C# compiler omits a
/// reference whose types are never used. A module that declares a <c>ProjectReference</c> on
/// another module but has not used it yet is therefore <b>invisible</b> to a reflection-based
/// check — which is precisely the state a boundary breach passes through on its way in: the
/// reference is added first, the coupling follows.
/// </para>
/// <para>
/// This was found by planting exactly that violation and watching a reflection-based test pass it.
/// Reading the project files catches the declaration at the moment it is added.
/// </para>
/// </remarks>
internal static class ProjectGraph
{
    /// <summary>Locates the repository's <c>dotnet/</c> directory from the test binary's location.</summary>
    /// <returns>The directory containing <c>Synthia.sln</c>.</returns>
    public static DirectoryInfo SolutionDirectory()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);

        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Synthia.sln")))
        {
            directory = directory.Parent;
        }

        Assert.True(
            directory is not null,
            "Could not locate Synthia.sln above the test binary. The project-graph tests read the " +
            ".csproj files directly and need the source tree.");

        return directory!;
    }

    /// <summary>Every project file in the solution, keyed by project name.</summary>
    /// <returns>A map of project name to project file.</returns>
    public static IReadOnlyDictionary<string, FileInfo> AllProjects()
    {
        DirectoryInfo root = SolutionDirectory();

        return root.GetFiles("*.csproj", SearchOption.AllDirectories)
            .Where(f => !f.FullName.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}", StringComparison.Ordinal))
            .Where(f => !f.FullName.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}", StringComparison.Ordinal))
            .ToDictionary(f => Path.GetFileNameWithoutExtension(f.Name), f => f, StringComparer.Ordinal);
    }

    /// <summary>The project names a project declares a reference to.</summary>
    /// <param name="project">The project file to read.</param>
    /// <returns>Referenced project names, in declaration order.</returns>
    public static IReadOnlyList<string> DeclaredReferences(FileInfo project)
    {
        ArgumentNullException.ThrowIfNull(project);

        XDocument document = XDocument.Load(project.FullName);

        return document
            .Descendants("ProjectReference")
            .Select(element => element.Attribute("Include")?.Value)
            .Where(include => !string.IsNullOrWhiteSpace(include))
            .Select(include => Path.GetFileNameWithoutExtension(include!.Replace('\\', '/')))
            .ToList();
    }
}
