using System.Globalization;
using Synthia.Api.Paging;
using Synthia.Contracts.Paging;
using Synthia.Contracts.Querying;

namespace Synthia.Api.Querying;

/// <summary>
/// Binds <c>?limit=</c>, <c>?cursor=</c> and <c>?sort=</c> into a validated page request.
/// </summary>
/// <remarks>
/// <b>Parse external input into precise internal types at the boundary</b> (constitution
/// Principle VI). Past this point a read model receives a <see cref="KeysetRequest"/> whose sort
/// field is known to be whitelisted and whose cursor is known to be readable — it has no
/// validation left to do and no way to skip any.
/// </remarks>
internal static class QueryBinding
{
    /// <summary>
    /// Binds the paging and sorting parameters of a request.
    /// </summary>
    /// <param name="query">The query string.</param>
    /// <param name="whitelist">The resource's allowed fields and default sort.</param>
    /// <param name="request">The validated request, when binding succeeded.</param>
    /// <param name="detail">A client-safe explanation, when it did not.</param>
    /// <returns><see langword="false"/> when the request must be refused with a 400.</returns>
    public static bool TryBindPage(
        IQueryCollection query,
        QueryWhitelist whitelist,
        out KeysetRequest? request,
        out string? detail)
    {
        ArgumentNullException.ThrowIfNull(query);
        ArgumentNullException.ThrowIfNull(whitelist);

        request = null;

        string? rawSort = query["sort"].FirstOrDefault();

        if (!whitelist.TryResolveSort(rawSort, out SortSpec sort))
        {
            detail = $"'{rawSort}' is not a sortable field on this resource. Sortable fields are: " +
                     $"{string.Join(", ", whitelist.SortableFields.Order(StringComparer.Ordinal))}.";
            return false;
        }

        if (!OpaqueCursor.TryDecode(query["cursor"].FirstOrDefault(), out KeysetPosition? position))
        {
            // Not a silent restart. A cursor that cannot be read is a client bug or a tampered
            // value, and answering with page one looks exactly like the end of the collection.
            detail = "The cursor could not be read. Cursors are opaque and must be echoed back " +
                     "exactly as they were issued.";
            return false;
        }

        if (!TryBindLimit(query, out int limit, out detail))
        {
            return false;
        }

        request = new KeysetRequest(limit, sort, position);
        detail = null;

        return true;
    }

    /// <summary>Reads an optional, whitelisted enum filter.</summary>
    /// <typeparam name="TEnum">The enum type.</typeparam>
    /// <param name="query">The query string.</param>
    /// <param name="field">The field name, as the contract spells it.</param>
    /// <param name="value">The parsed value, or <see langword="null"/> when absent.</param>
    /// <param name="detail">A client-safe explanation, when the value was unreadable.</param>
    /// <returns><see langword="false"/> when the request must be refused with a 400.</returns>
    public static bool TryBindEnum<TEnum>(
        IQueryCollection query,
        string field,
        out TEnum? value,
        out string? detail)
        where TEnum : struct, Enum
    {
        ArgumentNullException.ThrowIfNull(query);

        value = null;
        detail = null;

        string? raw = query[field].FirstOrDefault();

        if (string.IsNullOrEmpty(raw))
        {
            return true;
        }

        // Unknown is the unset sentinel on every enum in this platform. Accepting it as a filter
        // value would let a client ask for rows whose state is "we do not know", which is not a
        // question the data can answer.
        if (!Enum.TryParse(raw, ignoreCase: true, out TEnum parsed) ||
            string.Equals(parsed.ToString(), "Unknown", StringComparison.Ordinal))
        {
            detail = $"'{raw}' is not a valid value for {field}. Accepted values are: " +
                     $"{string.Join(", ", AcceptedValues<TEnum>())}.";
            return false;
        }

        value = parsed;

        return true;
    }

    /// <summary>Reads an optional identifier filter.</summary>
    /// <param name="query">The query string.</param>
    /// <param name="field">The field name, as the contract spells it.</param>
    /// <param name="value">The parsed identifier, or <see langword="null"/> when absent.</param>
    /// <param name="detail">A client-safe explanation, when the value was unreadable.</param>
    /// <returns><see langword="false"/> when the request must be refused with a 400.</returns>
    public static bool TryBindGuid(
        IQueryCollection query,
        string field,
        out Guid? value,
        out string? detail)
    {
        ArgumentNullException.ThrowIfNull(query);

        value = null;
        detail = null;

        string? raw = query[field].FirstOrDefault();

        if (string.IsNullOrEmpty(raw))
        {
            return true;
        }

        if (!Guid.TryParseExact(raw, "D", out Guid parsed))
        {
            detail = $"'{field}' must be a UUID in 8-4-4-4-12 form.";
            return false;
        }

        value = parsed;

        return true;
    }

    /// <summary>Reads an optional timestamp filter.</summary>
    /// <param name="query">The query string.</param>
    /// <param name="field">The field name, as the contract spells it.</param>
    /// <param name="value">The parsed timestamp, or <see langword="null"/> when absent.</param>
    /// <param name="detail">A client-safe explanation, when the value was unreadable.</param>
    /// <returns><see langword="false"/> when the request must be refused with a 400.</returns>
    public static bool TryBindTimestamp(
        IQueryCollection query,
        string field,
        out DateTimeOffset? value,
        out string? detail)
    {
        ArgumentNullException.ThrowIfNull(query);

        value = null;
        detail = null;

        string? raw = query[field].FirstOrDefault();

        if (string.IsNullOrEmpty(raw))
        {
            return true;
        }

        if (!DateTimeOffset.TryParse(
                raw,
                CultureInfo.InvariantCulture,
                DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal,
                out DateTimeOffset parsed))
        {
            detail = $"'{field}' must be an ISO-8601 timestamp.";
            return false;
        }

        value = parsed;

        return true;
    }

    /// <summary>
    /// Refuses any filter parameter the resource does not whitelist.
    /// </summary>
    /// <remarks>
    /// The positive checks above confirm that the fields a resource <i>does</i> accept are
    /// readable. This confirms there are no others — which is the half that stops a client
    /// believing it narrowed a result set that the server returned whole.
    /// </remarks>
    /// <param name="query">The query string.</param>
    /// <param name="whitelist">The resource's allowed fields.</param>
    /// <param name="detail">A client-safe explanation, when an unknown field was present.</param>
    /// <returns><see langword="false"/> when the request must be refused with a 400.</returns>
    public static bool TryRejectUnknownFilters(
        IQueryCollection query,
        QueryWhitelist whitelist,
        out string? detail)
    {
        ArgumentNullException.ThrowIfNull(query);
        ArgumentNullException.ThrowIfNull(whitelist);

        foreach (string name in query.Keys)
        {
            if (string.Equals(name, "sort", StringComparison.Ordinal) ||
                string.Equals(name, "cursor", StringComparison.Ordinal) ||
                string.Equals(name, "limit", StringComparison.Ordinal))
            {
                continue;
            }

            if (!whitelist.AllowsFilterOn(name))
            {
                detail = $"'{name}' is not a filterable field on this resource. Filterable fields " +
                         $"are: {string.Join(", ", whitelist.FilterableFields.Order(StringComparer.Ordinal))}.";
                return false;
            }
        }

        detail = null;

        return true;
    }

    private static bool TryBindLimit(IQueryCollection query, out int limit, out string? detail)
    {
        string? raw = query["limit"].FirstOrDefault();

        if (string.IsNullOrEmpty(raw))
        {
            limit = PageRequest.DefaultLimit;
            detail = null;
            return true;
        }

        if (!int.TryParse(raw, NumberStyles.None, CultureInfo.InvariantCulture, out int requested))
        {
            limit = PageRequest.DefaultLimit;
            detail = "'limit' must be a positive whole number.";
            return false;
        }

        // Clamped rather than refused, unlike an unknown field. An oversized limit is a client
        // being optimistic about how much it wants, not a client asking for something that does
        // not exist — and refusing it would teach nothing (see PageRequest.ClampLimit).
        limit = PageRequest.ClampLimit(requested);
        detail = null;

        return true;
    }

    private static IEnumerable<string> AcceptedValues<TEnum>()
        where TEnum : struct, Enum =>
        Enum.GetNames<TEnum>()
            .Where(name => !string.Equals(name, "Unknown", StringComparison.Ordinal))
            .Select(name => char.ToLowerInvariant(name[0]) + name[1..]);
}
