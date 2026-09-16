using Synthia.Api.Authorization;
using Synthia.Api.Errors;
using Synthia.Api.Middleware;
using Synthia.Api.Querying;
using Synthia.Contracts.Paging;
using Synthia.Contracts.ReadModels;
using Synthia.Modules.Approvals;
using Synthia.Modules.Audit;
using Synthia.Modules.Sessions;
using Synthia.Modules.Tenancy;
using Synthia.SharedKernel.Authorization;
using Synthia.SharedKernel.Identity;
using Synthia.SharedKernel.Sessions;

namespace Synthia.Api.Endpoints;

/// <summary>
/// Staff read models. <b>Every route here is a read.</b>
/// </summary>
/// <remarks>
/// <para>
/// Note the split the contract makes: the approval <b>queue</b> is read from this deployable, and
/// the <b>verdict</b> is written to RagCore. Because both sit on one database the read reflects the
/// write immediately, which is what lets the two deployables stay free of an application dependency
/// on each other (contracts §staff-api).
/// </para>
/// <para>
/// <b>There is no route here to start a session or raise a request.</b> That is absent by design,
/// not missing: take-over is participation in an existing session, never origination, and staff
/// needing their own support use a customer surface.
/// </para>
/// <para>
/// In the initial release <c>technician</c> may approve and <c>administrator</c> may not, and no
/// operation accepts <c>senior_technician</c>. Those are disjoint capability sets, not a ladder —
/// which is why the dashboard and registry routes below name <c>administrator</c> and the queue
/// routes name <c>technician</c>, with no route naming both by implication.
/// </para>
/// </remarks>
internal static class StaffViewEndpoints
{
    /// <summary>Maps the staff read routes.</summary>
    /// <param name="app">The application being built.</param>
    /// <returns>The same application, for chaining.</returns>
    public static WebApplication MapStaffViewEndpoints(this WebApplication app)
    {
        ArgumentNullException.ThrowIfNull(app);

        RouteGroupBuilder views = app
            .MapGroup($"{AudienceRouting.StaffPrefix}/views")
            .WithTags("staff-views");

        views.MapGet("/sessions/live", ListLiveSessionsAsync)
            .WithName("StaffListLiveSessions")
            .WithSummary("Lists live sessions. Cursor paged.")
            .AcceptsRoles(StaffRole.Technician);

        views.MapGet("/sessions/{sessionId:guid}", GetSessionAsync)
            .WithName("StaffGetSession")
            .WithSummary("Reads one session and its step trail.")
            .AcceptsRoles(StaffRole.Technician);

        views.MapGet("/approvals/queue", ListApprovalQueueAsync)
            .WithName("StaffListApprovalQueue")
            .WithSummary("Lists pending approvals with their fully disclosed commands. Cursor paged.")
            .AcceptsRoles(StaffRole.Technician);

        views.MapGet("/approvals/unexecuted", ListUnexecutedApprovalsAsync)
            .WithName("StaffListUnexecutedApprovals")
            .WithSummary("Lists work approved but never executed. Cursor paged.")
            .AcceptsRoles(StaffRole.Technician);

        views.MapGet("/audit", SearchAuditAsync)
            .WithName("StaffSearchAudit")
            .WithSummary("Searches audit records. Cursor paged.")
            .AcceptsRoles(StaffRole.Technician);

        views.MapGet("/dashboard/platform", GetPlatformDashboardAsync)
            .WithName("StaffGetPlatformDashboard")
            .WithSummary("Reads the platform rollup. Aggregate only; no per-organisation breakdown.")
            .AcceptsRoles(StaffRole.Administrator);

        views.MapGet("/tenants", ListTenantsAsync)
            .WithName("StaffListTenants")
            .WithSummary("Lists organisations. Cursor paged.")
            .AcceptsRoles(StaffRole.Administrator);

        return app;
    }

    private static async Task<IResult> ListLiveSessionsAsync(
        HttpContext context,
        IStaffSessionReadModel sessions,
        CancellationToken cancellationToken)
    {
        if (!QueryBinding.TryRejectUnknownFilters(
                context.Request.Query,
                ResourceQueries.StaffLiveSessions,
                out string? detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindPage(
                context.Request.Query,
                ResourceQueries.StaffLiveSessions,
                out KeysetRequest? page,
                out detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindEnum(context.Request.Query, "state", out SessionState? state, out detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindGuid(context.Request.Query, "tenantId", out Guid? tenantId, out detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        KeysetPage<SessionSummary> result = await sessions
            .ListLiveAsync(
                new StaffSessionFilter(state, Narrowing(tenantId)),
                page!,
                cancellationToken)
            .ConfigureAwait(false);

        return Results.Ok(CursorEnvelope.From(result));
    }

    private static async Task<IResult> GetSessionAsync(
        HttpContext context,
        Guid sessionId,
        IStaffSessionReadModel sessions,
        CancellationToken cancellationToken)
    {
        SessionSummary? session = await sessions
            .FindAsync(new SessionId(sessionId), cancellationToken)
            .ConfigureAwait(false);

        if (session is null)
        {
            return Problems.NotFound(context);
        }

        IReadOnlyList<SessionStep> steps = await sessions
            .ListStepsAsync(new SessionId(sessionId), cancellationToken)
            .ConfigureAwait(false);

        return Results.Ok(new StaffSessionDetail(session, steps));
    }

    private static async Task<IResult> ListApprovalQueueAsync(
        HttpContext context,
        IApprovalReadModel approvals,
        CancellationToken cancellationToken)
    {
        if (!TryBindTenantNarrowedPage(
                context,
                ResourceQueries.StaffApprovalQueue,
                out KeysetRequest? page,
                out ApprovalQueueFilter? filter,
                out string? detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        KeysetPage<ApprovalQueueEntry> result = await approvals
            .ListQueueAsync(filter!, page!, cancellationToken)
            .ConfigureAwait(false);

        return Results.Ok(CursorEnvelope.From(result));
    }

    private static async Task<IResult> ListUnexecutedApprovalsAsync(
        HttpContext context,
        IApprovalReadModel approvals,
        CancellationToken cancellationToken)
    {
        if (!TryBindTenantNarrowedPage(
                context,
                ResourceQueries.StaffUnexecutedApprovals,
                out KeysetRequest? page,
                out ApprovalQueueFilter? filter,
                out string? detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        KeysetPage<UnexecutedApproval> result = await approvals
            .ListUnexecutedAsync(filter!, page!, cancellationToken)
            .ConfigureAwait(false);

        return Results.Ok(CursorEnvelope.From(result));
    }

    private static async Task<IResult> SearchAuditAsync(
        HttpContext context,
        IAuditReadModel audit,
        CancellationToken cancellationToken)
    {
        if (!QueryBinding.TryRejectUnknownFilters(
                context.Request.Query,
                ResourceQueries.StaffAudit,
                out string? detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindPage(
                context.Request.Query,
                ResourceQueries.StaffAudit,
                out KeysetRequest? page,
                out detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindGuid(context.Request.Query, "tenantId", out Guid? tenantId, out detail) ||
            !QueryBinding.TryBindGuid(context.Request.Query, "workItemId", out Guid? workItemId, out detail) ||
            !QueryBinding.TryBindTimestamp(context.Request.Query, "occurredFrom", out DateTimeOffset? from, out detail) ||
            !QueryBinding.TryBindTimestamp(context.Request.Query, "occurredTo", out DateTimeOffset? to, out detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (from is not null && to is not null && from >= to)
        {
            return Problems.ValidationFailed(
                context,
                "'occurredFrom' must be earlier than 'occurredTo'. The range is inclusive of the " +
                "lower bound and exclusive of the upper.");
        }

        KeysetPage<AuditEventView> result = await audit
            .SearchAsync(
                new AuditFilter(
                    Narrowing(tenantId),
                    workItemId is null ? null : new WorkItemId(workItemId.Value),
                    context.Request.Query["eventKind"].FirstOrDefault(),
                    from,
                    to),
                page!,
                cancellationToken)
            .ConfigureAwait(false);

        return Results.Ok(CursorEnvelope.From(result));
    }

    private static async Task<IResult> GetPlatformDashboardAsync(
        HttpContext context,
        IDashboardReadModel dashboard,
        CancellationToken cancellationToken)
    {
        DashboardRollup? rollup = await dashboard
            .GetPlatformAsync(cancellationToken)
            .ConfigureAwait(false);

        return rollup is null ? Problems.NotFound(context) : Results.Ok(rollup);
    }

    private static async Task<IResult> ListTenantsAsync(
        HttpContext context,
        ITenantReadModel tenants,
        CancellationToken cancellationToken)
    {
        if (!QueryBinding.TryRejectUnknownFilters(
                context.Request.Query,
                ResourceQueries.StaffTenants,
                out string? detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindPage(
                context.Request.Query,
                ResourceQueries.StaffTenants,
                out KeysetRequest? page,
                out detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindEnum(context.Request.Query, "status", out TenantStatus? status, out detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        KeysetPage<TenantView> result = await tenants
            .ListAsync(new TenantRegistryFilter(status), page!, cancellationToken)
            .ConfigureAwait(false);

        return Results.Ok(CursorEnvelope.From(result));
    }

    /// <summary>
    /// Turns a supplied <c>tenantId</c> into a narrowing, never an authority.
    /// </summary>
    /// <remarks>
    /// The value reaches the query as one more <c>WHERE</c> clause underneath the global scope
    /// filter, so a caller naming an organisation outside their scope receives no rows rather than
    /// that organisation's rows. It narrows; it cannot widen (contracts §README rule 1).
    /// </remarks>
    private static TenantId? Narrowing(Guid? tenantId) =>
        tenantId is null ? null : new TenantId(tenantId.Value);

    private static bool TryBindTenantNarrowedPage(
        HttpContext context,
        Contracts.Querying.QueryWhitelist whitelist,
        out KeysetRequest? page,
        out ApprovalQueueFilter? filter,
        out string? detail)
    {
        page = null;
        filter = null;

        if (!QueryBinding.TryRejectUnknownFilters(context.Request.Query, whitelist, out detail) ||
            !QueryBinding.TryBindPage(context.Request.Query, whitelist, out page, out detail) ||
            !QueryBinding.TryBindGuid(context.Request.Query, "tenantId", out Guid? tenantId, out detail))
        {
            return false;
        }

        filter = new ApprovalQueueFilter(Narrowing(tenantId));

        return true;
    }
}

/// <summary>A session and its step trail, as the staff detail view returns them together.</summary>
/// <param name="Session">The session summary.</param>
/// <param name="Steps">The step trail, oldest first.</param>
internal sealed record StaffSessionDetail(SessionSummary Session, IReadOnlyList<SessionStep> Steps);
