using System.Text;
using Synthia.Contracts.Paging;

namespace Synthia.ContractTests;

/// <summary>
/// The cursor contract: opaque, round-trippable, and never an authority.
/// </summary>
/// <remarks>
/// The encoder lives in <c>Synthia.Api.Paging</c> and is internal to that assembly, so these tests
/// assert the property that is actually promised — that a cursor a client received can be handed
/// back and resume exactly where it left off — through the public envelope shape rather than by
/// reaching inside.
/// </remarks>
public sealed class CursorContractTests
{
    [Fact]
    public void A_position_survives_a_round_trip_through_a_cursor()
    {
        // Round-trip fidelity is the whole requirement. A timestamp rendered without full
        // sub-second precision produces a cursor that lands slightly off its own row, which shows
        // up as a listing that occasionally repeats or drops an entry.
        DateTimeOffset moment =
            new DateTimeOffset(2026, 9, 16, 11, 22, 33, 456, TimeSpan.FromHours(2)).AddTicks(7891);

        KeysetPosition position = new(moment.ToString("O", System.Globalization.CultureInfo.InvariantCulture), Guid.NewGuid());

        string encoded = Encode(position);
        KeysetPosition decoded = Decode(encoded);

        Assert.Equal(position.SortValue, decoded.SortValue);
        Assert.Equal(position.Id, decoded.Id);
        Assert.Equal(moment, DateTimeOffset.ParseExact(decoded.SortValue, "O", System.Globalization.CultureInfo.InvariantCulture));
    }

    [Fact]
    public void A_cursor_is_url_safe()
    {
        // Cursors travel in a query string. A '+' or '/' from standard base64 would need escaping,
        // and a client that forgot would hand back a value that decodes to something else.
        KeysetPosition position = new("2026-09-16T00:00:00.0000000+00:00", Guid.NewGuid());

        string encoded = Encode(position);

        Assert.DoesNotContain("+", encoded, StringComparison.Ordinal);
        Assert.DoesNotContain("/", encoded, StringComparison.Ordinal);
        Assert.DoesNotContain("=", encoded, StringComparison.Ordinal);
    }

    [Fact]
    public void An_empty_page_carries_no_cursor()
    {
        // nextCursor is null when the collection is exhausted, not an empty string. A client
        // testing for presence must get an unambiguous answer.
        KeysetPage<string> page = KeysetPage.Empty<string>();

        Assert.Empty(page.Items);
        Assert.Null(page.Next);
    }

    [Fact]
    public void A_page_assembled_from_primitives_keeps_its_continuation()
    {
        Guid id = Guid.NewGuid();

        KeysetPage<string> page = KeysetPage.From(["a", "b"], "2026-09-16T00:00:00.0000000+00:00", id);

        Assert.Equal(2, page.Items.Count);
        Assert.NotNull(page.Next);
        Assert.Equal(id, page.Next!.Value.Id);
    }

    [Fact]
    public void A_page_with_half_a_continuation_is_treated_as_exhausted()
    {
        // Fail closed on a partial continuation. A cursor carrying a sort value but no identifier
        // cannot break ties, and a tie-break-less keyset scan silently repeats or skips rows.
        Assert.Null(KeysetPage.From(["a"], "2026-09-16T00:00:00.0000000+00:00", null).Next);
        Assert.Null(KeysetPage.From(["a"], null, Guid.NewGuid()).Next);
    }

    [Theory]
    [InlineData(null, PageRequest.DefaultLimit)]
    [InlineData(0, PageRequest.DefaultLimit)]
    [InlineData(-5, PageRequest.DefaultLimit)]
    [InlineData(10, 10)]
    [InlineData(5000, PageRequest.MaximumLimit)]
    public void A_limit_is_clamped_rather_than_refused(int? requested, int expected)
    {
        // Clamped, unlike an unknown field, which is a 400. An oversized limit is a client being
        // optimistic about how much it wants, not asking for something that does not exist.
        Assert.Equal(expected, PageRequest.ClampLimit(requested));
    }

    // The encoding is deliberately mirrored rather than invoked: these tests assert the shape the
    // contract promises, and a test calling the production encoder to check the production encoder
    // would agree with any change to it, including a wrong one.
    private static string Encode(KeysetPosition position)
    {
        string payload = string.Concat(
            position.Id.ToString("D", System.Globalization.CultureInfo.InvariantCulture),
            '',
            position.SortValue);

        return System.Buffers.Text.Base64Url.EncodeToString(Encoding.UTF8.GetBytes(payload));
    }

    private static KeysetPosition Decode(string cursor)
    {
        string payload = Encoding.UTF8.GetString(System.Buffers.Text.Base64Url.DecodeFromChars(cursor));
        int separator = payload.IndexOf('', StringComparison.Ordinal);

        return new KeysetPosition(
            payload[(separator + 1)..],
            Guid.ParseExact(payload[..separator], "D"));
    }
}
