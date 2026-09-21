using System.Collections.Frozen;
using Synthia.Contracts.Paging;
using Synthia.Contracts.Querying;
using Synthia.Contracts.ReadModels;
using Synthia.Persistence;
using Synthia.Persistence.Paging;
using Synthia.Persistence.Views;

namespace Synthia.Modules.Approvals;

/// <summary>
/// The staff read surface over approvals.
/// </summary>
/// <remarks>
/// <b>Note the split.</b> The queue is read from this deployable; the verdict is written to
/// RagCore (contracts §staff-api). Because both sit on one database, the read reflects the write
/// immediately — which is the property that lets the two deployables stay free of an application
/// dependency on each other.
/// </remarks>
public interface IApprovalReadModel
{
    /// <summary>Lists approvals awaiting a verdict, with their fully disclosed commands.</summary>
    /// <param name="filter">Typed narrowing over the whitelisted fields.</param>
    /// <param name="request">The validated page request.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>One page of pending approvals.</returns>
    Task<KeysetPage<ApprovalQueueEntry>> ListQueueAsync(
        ApprovalQueueFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken);

    /// <summary>
    /// Lists work that was approved and never executed.
    /// </summary>
    /// <remarks>
    /// The dead-letter surface ADR-0002 requires. Approved-but-unexecuted work surfaces to humans
    /// rather than expiring silently, and recovers only through fresh authorization.
    /// </remarks>
    /// <param name="filter">Typed narrowing over the whitelisted fields.</param>
    /// <param name="request">The validated page request.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>One page of unexecuted approvals.</returns>
    Task<KeysetPage<UnexecutedApproval>> ListUnexecutedAsync(
        ApprovalQueueFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken);
}

/// <summary>The sortable fields for this module's resources, and how to page by each.</summary>
/// <remarks>
/// The complete sets from <c>contracts/README.md</c>. A field absent here is not sortable on that
/// resource and a request naming one is a 400.
/// </remarks>
public static class ApprovalSortKeys
{
    /// <summary>
    /// The default sort for the queue, matching the contract's <c>-createdAt</c> rule.
    /// </summary>
    public const string QueueDefault = "createdAt";

    /// <summary>
    /// The default sort for the unexecuted surface.
    /// </summary>
    /// <remarks>
    /// <b>A stated divergence from the contract's default rule, not an oversight.</b>
    /// <c>contracts/README.md</c> says the default is <c>-createdAt</c> where the client supplies
    /// none, but that resource's sortable set is <c>decidedAt</c> and <c>expiresAt</c> — it does
    /// not contain <c>createdAt</c>, so the stated default is unsatisfiable there. Keyset paging
    /// needs a deterministic order, so the nearest sortable timestamp is used and the divergence
    /// is recorded here rather than resolved silently (.claude/rules/70-adr.md).
    /// </remarks>
    public const string UnexecutedDefault = "decidedAt";

    private static readonly FrozenDictionary<string, IKeysetSortKey<ApprovalQueueRow>> _queue =
        new IKeysetSortKey<ApprovalQueueRow>[]
        {
            new KeysetSortKey<ApprovalQueueRow, DateTimeOffset>(
                "createdAt",
                row => row.CreatedAt,
                row => row.ApprovalId,
                KeysetValues.Render,
                KeysetValues.ParseTimestamp),
            new KeysetSortKey<ApprovalQueueRow, DateTimeOffset?>(
                "expiresAt",
                row => row.ExpiresAt,
                row => row.ApprovalId,
                KeysetValues.Render,
                KeysetValues.ParseNullableTimestamp),
        }.ToFrozenDictionary(key => key.Field, StringComparer.Ordinal);

    private static readonly FrozenDictionary<string, IKeysetSortKey<ApprovalUnexecutedRow>> _unexecuted =
        new IKeysetSortKey<ApprovalUnexecutedRow>[]
        {
            new KeysetSortKey<ApprovalUnexecutedRow, DateTimeOffset>(
                "decidedAt",
                row => row.DecidedAt,
                row => row.ApprovalId,
                KeysetValues.Render,
                KeysetValues.ParseTimestamp),
            new KeysetSortKey<ApprovalUnexecutedRow, DateTimeOffset?>(
                "expiresAt",
                row => row.ExpiresAt,
                row => row.ApprovalId,
                KeysetValues.Render,
                KeysetValues.ParseNullableTimestamp),
        }.ToFrozenDictionary(key => key.Field, StringComparer.Ordinal);

    /// <summary>Sortable fields for the approval queue.</summary>
    public static IReadOnlyDictionary<string, IKeysetSortKey<ApprovalQueueRow>> Queue => _queue;

    /// <summary>Sortable fields for the unexecuted surface.</summary>
    public static IReadOnlyDictionary<string, IKeysetSortKey<ApprovalUnexecutedRow>> Unexecuted => _unexecuted;
}

/// <summary>
/// Translates a contract-level page request into the persistence-level one.
/// </summary>
/// <remarks>
/// Each module carries its own copy. See the note in <c>Synthia.Modules.Sessions</c>: Contracts and
/// Persistence are siblings that may not reference each other, and duplication across a boundary is
/// cheaper than forcing six isolated modules onto a shared dependency (.claude/rules/10-principles.md P-6).
/// </remarks>
internal static class KeysetTranslation
{
    public static KeysetDirection Direction(SortSpec sort) =>
        sort.Direction == SortDirection.Descending ? KeysetDirection.Descending : KeysetDirection.Ascending;

    public static KeysetAnchor? Anchor(KeysetPosition? position) =>
        position is null ? null : new KeysetAnchor(position.Value.SortValue, position.Value.Id);
}

/// <summary>Reads approvals from the published views.</summary>
internal sealed class ApprovalReadModel : IApprovalReadModel
{
    private readonly SynthiaReadContext _context;

    public ApprovalReadModel(SynthiaReadContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        _context = context;
    }

    public async Task<KeysetPage<ApprovalQueueEntry>> ListQueueAsync(
        ApprovalQueueFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(filter);
        ArgumentNullException.ThrowIfNull(request);

        IQueryable<ApprovalQueueRow> query = _context.ApprovalQueue;

        if (filter.TenantId is not null)
        {
            Guid narrowed = filter.TenantId.Value.Value;
            query = query.Where(row => row.TenantId == narrowed);
        }

        KeysetSlice<ApprovalQueueRow> slice = await KeysetQuery
            .TakeAsync(
                query,
                ApprovalSortKeys.Queue[request.Sort.Field],
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

    public async Task<KeysetPage<UnexecutedApproval>> ListUnexecutedAsync(
        ApprovalQueueFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(filter);
        ArgumentNullException.ThrowIfNull(request);

        IQueryable<ApprovalUnexecutedRow> query = _context.UnexecutedApprovals;

        if (filter.TenantId is not null)
        {
            Guid narrowed = filter.TenantId.Value.Value;
            query = query.Where(row => row.TenantId == narrowed);
        }

        KeysetSlice<ApprovalUnexecutedRow> slice = await KeysetQuery
            .TakeAsync(
                query,
                ApprovalSortKeys.Unexecuted[request.Sort.Field],
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

    private static ApprovalQueueEntry Project(ApprovalQueueRow row) =>
        new(
            row.ApprovalId,
            row.WorkItemId,
            row.TenantId,
            row.CatalogueId,
            row.CatalogueVersion,
            row.DisclosedCommands,
            row.RequestedAt,
            row.ExpiresAt,
            row.CreatedAt,
            row.UpdatedAt,
            row.Version);

    private static UnexecutedApproval Project(ApprovalUnexecutedRow row) =>
        new(
            row.ApprovalId,
            row.WorkItemId,
            row.TenantId,
            row.CatalogueId,
            row.DecidedAt,
            row.DecidedByOid,
            row.ExpiresAt,
            row.Version);
}
