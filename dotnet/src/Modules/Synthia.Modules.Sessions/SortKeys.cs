using System.Collections.Frozen;
using Synthia.Contracts.Querying;
using Synthia.Persistence.Paging;
using Synthia.Persistence.Views;
using Synthia.SharedKernel.Sessions;

namespace Synthia.Modules.Sessions;

/// <summary>
/// The sortable fields for this module's resources, and how to page by each.
/// </summary>
/// <remarks>
/// <para>
/// <b>These sets are the complete ones from <c>contracts/README.md</c>.</b> A field absent here is
/// not sortable on that resource, and a request naming one is a 400 — never silently ignored.
/// Adding a field is a contract change, and it is made here.
/// </para>
/// <para>
/// The API layer decides whether a requested field is allowed; this decides what allowing it means.
/// Keeping the two apart is what lets the whitelist be asserted against the contract document
/// without a database in the room.
/// </para>
/// </remarks>
public static class SessionSortKeys
{
    /// <summary>The sort applied when a client supplies none.</summary>
    public const string Default = "createdAt";

    private static readonly FrozenDictionary<string, IKeysetSortKey<SessionSummaryRow>> _summaries =
        new IKeysetSortKey<SessionSummaryRow>[]
        {
            new KeysetSortKey<SessionSummaryRow, DateTimeOffset>(
                "createdAt",
                row => row.CreatedAt,
                row => row.SessionId,
                KeysetValues.Render,
                KeysetValues.ParseTimestamp),
            new KeysetSortKey<SessionSummaryRow, DateTimeOffset>(
                "updatedAt",
                row => row.UpdatedAt,
                row => row.SessionId,
                KeysetValues.Render,
                KeysetValues.ParseTimestamp),
            new KeysetSortKey<SessionSummaryRow, SessionState>(
                "state",
                row => row.State,
                row => row.SessionId,
                KeysetValues.RenderEnum,
                KeysetValues.ParseEnum<SessionState>),
        }.ToFrozenDictionary(key => key.Field, StringComparer.Ordinal);

    private static readonly FrozenDictionary<string, IKeysetSortKey<SessionMessageRow>> _messages =
        new IKeysetSortKey<SessionMessageRow>[]
        {
            new KeysetSortKey<SessionMessageRow, DateTimeOffset>(
                "createdAt",
                row => row.CreatedAt,
                row => row.MessageId,
                KeysetValues.Render,
                KeysetValues.ParseTimestamp),
        }.ToFrozenDictionary(key => key.Field, StringComparer.Ordinal);

    /// <summary>Sortable fields for a session listing.</summary>
    public static IReadOnlyDictionary<string, IKeysetSortKey<SessionSummaryRow>> Summaries => _summaries;

    /// <summary>Sortable fields for a conversation history.</summary>
    public static IReadOnlyDictionary<string, IKeysetSortKey<SessionMessageRow>> Messages => _messages;
}

/// <summary>
/// Translates a contract-level page request into the persistence-level one.
/// </summary>
/// <remarks>
/// <para>
/// <c>Synthia.Contracts</c> and <c>Synthia.Persistence</c> are siblings: neither may reference the
/// other (plan §Dependency direction), so each owns its own vocabulary for a sort direction and a
/// resume position. A module is the only project that can see both, which makes it the only place
/// this translation can live.
/// </para>
/// <para>
/// <b>Every module carries its own copy, deliberately.</b> Hoisting eight lines into a shared type
/// would force six isolated modules onto a common dependency to remove a duplication that costs
/// nothing — and duplication across a boundary is cheaper than a false shared contract
/// (constitution Principle VI).
/// </para>
/// </remarks>
internal static class KeysetTranslation
{
    public static KeysetDirection Direction(SortSpec sort) =>
        sort.Direction == SortDirection.Descending ? KeysetDirection.Descending : KeysetDirection.Ascending;

    public static KeysetAnchor? Anchor(Contracts.Paging.KeysetPosition? position) =>
        position is null ? null : new KeysetAnchor(position.Value.SortValue, position.Value.Id);
}
