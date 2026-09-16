using Synthia.Api.Paging;
using Synthia.Contracts.Paging;

namespace Synthia.Api.Endpoints;

/// <summary>
/// The wire shape of a cursor-paged collection.
/// </summary>
/// <remarks>
/// <b><c>items</c> and <c>nextCursor</c> — that is the whole envelope</b> (contracts §README).
/// There is deliberately no total count and no page number: a keyset scan cannot produce either
/// cheaply, and a total that was true when the query ran is a number a client will treat as current
/// long after it stops being so.
/// </remarks>
/// <typeparam name="T">The item type.</typeparam>
/// <param name="Items">The items in this page.</param>
/// <param name="NextCursor">
/// An opaque cursor to resume from, or <see langword="null"/> when the collection is exhausted.
/// </param>
internal sealed record CursorEnvelope<T>(IReadOnlyList<T> Items, string? NextCursor);

/// <summary>Builds the wire shape of a paged collection.</summary>
internal static class CursorEnvelope
{
    /// <summary>
    /// Turns an internal page into the client-facing envelope.
    /// </summary>
    /// <remarks>
    /// This is where a resume position becomes opaque. The read models deal in positions and the
    /// edge encodes them, so nothing inside the application has to remember that clients must not
    /// see the sort key.
    /// </remarks>
    /// <typeparam name="T">The item type.</typeparam>
    /// <param name="page">The page a read model returned.</param>
    /// <returns>The envelope.</returns>
    public static CursorEnvelope<T> From<T>(KeysetPage<T> page)
    {
        ArgumentNullException.ThrowIfNull(page);

        return new CursorEnvelope<T>(
            page.Items,
            page.Next is null ? null : OpaqueCursor.Encode(page.Next.Value));
    }
}
