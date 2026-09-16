using System.Text.Json;
using System.Text.Json.Serialization;

namespace Synthia.Api.Errors;

/// <summary>
/// The JSON shape both deployables emit.
/// </summary>
/// <remarks>
/// <b>camelCase in both directions, on both deployables</b> (contracts §README). Enum members are
/// written as their names rather than their numbers, because a number in a payload is a value
/// nobody can read in a log or a bug report — and renumbering an enum would silently change the
/// wire contract.
/// </remarks>
internal static class JsonConventions
{
    /// <summary>The serializer options every response is written with.</summary>
    public static JsonSerializerOptions Options { get; } = Build();

    /// <summary>Applies the conventions to a serializer options instance.</summary>
    /// <param name="options">The options to configure.</param>
    public static void Apply(JsonSerializerOptions options)
    {
        ArgumentNullException.ThrowIfNull(options);

        options.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
        options.DictionaryKeyPolicy = JsonNamingPolicy.CamelCase;
        options.PropertyNameCaseInsensitive = false;
        options.DefaultIgnoreCondition = JsonIgnoreCondition.Never;
        options.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));
    }

    private static JsonSerializerOptions Build()
    {
        JsonSerializerOptions options = new(JsonSerializerDefaults.Web);
        Apply(options);
        options.MakeReadOnly();

        return options;
    }
}
