using Synthia.Api.Authorization;
using Synthia.Api.Errors;
using Synthia.Api.Middleware;
using Synthia.Api.Querying;
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
            .AcceptsRolesOfCustomer();

        views.MapGet("/sessions/{sessionId:guid}", GetSessionAsync)
            .WithName("CustomerGetSession")
            .WithSummary("Reads one of the caller's own sessions.")
            .AcceptsRolesOfCustomer();

        views.MapGet("/sessions/{sessionId:guid}/messages", ListMessagesAsync)
            .WithName("CustomerListSessionMessages")
            .WithSummary("Lists a session's conversation history. Cursor paged.")
            .AcceptsRolesOfCustomer();

        views.MapGet("/sessions/{sessionId:guid}/steps", ListStepsAsync)
            .WithName("CustomerListSessionSteps")
            .WithSummary("Reads a session's step trail, oldest first.")
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
                ResourceQueries.CustomerSessions,
                out string? detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindPage(
                context.Request.Query,
                ResourceQueries.CustomerSessions,
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
                ResourceQueries.CustomerSessionMessages,
                out string? detail))
        {
            return Problems.ValidationFailed(context, detail!);
        }

        if (!QueryBinding.TryBindPage(
                context.Request.Query,
                ResourceQueries.CustomerSessionMessages,
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

    private static async Task<IResult> ListStepsAsync(
        HttpContext context,
        Guid sessionId,
        ICustomerSessionReadModel sessions,
        IPrincipalScope principal,
        CancellationToken cancellationToken)
    {
        if (!QueryBinding.TryRejectUnknownFilters(
                context.Request.Query,
                ResourceQueries.CustomerSessionSteps,
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
