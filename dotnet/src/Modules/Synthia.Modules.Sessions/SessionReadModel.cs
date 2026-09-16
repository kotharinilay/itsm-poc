using Microsoft.EntityFrameworkCore;
using Synthia.Contracts.Paging;
using Synthia.Contracts.ReadModels;
using Synthia.Persistence;
using Synthia.Persistence.Paging;
using Synthia.Persistence.Views;
using Synthia.SharedKernel.Identity;

namespace Synthia.Modules.Sessions;

/// <summary>
/// The customer read surface over a session.
/// </summary>
/// <remarks>
/// <b>Scoped to the caller's own organisation and their own sessions.</b> The organisation comes
/// from the global query filter, which no query here can escape; ownership is the requester
/// predicate below. A session belonging to another user or organisation returns nothing, and the
/// endpoint turns that into a 404 — existence is itself tenant-scoped information.
/// </remarks>
public interface ICustomerSessionReadModel
{
    /// <summary>Lists the caller's own sessions.</summary>
    /// <param name="requester">The caller, from the Gateway-derived header contract.</param>
    /// <param name="filter">Typed narrowing over the whitelisted fields.</param>
    /// <param name="request">The validated page request.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>One page of sessions.</returns>
    Task<KeysetPage<SessionSummary>> ListAsync(
        PrincipalId requester,
        SessionListFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken);

    /// <summary>Reads one of the caller's own sessions.</summary>
    /// <param name="requester">The caller.</param>
    /// <param name="sessionId">The session.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>The session, or <see langword="null"/> when it is not theirs.</returns>
    Task<SessionSummary?> FindAsync(
        PrincipalId requester,
        SessionId sessionId,
        CancellationToken cancellationToken);

    /// <summary>Lists the conversation history of one of the caller's own sessions.</summary>
    /// <param name="requester">The caller.</param>
    /// <param name="sessionId">The session.</param>
    /// <param name="filter">Typed narrowing over the whitelisted fields.</param>
    /// <param name="request">The validated page request.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>One page of messages.</returns>
    Task<KeysetPage<SessionMessage>> ListMessagesAsync(
        PrincipalId requester,
        SessionId sessionId,
        SessionMessageFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken);

    /// <summary>Reads the step trail of one of the caller's own sessions.</summary>
    /// <param name="requester">The caller.</param>
    /// <param name="sessionId">The session.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>The step trail, oldest first.</returns>
    Task<IReadOnlyList<SessionStep>> ListStepsAsync(
        PrincipalId requester,
        SessionId sessionId,
        CancellationToken cancellationToken);
}

/// <summary>
/// The staff read surface over sessions.
/// </summary>
/// <remarks>
/// Staff read across the organisations they are entitled to see; the <c>tenantId</c> filter is a
/// narrowing within that set and never a widening (contracts §README rule 1). There is no
/// staff-side way to originate a session — that is absent by design, not missing.
/// </remarks>
public interface IStaffSessionReadModel
{
    /// <summary>Lists live sessions.</summary>
    /// <param name="filter">Typed narrowing over the whitelisted fields.</param>
    /// <param name="request">The validated page request.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>One page of sessions.</returns>
    Task<KeysetPage<SessionSummary>> ListLiveAsync(
        StaffSessionFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken);

    /// <summary>Reads one session.</summary>
    /// <param name="sessionId">The session.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>The session, or <see langword="null"/>.</returns>
    Task<SessionSummary?> FindAsync(SessionId sessionId, CancellationToken cancellationToken);

    /// <summary>Reads a session's step trail.</summary>
    /// <param name="sessionId">The session.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>The step trail, oldest first.</returns>
    Task<IReadOnlyList<SessionStep>> ListStepsAsync(SessionId sessionId, CancellationToken cancellationToken);
}

/// <summary>Reads sessions from the published views.</summary>
internal sealed class SessionReadModel : ICustomerSessionReadModel, IStaffSessionReadModel
{
    private readonly SynthiaReadContext _context;

    public SessionReadModel(SynthiaReadContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        _context = context;
    }

    public async Task<KeysetPage<SessionSummary>> ListAsync(
        PrincipalId requester,
        SessionListFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(filter);
        ArgumentNullException.ThrowIfNull(request);

        IQueryable<SessionSummaryRow> query = _context.SessionSummaries
            .Where(row => row.RequesterOid == requester.Value);

        if (filter.State is not null)
        {
            query = query.Where(row => row.State == filter.State);
        }

        return await PageSummariesAsync(query, request, cancellationToken).ConfigureAwait(false);
    }

    public async Task<SessionSummary?> FindAsync(
        PrincipalId requester,
        SessionId sessionId,
        CancellationToken cancellationToken)
    {
        SessionSummaryRow? row = await _context.SessionSummaries
            .Where(candidate => candidate.SessionId == sessionId.Value)
            .Where(candidate => candidate.RequesterOid == requester.Value)
            .FirstOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);

        return row is null ? null : Project(row);
    }

    public async Task<KeysetPage<SessionMessage>> ListMessagesAsync(
        PrincipalId requester,
        SessionId sessionId,
        SessionMessageFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(filter);
        ArgumentNullException.ThrowIfNull(request);

        // The ownership predicate is re-applied against the session view rather than trusted from
        // the route. A message identifier does not carry ownership, and the route is client input.
        IQueryable<Guid> ownSessions = _context.SessionSummaries
            .Where(row => row.SessionId == sessionId.Value && row.RequesterOid == requester.Value)
            .Select(row => row.SessionId);

        IQueryable<SessionMessageRow> query = _context.SessionMessages
            .Where(row => ownSessions.Contains(row.SessionId));

        if (filter.SenderKind is not null)
        {
            query = query.Where(row => row.SenderKind == filter.SenderKind);
        }

        IKeysetSortKey<SessionMessageRow> sortKey = SessionSortKeys.Messages[request.Sort.Field];

        KeysetSlice<SessionMessageRow> slice = await KeysetQuery
            .TakeAsync(
                query,
                sortKey,
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

    public async Task<IReadOnlyList<SessionStep>> ListStepsAsync(
        PrincipalId requester,
        SessionId sessionId,
        CancellationToken cancellationToken)
    {
        IQueryable<Guid> ownSessions = _context.SessionSummaries
            .Where(row => row.SessionId == sessionId.Value && row.RequesterOid == requester.Value)
            .Select(row => row.SessionId);

        List<SessionStepRow> rows = await _context.SessionSteps
            .Where(row => ownSessions.Contains(row.SessionId))
            .OrderBy(row => row.CreatedAt)
            .ThenBy(row => row.StepId)
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

        return rows.Select(Project).ToList();
    }

    public async Task<KeysetPage<SessionSummary>> ListLiveAsync(
        StaffSessionFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(filter);
        ArgumentNullException.ThrowIfNull(request);

        IQueryable<SessionSummaryRow> query = _context.SessionSummaries
            .Where(row => row.ClosedAt == null);

        if (filter.State is not null)
        {
            query = query.Where(row => row.State == filter.State);
        }

        if (filter.TenantId is not null)
        {
            Guid narrowed = filter.TenantId.Value.Value;
            query = query.Where(row => row.TenantId == narrowed);
        }

        return await PageSummariesAsync(query, request, cancellationToken).ConfigureAwait(false);
    }

    public async Task<SessionSummary?> FindAsync(SessionId sessionId, CancellationToken cancellationToken)
    {
        SessionSummaryRow? row = await _context.SessionSummaries
            .Where(candidate => candidate.SessionId == sessionId.Value)
            .FirstOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);

        return row is null ? null : Project(row);
    }

    public async Task<IReadOnlyList<SessionStep>> ListStepsAsync(
        SessionId sessionId,
        CancellationToken cancellationToken)
    {
        List<SessionStepRow> rows = await _context.SessionSteps
            .Where(row => row.SessionId == sessionId.Value)
            .OrderBy(row => row.CreatedAt)
            .ThenBy(row => row.StepId)
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

        return rows.Select(Project).ToList();
    }

    private static SessionSummary Project(SessionSummaryRow row) =>
        new(row.SessionId, row.TenantId, row.State, row.CaseReference, row.CreatedAt, row.UpdatedAt, row.ClosedAt);

    private static SessionMessage Project(SessionMessageRow row) =>
        new(row.MessageId, row.SessionId, row.TenantId, row.SenderKind, row.SenderOid, row.Body, row.CreatedAt);

    private static SessionStep Project(SessionStepRow row) =>
        new(row.StepId, row.SessionId, row.TenantId, row.Kind, row.Summary, row.CreatedAt);

    private static async Task<KeysetPage<SessionSummary>> PageSummariesAsync(
        IQueryable<SessionSummaryRow> query,
        KeysetRequest request,
        CancellationToken cancellationToken)
    {
        IKeysetSortKey<SessionSummaryRow> sortKey = SessionSortKeys.Summaries[request.Sort.Field];

        KeysetSlice<SessionSummaryRow> slice = await KeysetQuery
            .TakeAsync(
                query,
                sortKey,
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
}
