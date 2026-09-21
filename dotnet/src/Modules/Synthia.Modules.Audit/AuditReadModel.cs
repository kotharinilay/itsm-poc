using System.Collections.Frozen;
using Synthia.Contracts.Paging;
using Synthia.Contracts.Querying;
using Synthia.Contracts.ReadModels;
using Synthia.Persistence;
using Synthia.Persistence.Paging;
using Synthia.Persistence.Views;

namespace Synthia.Modules.Audit;

/// <summary>
/// The staff read surface over the audit trail.
/// </summary>
/// <remarks>
/// <b>Audit is not telemetry.</b> Separate stores, separate retention — seven years against thirty
/// days — and telemetry MUST NEVER answer an audit question (A2 §8.1). This
/// reads the audit store, and it is the only thing that can answer these questions.
/// </remarks>
public interface IAuditReadModel
{
    /// <summary>Searches audit records.</summary>
    /// <param name="filter">Typed narrowing over the whitelisted fields.</param>
    /// <param name="request">The validated page request.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>One page of audit records.</returns>
    Task<KeysetPage<AuditEventView>> SearchAsync(
        AuditFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken);
}

/// <summary>The sortable fields for audit search.</summary>
public static class AuditSortKeys
{
    /// <summary>
    /// The default sort. Audit is the resource the contract names an explicit default for.
    /// </summary>
    public const string Default = "occurredAt";

    private static readonly FrozenDictionary<string, IKeysetSortKey<AuditEventRow>> _events =
        new IKeysetSortKey<AuditEventRow>[]
        {
            new KeysetSortKey<AuditEventRow, DateTimeOffset>(
                "occurredAt",
                row => row.OccurredAt,
                row => row.AuditId,
                KeysetValues.Render,
                KeysetValues.ParseTimestamp),
        }.ToFrozenDictionary(key => key.Field, StringComparer.Ordinal);

    /// <summary>Sortable fields for audit search.</summary>
    public static IReadOnlyDictionary<string, IKeysetSortKey<AuditEventRow>> Events => _events;
}

/// <summary>
/// Translates a contract-level page request into the persistence-level one.
/// </summary>
/// <remarks>
/// Each module carries its own copy. See the note in <c>Synthia.Modules.Sessions</c>.
/// </remarks>
internal static class KeysetTranslation
{
    public static KeysetDirection Direction(SortSpec sort) =>
        sort.Direction == SortDirection.Descending ? KeysetDirection.Descending : KeysetDirection.Ascending;

    public static KeysetAnchor? Anchor(KeysetPosition? position) =>
        position is null ? null : new KeysetAnchor(position.Value.SortValue, position.Value.Id);
}

/// <summary>Reads audit records from the published view.</summary>
internal sealed class AuditReadModel : IAuditReadModel
{
    private readonly SynthiaReadContext _context;

    public AuditReadModel(SynthiaReadContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        _context = context;
    }

    public async Task<KeysetPage<AuditEventView>> SearchAsync(
        AuditFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(filter);
        ArgumentNullException.ThrowIfNull(request);

        IQueryable<AuditEventRow> query = _context.AuditEvents;

        if (filter.TenantId is not null)
        {
            Guid narrowed = filter.TenantId.Value.Value;
            query = query.Where(row => row.TenantId == narrowed);
        }

        if (filter.WorkItemId is not null)
        {
            Guid workItemId = filter.WorkItemId.Value.Value;
            query = query.Where(row => row.WorkItemId == workItemId);
        }

        if (filter.EventKind is not null)
        {
            string action = filter.EventKind;
            query = query.Where(row => row.Action == action);
        }

        if (filter.OccurredFrom is not null)
        {
            DateTimeOffset from = filter.OccurredFrom.Value;
            query = query.Where(row => row.OccurredAt >= from);
        }

        if (filter.OccurredTo is not null)
        {
            DateTimeOffset to = filter.OccurredTo.Value;
            query = query.Where(row => row.OccurredAt < to);
        }

        KeysetSlice<AuditEventRow> slice = await KeysetQuery
            .TakeAsync(
                query,
                AuditSortKeys.Events[request.Sort.Field],
                KeysetTranslation.Direction(request.Sort),
                KeysetTranslation.Anchor(request.Position),
                request.Limit,
                cancellationToken)
            .ConfigureAwait(false);

        return KeysetPage.From(
            slice.Rows.Select(Project).ToList(),
            slice.Next?.SortValue,
            slice.Next?.Id);
    }

    private static AuditEventView Project(AuditEventRow row) =>
        new(
            row.AuditId,
            row.TenantId,
            row.OccurredAt,
            row.WorkItemId,
            row.Action,
            row.RequestedByOid,
            row.ApprovedByOid,
            row.ExecutedBy,
            row.ExecutionMethod,
            row.Outcome,
            row.Verification,
            row.CorrelationId,
            row.RetainUntil);
}
