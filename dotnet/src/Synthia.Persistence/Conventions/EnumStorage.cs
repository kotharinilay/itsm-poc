using System.Collections.Frozen;
using System.Globalization;
using Microsoft.EntityFrameworkCore.Storage.ValueConversion;

namespace Synthia.Persistence.Conventions;

/// <summary>
/// Translates between a CLR enum member and the spelling PostgreSQL holds.
/// </summary>
/// <remarks>
/// <para>
/// The database enums are owned by RagCore's migrations and spelled the way PostgreSQL and Python
/// spell things: <c>awaiting_user</c>, <c>desktop_script</c>. The CLR spelling is PascalCase. This
/// is the one place that difference is resolved.
/// </para>
/// <para>
/// <b>An unrecognised value throws rather than defaulting.</b> RagCore adding an enum member the
/// monolith has not been told about is a published-view contract change, and the correct response
/// is a loud failure at the read, not a row silently reported as <c>Unknown</c>.
/// </para>
/// </remarks>
internal static class EnumStorage
{
    /// <summary>Renders a CLR enum member in <c>lower_snake_case</c>.</summary>
    /// <typeparam name="TEnum">The enum type.</typeparam>
    /// <param name="member">The member to render.</param>
    /// <returns>The stored spelling.</returns>
    public static string ToLowerSnakeCase<TEnum>(TEnum member)
        where TEnum : struct, Enum =>
        SnakeCaseNaming.ToSnakeCase(member.ToString() ?? string.Empty);

    /// <summary>Renders a CLR enum member in <c>UPPER_SNAKE_CASE</c>.</summary>
    /// <typeparam name="TEnum">The enum type.</typeparam>
    /// <param name="member">The member to render.</param>
    /// <returns>The stored spelling.</returns>
    public static string ToUpperSnakeCase<TEnum>(TEnum member)
        where TEnum : struct, Enum =>
        SnakeCaseNaming.ToSnakeCase(member.ToString() ?? string.Empty).ToUpperInvariant();

    /// <summary>Builds a lookup from stored spelling back to the CLR member.</summary>
    /// <typeparam name="TEnum">The enum type.</typeparam>
    /// <param name="render">How members of this enum are spelled in storage.</param>
    /// <returns>A frozen lookup, excluding the <c>Unknown</c> sentinel.</returns>
    public static FrozenDictionary<string, TEnum> BuildLookup<TEnum>(Func<TEnum, string> render)
        where TEnum : struct, Enum
    {
        ArgumentNullException.ThrowIfNull(render);

        return Enum.GetValues<TEnum>()
            .Where(member => !string.Equals(member.ToString(), "Unknown", StringComparison.Ordinal))
            .ToFrozenDictionary(render, member => member, StringComparer.Ordinal);
    }

    /// <summary>Reports a stored value the monolith has no member for.</summary>
    /// <param name="stored">The value the view returned.</param>
    /// <param name="enumType">The enum it was being read into.</param>
    /// <returns>Never returns; always throws.</returns>
    /// <exception cref="InvalidOperationException">Always.</exception>
    public static InvalidOperationException UnknownValue(string stored, Type enumType)
    {
        ArgumentNullException.ThrowIfNull(enumType);

        return new InvalidOperationException(
            string.Format(
                CultureInfo.InvariantCulture,
                "The published view returned '{0}', which is not a known {1}. RagCore has added an " +
                "enum member without publishing a new view version — see contracts/read-views.md.",
                stored,
                enumType.Name));
    }
}

/// <summary>Stores an enum as the <c>lower_snake_case</c> text PostgreSQL holds.</summary>
/// <typeparam name="TEnum">The enum type.</typeparam>
internal sealed class LowerSnakeCaseEnumConverter<TEnum> : ValueConverter<TEnum, string>
    where TEnum : struct, Enum
{
    private static readonly FrozenDictionary<string, TEnum> _lookup =
        EnumStorage.BuildLookup<TEnum>(EnumStorage.ToLowerSnakeCase);

    /// <summary>Creates the converter.</summary>
    public LowerSnakeCaseEnumConverter()
        : base(member => EnumStorage.ToLowerSnakeCase(member), stored => Parse(stored))
    {
    }

    private static TEnum Parse(string stored) =>
        _lookup.TryGetValue(stored, out TEnum member)
            ? member
            : throw EnumStorage.UnknownValue(stored, typeof(TEnum));
}

/// <summary>Stores an enum as the <c>UPPER_SNAKE_CASE</c> text PostgreSQL holds.</summary>
/// <remarks>
/// Execution treatments are spelled <c>AUTO</c>, <c>END_USER_APPROVAL</c>, <c>STAFF_APPROVAL</c>
/// and <c>NOT_ALLOWED</c> in data-model.md, unlike every other enum in the schema.
/// </remarks>
/// <typeparam name="TEnum">The enum type.</typeparam>
internal sealed class UpperSnakeCaseEnumConverter<TEnum> : ValueConverter<TEnum, string>
    where TEnum : struct, Enum
{
    private static readonly FrozenDictionary<string, TEnum> _lookup =
        EnumStorage.BuildLookup<TEnum>(EnumStorage.ToUpperSnakeCase);

    /// <summary>Creates the converter.</summary>
    public UpperSnakeCaseEnumConverter()
        : base(member => EnumStorage.ToUpperSnakeCase(member), stored => Parse(stored))
    {
    }

    private static TEnum Parse(string stored) =>
        _lookup.TryGetValue(stored, out TEnum member)
            ? member
            : throw EnumStorage.UnknownValue(stored, typeof(TEnum));
}
