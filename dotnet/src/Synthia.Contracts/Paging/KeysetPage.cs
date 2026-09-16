namespace Synthia.Contracts.Paging;

/// <summary>
/// Where a keyset scan resumes: the sort key of the last row returned, plus its identifier.
/// </summary>
/// <remarks>
/// <para>
/// The identifier is the tie-breaker. Without it a page boundary that falls inside a run of equal
/// sort values either repeats rows or skips them, and <c>-createdAt</c> on rows written in the same
/// millisecond is exactly that case.
/// </para>
/// <para>
/// <b>This type is never seen by a client.</b> Cursors are opaque, and the API boundary is where a
/// position becomes an opaque string. A read model deals in positions; only the edge encodes them.
/// </para>
/// </remarks>
/// <param name="SortValue">The last row's sort key, rendered round-trippably.</param>
/// <param name="Id">The last row's identifier, breaking ties on equal sort values.</param>
public readonly record struct KeysetPosition(string SortValue, Guid Id);

/// <summary>One page of a keyset scan, plus where it resumes.</summary>
/// <typeparam name="T">The item type.</typeparam>
/// <param name="Items">The items in this page.</param>
/// <param name="Next">
/// Where to resume, or <see langword="null"/> when the collection is exhausted.
/// </param>
public sealed record KeysetPage<T>(IReadOnlyList<T> Items, KeysetPosition? Next);

/// <summary>Factory helpers for <see cref="KeysetPage{T}"/>.</summary>
/// <remarks>
/// Separate from the generic type for the same reason as <see cref="CursorPage"/>: CA1000 rules out
/// statics on a generic, and <c>KeysetPage&lt;Thing&gt;.Empty</c> reads as though emptiness differed
/// per element type.
/// </remarks>
public static class KeysetPage
{
    /// <summary>An exhausted page of the given element type.</summary>
    /// <typeparam name="T">The item type.</typeparam>
    /// <returns>A page with no items and no continuation.</returns>
    public static KeysetPage<T> Empty<T>() => new(Array.Empty<T>(), null);

    /// <summary>
    /// Assembles a page from items and the primitives a data layer reports its continuation as.
    /// </summary>
    /// <remarks>
    /// Takes primitives rather than a position type so a read model can hand back a continuation
    /// without the two layers sharing a type. Persistence sits below contracts in the dependency
    /// graph and cannot name <see cref="KeysetPosition"/>; this is the seam where its equivalent
    /// becomes one.
    /// </remarks>
    /// <typeparam name="T">The item type.</typeparam>
    /// <param name="items">The items in this page.</param>
    /// <param name="nextSortValue">The continuation's sort value, or <see langword="null"/>.</param>
    /// <param name="nextId">The continuation's identifier, or <see langword="null"/>.</param>
    /// <returns>The page.</returns>
    public static KeysetPage<T> From<T>(IReadOnlyList<T> items, string? nextSortValue, Guid? nextId) =>
        nextSortValue is null || nextId is null
            ? new KeysetPage<T>(items, null)
            : new KeysetPage<T>(items, new KeysetPosition(nextSortValue, nextId.Value));
}

/// <summary>
/// A keyset page request, already validated against a resource's whitelist.
/// </summary>
/// <param name="Limit">The clamped page size.</param>
/// <param name="Sort">The resolved sort, defaulted when the client supplied none.</param>
/// <param name="Position">Where to resume, or <see langword="null"/> for the first page.</param>
public sealed record KeysetRequest(int Limit, Querying.SortSpec Sort, KeysetPosition? Position);
