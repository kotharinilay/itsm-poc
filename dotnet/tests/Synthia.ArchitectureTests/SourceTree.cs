using System.Text;

namespace Synthia.ArchitectureTests;

/// <summary>
/// The .NET source files, read as code rather than as prose.
/// </summary>
/// <remarks>
/// <para>
/// <b>Some rules are about source, not about compiled metadata.</b> "This API is called in exactly
/// one place" and "this string appears nowhere" are properties of what somebody wrote — a call site
/// that was deleted leaves no trace in IL, and a call site that was added looks identical to every
/// other call of the same method.
/// </para>
/// <para>
/// <b>Comments are stripped before matching, and that is not a detail.</b> Written naively, a rule
/// banning <c>Database.Migrate()</c> fires on the comment explaining why <c>Database.Migrate()</c>
/// is banned — so the only way to pass is to stop writing the explanation down. A guard that
/// punishes documentation gets the documentation deleted, and then nobody remembers what the guard
/// was for.
/// </para>
/// <para>
/// String literals are <b>kept</b>, because a literal is code: a header name in quotes is exactly
/// what several of these rules are looking for.
/// </para>
/// </remarks>
internal static class SourceTree
{
    /// <summary>Every production C# file, excluding tests and build output.</summary>
    /// <returns>The files.</returns>
    public static IReadOnlyList<FileInfo> ProductionFiles()
    {
        DirectoryInfo root = new(Path.Combine(ProjectGraph.SolutionDirectory().FullName, "src"));

        return root.GetFiles("*.cs", SearchOption.AllDirectories)
            .Where(file => !IsBuildOutput(file))
            .ToList();
    }

    /// <summary>
    /// Finds production files whose <b>code</b> contains a term.
    /// </summary>
    /// <param name="term">The term to look for.</param>
    /// <returns>Matching file names, short enough to read in a failure message.</returns>
    public static IReadOnlyList<string> ProductionFilesContaining(string term)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(term);

        return ProductionFiles()
            .Where(file => CodeOf(file).Contains(term, StringComparison.Ordinal))
            .Select(file => file.Name)
            .Order(StringComparer.Ordinal)
            .ToList();
    }

    /// <summary>
    /// Reads a file with its comments removed and its string literals intact.
    /// </summary>
    /// <remarks>
    /// Handles line comments, block comments, ordinary and verbatim string literals, and character
    /// literals. It does not handle raw string literals (<c>"""</c>); none is used in this tree, and
    /// <c>No_source_file_uses_a_raw_string_literal</c> keeps it that way so this stays true.
    /// </remarks>
    /// <param name="file">The file to read.</param>
    /// <returns>The code.</returns>
    public static string CodeOf(FileInfo file)
    {
        ArgumentNullException.ThrowIfNull(file);

        string text = File.ReadAllText(file.FullName);
        StringBuilder code = new(text.Length);

        for (int index = 0; index < text.Length; index++)
        {
            char current = text[index];
            char next = index + 1 < text.Length ? text[index + 1] : '\0';

            if (current == '/' && next == '/')
            {
                while (index < text.Length && text[index] != '\n')
                {
                    index++;
                }

                code.Append('\n');
                continue;
            }

            if (current == '/' && next == '*')
            {
                index += 2;

                while (index + 1 < text.Length && !(text[index] == '*' && text[index + 1] == '/'))
                {
                    index++;
                }

                index++;
                continue;
            }

            if (current == '@' && next == '"')
            {
                index = CopyVerbatimString(text, index, code);
                continue;
            }

            if (current == '"' || current == '\'')
            {
                index = CopyQuoted(text, index, current, code);
                continue;
            }

            code.Append(current);
        }

        return code.ToString();
    }

    private static int CopyVerbatimString(string text, int index, StringBuilder code)
    {
        code.Append(text[index]).Append(text[index + 1]);
        index += 2;

        while (index < text.Length)
        {
            if (text[index] == '"')
            {
                // "" inside a verbatim string is an escaped quote, not the end of it.
                if (index + 1 < text.Length && text[index + 1] == '"')
                {
                    code.Append('"').Append('"');
                    index += 2;
                    continue;
                }

                code.Append('"');
                return index;
            }

            code.Append(text[index]);
            index++;
        }

        return index;
    }

    private static int CopyQuoted(string text, int index, char quote, StringBuilder code)
    {
        code.Append(quote);
        index++;

        while (index < text.Length)
        {
            if (text[index] == '\\' && index + 1 < text.Length)
            {
                code.Append(text[index]).Append(text[index + 1]);
                index += 2;
                continue;
            }

            code.Append(text[index]);

            if (text[index] == quote)
            {
                return index;
            }

            index++;
        }

        return index;
    }

    private static bool IsBuildOutput(FileInfo file) =>
        file.FullName.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}", StringComparison.Ordinal) ||
        file.FullName.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}", StringComparison.Ordinal);
}
