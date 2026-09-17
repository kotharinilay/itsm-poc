using Synthia.Api.Authorization;
using Synthia.Api.Contracts;
using Synthia.Api.Errors;
using Synthia.Api.Middleware;
using Synthia.Api.Querying;
using Synthia.Contracts.Errors;
using Synthia.Contracts.Paging;
using Synthia.Contracts.ReadModels;
using Synthia.Modules.Sessions;
using Synthia.SharedKernel.Authorization;
using Synthia.SharedKernel.Identity;
using Synthia.SharedKernel.Sessions;

namespace Synthia.Api.Endpoints;

/// <summary>
/// Customer read models. <b>Every route here is a read.</b>
/// </summary>
/// <remarks>
/// <para>
/// The monolith exposes no state-changing endpoint (contracts §README rule 3, ADR-0001), and
/// <c>NoWriteEndpointTests</c> asserts it by walking the endpoint table rather than trusting this
/// comment.
/// </para>
/// <para>
/// Scoped to the caller's own organisation <b>and their own sessions</b>. A session belonging to
/// another user or organisation returns 404, not 403 — existence is itself tenant-scoped
/// information, and 403 would confirm the resource exists.
/// </para>
/// </remarks>
internal static class CustomerViewEndpoints
{
    /// <summary>Maps the customer read routes.</summary>
    /// <param name="app">The application being built.</param>
    /// <returns>The same application, for chaining.</returns>
    public static WebApplication MapCustomerViewEndpoints(this WebApplication app)
    {
        ArgumentNullException.ThrowIfNull(app);

        // URI-segment versioning. A breaking change adds /v2/; it never mutates /v1/. Plural
        // resource nouns; kebab-case would apply to any multi-word segment, and none of these has
        // one (contracts §README).
        RouteGroupBuilder views = app
            .MapGroup($"{AudienceRouting.CustomerPrefix}/views")
            .WithTags("customer-views");

        views.MapGet("/sessions", ListSessionsAsync)
            .WithName("CustomerListSessions")
            .WithSummary("Lists the caller's own sessions. Cursor paged.")
            .PagedOver(ResourceQueries.CustomerSessions)
            .Returns<CursorEnvelope<SessionSummary>>()
            .AcceptsRolesOfCustomer();

        views.MapGet("/sessions/{sessionId:guid}", GetSessionAsync)
            .WithName("CustomerGetSession")
            .WithSummary("Reads one of the caller's own sessions.")
            .Returns<SessionSummary>()
            .AcceptsRolesOfCustomer();

        views.MapGet("/sessions/{sessionId:guid}/messages", ListMessagesAsync)
            .WithName("CustomerListSessionMessages")
            .WithSummary("Lists a session's conversation history. Cursor paged.")
            .PagedOver(ResourceQueries.CustomerSessionMessages)
            .Returns<CursorEnvelope<SessionMessage>>()
            .AcceptsRolesOfCustomer();

        views.MapGet("/sessions/{sessionId:guid}/steps", ListStepsAsync)
            .WithName("CustomerListSessionSteps")
            .WithSummary("Reads a session's step trail, oldest first.")
            .QueriedOver(ResourceQueries.CustomerSessionSteps)
            .Returns<IReadOnlyList<SessionStep>>()
            .AcceptsRolesOfCustomer();

        views.MapGet("/sessions/{sessionId:guid}/feedback", ListFeedbackAsync)
            .WithName("CustomerListSessionFeedback")
            .WithSummary("Reads the current thumbs signals on a session's agent messages.")
            .QueriedOver(ResourceQueries.CustomerSessionFeedback)
            .Returns<IReadOnlyList<MessageFeedback>>()
            .AcceptsRolesOfCustomer();

        return app;
    }

    /// <summary>
    /// Requires the end-user role, which is the only role this audience has.
    /// </summary>
    /// <remarks>
    /// Every caller here is an end user, including a member of staff. Their staff roles are not
    /// consulted on this surface and confer nothing (spec FR-SURF-008) — which
    /// <c>AuthenticatedPrincipal.AuthorizableRoles</c> enforces structurally rather than leaving to
    /// each endpoint to remember.
    /// </remarks>
    private static RouteHandlerBuilder AcceptsRolesOfCustomer(this RouteHandlerBuilder builder) =>
        builder.AcceptsRoles(StaffRole.EndUser);

    private static async Task<IResult> ListSessionsAsync(
        HttpContext context,
        ICustomerSessionReadModel sessions,
        IPrincipalScope principal,
        CancellationToken cancellationToken)
    {
        if (!QueryBinding.TryRejectUnknownFilters(
                context.Request.Query,
                QueryBinding.WhitelistOf(context),
                out string? detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindPage(
                context.Request.Query,
                QueryBinding.WhitelistOf(context),
                out KeysetRequest? page,
                out detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindEnum(context.Request.Query, "state", out SessionState? state, out detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        KeysetPage<SessionSummary> result = await sessions
            .ListAsync(
                principal.Current!.Identity.PrincipalId,
                new SessionListFilter(state),
                page!,
                cancellationToken)
            .ConfigureAwait(false);

        return Results.Ok(CursorEnvelope.From(result));
    }

    private static async Task<IResult> GetSessionAsync(
        HttpContext context,
        Guid sessionId,
        ICustomerSessionReadModel sessions,
        IPrincipalScope principal,
        CancellationToken cancellationToken)
    {
        SessionSummary? session = await sessions
            .FindAsync(principal.Current!.Identity.PrincipalId, new SessionId(sessionId), cancellationToken)
            .ConfigureAwait(false);

        return session is null ? Problems.NotFound(context) : Results.Ok(session);
    }

    private static async Task<IResult> ListMessagesAsync(
        HttpContext context,
        Guid sessionId,
        ICustomerSessionReadModel sessions,
        IPrincipalScope principal,
        CancellationToken cancellationToken)
    {
        if (!QueryBinding.TryRejectUnknownFilters(
                context.Request.Query,
                QueryBinding.WhitelistOf(context),
                out string? detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindPage(
                context.Request.Query,
                QueryBinding.WhitelistOf(context),
                out KeysetRequest? page,
                out detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindEnum(context.Request.Query, "senderKind", out SenderKind? senderKind, out detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        KeysetPage<SessionMessage> result = await sessions
            .ListMessagesAsync(
                principal.Current!.Identity.PrincipalId,
                new SessionId(sessionId),
                new SessionMessageFilter(senderKind),
                page!,
                cancellationToken)
            .ConfigureAwait(false);

        return Results.Ok(CursorEnvelope.From(result));
    }

    /// <summary>
    /// Reads the current signals on one of the caller's own sessions.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Current signals, not a history.</b> A revision replaces rather than accumulates
    /// (spec FR-SESS-010), so there is one row per rated message and no ordering question about
    /// which of several is in force.
    /// </para>
    /// <para>
    /// Signals are content and expire with the session. The aggregate figures derived from them are
    /// retained independently (spec FR-SESS-012) and are read through
    /// <see cref="IFeedbackReadModel.SummariseAsync"/>, not from here — counting these rows would
    /// tie a reporting figure to a retention window and make engagement look like it fell whenever
    /// retention ran.
    /// </para>
    /// <para>
    /// A session that is not the caller's returns an empty list rather than a 403, for the reason
    /// every read on this surface does: existence is itself tenant-scoped information.
    /// </para>
    /// </remarks>
    private static async Task<IResult> ListFeedbackAsync(
        HttpContext context,
        Guid sessionId,
        IFeedbackReadModel feedback,
        IPrincipalScope principal,
        CancellationToken cancellationToken)
    {
        if (!QueryBinding.TryRejectUnknownFilters(
                context.Request.Query,
                QueryBinding.WhitelistOf(context),
                out string? detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        IReadOnlyList<MessageFeedback> signals = await feedback
            .ListForSessionAsync(principal.Current!.Identity.PrincipalId, new SessionId(sessionId), cancellationToken)
            .ConfigureAwait(false);

        return Results.Ok(signals);
    }

    private static async Task<IResult> ListStepsAsync(
        HttpContext context,
        Guid sessionId,
        ICustomerSessionReadModel sessions,
        IPrincipalScope principal,
        CancellationToken cancellationToken)
    {
        if (!QueryBinding.TryRejectUnknownFilters(
                context.Request.Query,
                QueryBinding.WhitelistOf(context),
                out string? detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        IReadOnlyList<SessionStep> steps = await sessions
            .ListStepsAsync(principal.Current!.Identity.PrincipalId, new SessionId(sessionId), cancellationToken)
            .ConfigureAwait(false);

        return Results.Ok(steps);
    }
}
