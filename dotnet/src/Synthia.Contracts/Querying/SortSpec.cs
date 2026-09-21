using System.Collections.Frozen;

namespace Synthia.Contracts.Querying;

/// <summary>Sort direction.</summary>
public enum SortDirection
{
    /// <summary>Ascending.</summary>
    Ascending = 0,

    /// <summary>Descending, requested as <c>?sort=-field</c>.</summary>
    Descending = 1,
}

/// <summary>A validated sort instruction.</summary>
/// <param name="Field">A field from the resource's whitelist.</param>
/// <param name="Direction">The direction requested.</param>
public readonly record struct SortSpec(string Field, SortDirection Direction);

/// <summary>A validated filter instruction.</summary>
/// <remarks>
/// Filters are <b>typed</b>. Arbitrary OData or expression-language filtering MUST NOT be exposed:
/// an expression language over a read model is an unbounded query surface, and unbounded query
/// surfaces are where tenant filters get evaded.
/// </remarks>
/// <param name="Field">A field from the resource's whitelist.</param>
/// <param name="Value">The value to match, already parsed to its precise type.</param>
public readonly record struct FilterSpec(string Field, object Value);

/// <summary>
/// What a filter value is, so the published contract and the binder agree on it.
/// </summary>
/// <remarks>
/// A closed set rather than a <see cref="Type"/>: these are the only shapes a filter value takes on
/// this platform, and an open type would invite one that has no wire representation.
/// </remarks>
public enum FilterKind
{
    /// <summary>A free-text match, published as a plain string.</summary>
    Text = 0,

    /// <summary>A GUID, published as <c>string</c> with <c>format: uuid</c>.</summary>
    Identifier = 1,

    /// <summary>An instant, published as <c>string</c> with <c>format: date-time</c>.</summary>
    Timestamp = 2,

    /// <summary>A member of a closed set, published with its <c>enum</c> values.</summary>
    Enumeration = 3,
}

/// <summary>
/// One filterable field, with the type a client may send.
/// </summary>
/// <remarks>
/// <para>
/// <b>The field is declared once and read twice</b> — by the binder that validates a request and by
/// the OpenAPI operation transformer that publishes the parameter. A document built from a separate
/// list would be a second description of the filter set with nothing keeping it true, which is the
/// failure the generated-contract rule exists to prevent.
/// </para>
/// <para>
/// <see cref="Values"/> is populated for <see cref="FilterKind.Enumeration"/> and empty otherwise.
/// It is read off the enum type, never restated.
/// </para>
/// </remarks>
public sealed class FilterField
{
    /// <summary>Declares a filter of a non-enumerated kind.</summary>
    /// <param name="name">The query-string field name, in camelCase.</param>
    /// <param name="kind">What the value is.</param>
    public FilterField(string name, FilterKind kind)
    {
        Name = name;
        Kind = kind;
        Values = [];
    }

    private FilterField(string name, IReadOnlyList<string> values)
    {
        Name = name;
        Kind = FilterKind.Enumeration;
        Values = values;
    }

    /// <summary>The query-string field name.</summary>
    public string Name { get; }

    /// <summary>What the value is.</summary>
    public FilterKind Kind { get; }

    /// <summary>The accepted values, for an enumerated filter. Empty otherwise.</summary>
    public IReadOnlyList<string> Values { get; }

    /// <summary>
    /// Declares a filter over a closed set, taking its values from the enum itself.
    /// </summary>
    /// <remarks>
    /// Names are lower-cased to match the camelCase JSON convention both deployables serialize
    /// with, so the published values are the ones a client actually sends.
    /// </remarks>
    /// <typeparam name="TEnum">The enum the binder parses into.</typeparam>
    /// <param name="name">The query-string field name.</param>
    /// <returns>The declaration.</returns>
    public static FilterField Over<TEnum>(string name)
        where TEnum : struct, Enum =>
        new(name, [.. Enum.GetNames<TEnum>().Select(value => value.ToLowerInvariant()).Order(StringComparer.Ordinal)]);
}

/// <summary>
/// The whitelist of sortable and filterable fields for one resource.
/// </summary>
/// <remarks>
/// <para>
/// Sorting is over a whitelisted field set, and filtering is allow-listed — an unknown field is a
/// 400, never silently ignored. Silently ignoring it is worse than failing: the client believes it
/// filtered and receives rows it did not ask for.
/// </para>
/// <para>
/// The per-resource sets are declared in each module's sort-key type and published in the
/// generated contracts under <c>build/contracts/</c>.
/// This type is how an endpoint holds one.
/// </para>
/// </remarks>
public sealed class QueryWhitelist
{
    private readonly FrozenSet<string> _sortable;
    private readonly FrozenSet<string> _filterable;

    /// <summary>Creates a whitelist for one resource.</summary>
    /// <param name="sortable">Fields this resource may be sorted by.</param>
    /// <param name="filterable">
    /// Fields this resource may be filtered by, each with the type a client may send. The type is
    /// here rather than at the endpoint so the binder and the published contract read one
    /// declaration.
    /// </param>
    /// <param name="defaultSort">
    /// The sort applied when a client supplies none, so keyset pagination always has a
    /// deterministic order.
    /// </param>
    public QueryWhitelist(
        IEnumerable<string> sortable,
        IEnumerable<FilterField> filterable,
        SortSpec defaultSort)
    {
        ArgumentNullException.ThrowIfNull(sortable);
        ArgumentNullException.ThrowIfNull(filterable);

        _sortable = sortable.ToFrozenSet(StringComparer.Ordinal);
        Filters = [.. filterable];
        _filterable = Filters.Select(filter => filter.Name).ToFrozenSet(StringComparer.Ordinal);
        DefaultSort = defaultSort;
    }

    /// <summary>The sort applied when a client supplies none.</summary>
    public SortSpec DefaultSort { get; }

    /// <summary>Fields this resource may be sorted by.</summary>
    public IReadOnlyCollection<string> SortableFields => _sortable;

    /// <summary>Fields this resource may be filtered by.</summary>
    public IReadOnlyCollection<string> FilterableFields => _filterable;

    /// <summary>The same fields, with the type a client may send. The publishing view.</summary>
    public IReadOnlyList<FilterField> Filters { get; }

    /// <summary>
    /// Parses a <c>?sort=</c> value against this whitelist.
    /// </summary>
    /// <param name="raw">The raw sort value, or <see langword="null"/> for the default.</param>
    /// <param name="sort">The resolved sort.</param>
    /// <returns><see langword="false"/> when the field is not whitelisted — the caller returns 400.</returns>
    public bool TryResolveSort(string? raw, out SortSpec sort)
    {
        if (string.IsNullOrWhiteSpace(raw))
        {
            sort = DefaultSort;
            return true;
        }

        bool descending = raw[0] == '-';
        string field = descending ? raw[1..] : raw;

        if (!_sortable.Contains(field))
        {
            sort = DefaultSort;
            return false;
        }

        sort = new SortSpec(field, descending ? SortDirection.Descending : SortDirection.Ascending);
        return true;
    }

    /// <summary>Whether a field may be filtered on.</summary>
    /// <param name="field">The candidate field.</param>
    /// <returns><see langword="true"/> when whitelisted.</returns>
    public bool AllowsFilterOn(string field) => _filterable.Contains(field);
}
