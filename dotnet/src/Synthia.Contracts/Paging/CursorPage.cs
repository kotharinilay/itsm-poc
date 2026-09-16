namespace Synthia.Contracts.Paging;

/// <summary>
/// An opaque pagination cursor.
/// </summary>
/// <remarks>
/// <b>Opaque means a client may infer nothing from it</b> — not position, not total, not the key it
/// encodes. Keyset pagination is the default for large or growing collections; offset paging is
/// used only where explicitly justified.
/// </remarks>
/// <param name="Value">The encoded cursor.</param>
public readonly record struct Cursor(string Value)
{
    /// <summary>Renders the cursor.</summary>
    /// <returns>The encoded value.</returns>
    public override string ToString() => Value;
}

/// <summary>A request for one page of a collection.</summary>
/// <param name="Limit">Maximum items to return.</param>
/// <param name="Cursor">Where to resume, or <see langword="null"/> for the first page.</param>
public sealed record PageRequest(int Limit, Cursor? Cursor)
{
    /// <summary>The page size applied when a client supplies none.</summary>
    public const int DefaultLimit = 50;

    /// <summary>The largest page a client may request.</summary>
    public const int MaximumLimit = 200;

    /// <summary>The first page, at the default size.</summary>
    public static PageRequest First { get; } = new(DefaultLimit, null);

    /// <summary>
    /// Clamps a caller-supplied limit into the permitted range.
    /// </summary>
    /// <remarks>
    /// Clamped rather than rejected: an oversized limit is a client being optimistic, not an
    /// attack, and failing the request would teach nothing. An unknown <i>field</i> is a different
    /// matter and is a 400 — see <see cref="Querying.SortSpec"/>.
    /// </remarks>
    /// <param name="requested">The requested limit.</param>
    /// <returns>A limit within range.</returns>
    public static int ClampLimit(int? requested) =>
        requested is null or < 1 ? DefaultLimit : Math.Min(requested.Value, MaximumLimit);
}

/// <summary>One page of results, plus where to resume.</summary>
/// <typeparam name="T">The item type.</typeparam>
/// <param name="Items">The items in this page.</param>
/// <param name="NextCursor">
/// Where to resume, or <see langword="null"/> when the collection is exhausted.
/// </param>
public sealed record CursorPage<T>(IReadOnlyList<T> Items, Cursor? NextCursor)
{
    /// <summary>Whether another page may exist.</summary>
    public bool HasMore => NextCursor is not null;
}

/// <summary>Factory helpers for <see cref="CursorPage{T}"/>.</summary>
/// <remarks>
/// Separate from the generic type because CA1000 rules out static members there — a static on a
/// generic must be written <c>CursorPage&lt;Thing&gt;.Empty</c>, which reads as though the empty
/// page differs per element type.
/// </remarks>
public static class CursorPage
{
    /// <summary>An empty page of the given element type.</summary>
    /// <typeparam name="T">The item type.</typeparam>
    /// <returns>A page with no items and no continuation.</returns>
    public static CursorPage<T> Empty<T>() => new(Array.Empty<T>(), null);
}
