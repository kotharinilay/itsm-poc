using System.Buffers.Text;
using System.Globalization;
using System.Text;
using Synthia.Contracts.Paging;

namespace Synthia.Api.Paging;

/// <summary>
/// Turns a resume position into an opaque cursor, and back.
/// </summary>
/// <remarks>
/// <para>
/// <b>Opaque means a client may infer nothing from it</b> — not position, not total, not the key it
/// encodes (contracts §README). Opacity here is a contract property, not a security one: base64url
/// is encoding, not encryption, and a determined client can read it. What opacity buys is freedom
/// to change the sort key later without breaking every client that had started parsing cursors.
/// </para>
/// <para>
/// A cursor is therefore <b>never trusted as authority</b>. It selects a position within a result
/// set that the tenant filter has already bounded, so a forged one can move a caller around inside
/// what they may already see and nowhere else.
/// </para>
/// <para>
/// A malformed cursor is a 400, not an empty first page. Silently restarting the scan looks to a
/// client like the end of the collection, which is the same shape as data loss.
/// </para>
/// </remarks>
internal static class OpaqueCursor
{
    private const char Separator = '';

    /// <summary>Encodes a resume position.</summary>
    /// <param name="position">Where the next page resumes.</param>
    /// <returns>The opaque cursor.</returns>
    public static string Encode(KeysetPosition position)
    {
        string payload = string.Concat(
            position.Id.ToString("D", CultureInfo.InvariantCulture),
            Separator,
            position.SortValue);

        return Base64Url.EncodeToString(Encoding.UTF8.GetBytes(payload));
    }

    /// <summary>Decodes a cursor a client sent back.</summary>
    /// <param name="cursor">The cursor, or <see langword="null"/> for the first page.</param>
    /// <param name="position">The decoded position, when there was one.</param>
    /// <returns><see langword="false"/> when the cursor was present but unreadable.</returns>
    public static bool TryDecode(string? cursor, out KeysetPosition? position)
    {
        position = null;

        if (string.IsNullOrEmpty(cursor))
        {
            return true;
        }

        byte[] decoded;

        try
        {
            decoded = Base64Url.DecodeFromChars(cursor);
        }
        catch (FormatException)
        {
            return false;
        }

        string payload = Encoding.UTF8.GetString(decoded);
        int separator = payload.IndexOf(Separator, StringComparison.Ordinal);

        if (separator <= 0)
        {
            return false;
        }

        if (!Guid.TryParseExact(payload[..separator], "D", out Guid id))
        {
            return false;
        }

        position = new KeysetPosition(payload[(separator + 1)..], id);

        return true;
    }
}
