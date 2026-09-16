using System.Text;

namespace Synthia.Persistence.Conventions;

/// <summary>
/// The one place PascalCase CLR names become the <c>snake_case</c> names PostgreSQL holds.
/// </summary>
/// <remarks>
/// Applied as a model-building convention rather than written out per property. Two hundred
/// hand-written <c>HasColumnName</c> calls are two hundred chances to typo a column into a runtime
/// error that only the query touching it will find.
/// </remarks>
internal static class SnakeCaseNaming
{
    /// <summary>Renders a PascalCase identifier as <c>snake_case</c>.</summary>
    /// <param name="pascalCase">The CLR name.</param>
    /// <returns>The database spelling.</returns>
    public static string ToSnakeCase(string pascalCase)
    {
        ArgumentNullException.ThrowIfNull(pascalCase);

        StringBuilder builder = new(pascalCase.Length + 4);

        for (int index = 0; index < pascalCase.Length; index++)
        {
            char character = pascalCase[index];

            if (index > 0 && char.IsUpper(character))
            {
                builder.Append('_');
            }

            builder.Append(char.ToLowerInvariant(character));
        }

        return builder.ToString();
    }
}
