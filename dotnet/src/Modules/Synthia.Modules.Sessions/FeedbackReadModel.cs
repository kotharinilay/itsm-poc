using Microsoft.EntityFrameworkCore;
using Synthia.Contracts.ReadModels;
using Synthia.Persistence;
using Synthia.Persistence.Views;
using Synthia.SharedKernel.Identity;

namespace Synthia.Modules.Sessions;

/// <summary>
/// The read side of message feedback: the caller's own current signals, and the aggregate figures
/// derived from them.
/// </summary>
/// <remarks>
/// <para>
/// <b>Two reads, and they are deliberately not the same read.</b> <see cref="ListForSessionAsync"/>
/// returns current signals on one session and follows the session's content retention, because a
/// signal is content. <see cref="SummariseAsync"/> returns pre-aggregated figures from
/// <c>vw_dashboard_rollup_v1</c>, which are <b>retained independently of the signals they were
/// computed from</b> (spec FR-SESS-012, FR-SESS-014) — so expiring feedback does not erase
/// reporting history, and a report covering last year does not silently go to zero.
/// </para>
/// <para>
/// Computing the rate here instead, by counting rows, would have tied the two together: the figure
/// would fall as content expired, and nobody reading the graph would know whether engagement had
/// dropped or retention had run.
/// </para>
/// <para>
/// <b>Nothing here answers a governance question.</b> Feedback never influences authorization,
/// governance treatment, retrieval scope or execution (spec FR-SESS-013). This module is read-only
/// and lives in the monolith, which holds no write path at all (ADR-0001), so there is no route
/// from anything here back into a decision.
/// </para>
/// <para>
/// <b>No aggregate reveals a single organisation's contribution</b> (spec FR-IDENT-010). Every
/// rollup row is stamped with one <c>tenantId</c> and the global query filter applies, so there is
/// no cross-organisation total for a caller to subtract their own figures from.
/// </para>
/// </remarks>
public interface IFeedbackReadModel
{
    /// <summary>Lists the current signals on one of the caller's own sessions.</summary>
    /// <param name="requester">The caller, from the Gateway-derived header contract.</param>
    /// <param name="sessionId">The session.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>
    /// The current signals, oldest first. Empty when the session is not the caller's — the same
    /// answer as a session with no feedback, because existence is tenant-scoped information.
    /// </returns>
    Task<IReadOnlyList<MessageFeedback>> ListForSessionAsync(
        PrincipalId requester,
        SessionId sessionId,
        CancellationToken cancellationToken);

    /// <summary>Reads the pre-aggregated feedback figures for a window.</summary>
    /// <param name="windowStart">Inclusive start of the period.</param>
    /// <param name="windowEnd">Exclusive end of the period.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>
    /// One summary per aggregation window, oldest first. Read from the rollup rather than counted
    /// from the signals, which is what makes the figures outlive them.
    /// </returns>
    Task<IReadOnlyList<FeedbackSummary>> SummariseAsync(
        DateTimeOffset windowStart,
        DateTimeOffset windowEnd,
        CancellationToken cancellationToken);
}

/// <summary>Reads feedback from the published views.</summary>
internal sealed class FeedbackReadModel : IFeedbackReadModel
{
    private readonly SynthiaReadContext _context;

    public FeedbackReadModel(SynthiaReadContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        _context = context;
    }

    public async Task<IReadOnlyList<MessageFeedback>> ListForSessionAsync(
        PrincipalId requester,
        SessionId sessionId,
        CancellationToken cancellationToken)
    {
        // Ownership is re-established against the session view rather than trusted from the route.
        // A message identifier carries no ownership, and a route parameter is client input — the
        // same reason SessionReadModel re-applies the requester predicate on every nested read.
        IQueryable<Guid> ownSessions = _context.SessionSummaries
            .Where(row => row.SessionId == sessionId.Value && row.RequesterOid == requester.Value)
            .Select(row => row.SessionId);

        List<MessageFeedbackRow> rows = await _context.MessageFeedback
            .Where(row => ownSessions.Contains(row.SessionId))
            .OrderBy(row => row.UpdatedAt)
            .ThenBy(row => row.MessageId)
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

        return rows.Select(Project).ToList();
    }

    public async Task<IReadOnlyList<FeedbackSummary>> SummariseAsync(
        DateTimeOffset windowStart,
        DateTimeOffset windowEnd,
        CancellationToken cancellationToken)
    {
        List<DashboardRollupRow> rows = await _context.DashboardRollups
            .Where(row => row.WindowStart >= windowStart && row.WindowStart < windowEnd)
            .OrderBy(row => row.WindowStart)
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

        return rows.Select(Project).ToList();
    }

    private static MessageFeedback Project(MessageFeedbackRow row) =>
        new(row.MessageId, row.SessionId, row.TenantId, row.Signal, row.UpdatedAt);

    // The rate comes off the rollup unchanged. Recomputing it from anything reachable here would
    // reintroduce the dependency on the underlying signals that FR-SESS-012 exists to break.
    private static FeedbackSummary Project(DashboardRollupRow row) =>
        new(row.TenantId, row.WindowStart, row.WindowEnd, row.FeedbackRate);
}
