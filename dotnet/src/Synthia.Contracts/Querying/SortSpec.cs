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
/// The whitelist of sortable and filterable fields for one resource.
/// </summary>
/// <remarks>
/// <para>
/// Sorting is over a whitelisted field set, and filtering is allow-listed — an unknown field is a
/// 400, never silently ignored. Silently ignoring it is worse than failing: the client believes it
/// filtered and receives rows it did not ask for.
/// </para>
/// <para>
/// The per-resource sets are enumerated in <c>specs/001-platform-scaffold/contracts/README.md</c>.
/// This type is how an endpoint holds one.
/// </para>
/// </remarks>
public sealed class QueryWhitelist
{
    private readonly FrozenSet<string> _sortable;
    private readonly FrozenSet<string> _filterable;

    /// <summary>Creates a whitelist for one resource.</summary>
    /// <param name="sortable">Fields this resource may be sorted by.</param>
    /// <param name="filterable">Fields this resource may be filtered by.</param>
    /// <param name="defaultSort">
    /// The sort applied when a client supplies none, so keyset pagination always has a
    /// deterministic order.
    /// </param>
    public QueryWhitelist(
        IEnumerable<string> sortable,
        IEnumerable<string> filterable,
        SortSpec defaultSort)
    {
        ArgumentNullException.ThrowIfNull(sortable);
        ArgumentNullException.ThrowIfNull(filterable);

        _sortable = sortable.ToFrozenSet(StringComparer.Ordinal);
        _filterable = filterable.ToFrozenSet(StringComparer.Ordinal);
        DefaultSort = defaultSort;
    }

    /// <summary>The sort applied when a client supplies none.</summary>
    public SortSpec DefaultSort { get; }

    /// <summary>Fields this resource may be sorted by.</summary>
    public IReadOnlyCollection<string> SortableFields => _sortable;

    /// <summary>Fields this resource may be filtered by.</summary>
    public IReadOnlyCollection<string> FilterableFields => _filterable;

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
