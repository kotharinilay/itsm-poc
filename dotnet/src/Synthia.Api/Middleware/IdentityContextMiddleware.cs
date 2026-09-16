using Synthia.Api.Errors;
using Synthia.Modules.Tenancy;
using Synthia.Observability;
using Synthia.SharedKernel.Identity;

namespace Synthia.Api.Middleware;

/// <summary>
/// Consumes the Gateway-derived header contract and establishes the scope for the request.
/// </summary>
/// <remarks>
/// <para>
/// <b>Identity is derived exactly once, at the Gateway.</b> This service MUST NOT parse an access
/// token and consumes only the five closed headers (constitution Principle I). There is
/// deliberately no code path here that looks at <c>Authorization</c>, and
/// <c>NoTokenParsingTests</c> asserts the string does not appear in the tree.
/// </para>
/// <para>
/// Two things happen, in this order, and neither may be skipped:
/// </para>
/// <list type="number">
///   <item>
///     Any request that supplies tenant, role or audience as a parameter is refused outright. Not
///     ignored — refused. Ignoring it would mean a client could believe it had scoped a request
///     that the server scoped differently.
///   </item>
///   <item>
///     The organisation is established from trusted state: registry admission for an end user,
///     the operator-wide scope for staff. Nothing the caller sent contributes to it.
///   </item>
/// </list>
/// </remarks>
internal sealed class IdentityContextMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<IdentityContextMiddleware> _logger;

    /// <summary>Creates the middleware.</summary>
    /// <param name="next">The next component in the pipeline.</param>
    /// <param name="logger">Structured logger.</param>
    public IdentityContextMiddleware(RequestDelegate next, ILogger<IdentityContextMiddleware> logger)
    {
        ArgumentNullException.ThrowIfNull(next);
        ArgumentNullException.ThrowIfNull(logger);

        _next = next;
        _logger = logger;
    }

    /// <summary>Establishes identity and organisation scope, then runs the rest of the pipeline.</summary>
    /// <param name="context">The request.</param>
    /// <param name="principalScope">The per-request principal holder.</param>
    /// <param name="tenantScope">The per-request organisation-scope holder.</param>
    /// <param name="registry">The organisation registry, for end-user admission.</param>
    /// <returns>A task that completes when the pipeline does.</returns>
    public async Task InvokeAsync(
        HttpContext context,
        IPrincipalScopeWriter principalScope,
        ITenantScopeWriter tenantScope,
        ITenantRegistry registry)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(principalScope);
        ArgumentNullException.ThrowIfNull(tenantScope);
        ArgumentNullException.ThrowIfNull(registry);

        if (!AudienceRouting.TryResolve(context.Request.Path, out Audience audience))
        {
            // Health probes and the OpenAPI document are not an audience and carry no identity.
            // They are also the only unauthenticated surface, which is why the check is a route
            // prefix rather than an allow-list that could grow.
            await _next(context).ConfigureAwait(false);
            return;
        }

        if (ForbiddenParameters.TryFind(context.Request.Query, audience, out string? offending))
        {
            IdentityLog.RefusedAuthorityParameter(_logger, offending);

            await WriteAsync(
                context,
                Problems.ValidationFailed(
                    context,
                    $"The parameter '{offending}' is not accepted. Tenant, role and audience are " +
                    "derived from trusted context and can never be supplied by a caller."))
                .ConfigureAwait(false);
            return;
        }

        if (!PrincipalFactory.TryCreate(
                context.Request.Headers[IdentityHeaders.TenantId].FirstOrDefault(),
                context.Request.Headers[IdentityHeaders.PrincipalId].FirstOrDefault(),
                context.Request.Headers[IdentityHeaders.Roles].FirstOrDefault(),
                context.Request.Headers[IdentityHeaders.CredentialClass].FirstOrDefault(),
                context.Request.Headers[IdentityHeaders.ClientSurface].FirstOrDefault(),
                audience,
                out AuthenticatedPrincipal? principal,
                out IdentityRejection rejection))
        {
            IdentityLog.RefusedIdentity(_logger, rejection.ToString());

            await WriteAsync(
                context,
                Problems.Unauthenticated(context, "The request carried no usable identity context."))
                .ConfigureAwait(false);
            return;
        }

        principalScope.Bind(principal!);

        if (!await TryBindScopeAsync(context, principal!, tenantScope, registry).ConfigureAwait(false))
        {
            return;
        }

        System.Diagnostics.Activity.Current?.SetTag(SynthiaTelemetry.AudienceTag, audience.ToString());

        await _next(context).ConfigureAwait(false);
    }

    private async Task<bool> TryBindScopeAsync(
        HttpContext context,
        AuthenticatedPrincipal principal,
        ITenantScopeWriter tenantScope,
        ITenantRegistry registry)
    {
        if (principal.Audience == Audience.Staff)
        {
            // Staff operate across customer organisations using trusted platform context
            // (spec FR-IDENT-007). The scope comes from the audience the Gateway routed to and the
            // credential class it carried — both already verified by PrincipalFactory — and there
            // is nothing for the caller to supply.
            tenantScope.BindOperatorWide();
            return true;
        }

        TenantAdmissionRecord? admitted = await registry
            .FindAsync(principal.Identity.TenantId, context.RequestAborted)
            .ConfigureAwait(false);

        if (admitted is null)
        {
            // Authenticated against Entra, unknown to this platform. Authentication is not
            // authorization (constitution Principle I), and an unregistered tenant is not admitted.
            IdentityLog.RefusedUnregisteredTenant(_logger);

            await WriteAsync(
                context,
                Problems.Forbidden(context, "This organisation is not registered with the platform."))
                .ConfigureAwait(false);
            return false;
        }

        TenantContext organisation = TenantAdmission.FromAdmittedIdentity(
            admitted.Value.TenantId,
            admitted.Value.EntraTenantId,
            admitted.Value.Status);

        tenantScope.BindOrganisation(organisation);

        System.Diagnostics.Activity.Current?.SetTag(
            SynthiaTelemetry.TenantTag,
            organisation.TenantId.Value);

        return true;
    }

    private static async Task WriteAsync(HttpContext context, IResult problem) =>
        await problem.ExecuteAsync(context).ConfigureAwait(false);
}

/// <summary>Maps a request path onto the audience the Gateway routed it to.</summary>
/// <remarks>
/// <b>The surface decides which authorization model applies</b> (constitution Principle II), and
/// the surface is the route — not a header, not a claim, not a body field. A person cannot promote
/// themselves by anything they supply because there is nothing they can supply that reaches here.
/// </remarks>
internal static class AudienceRouting
{
    /// <summary>The customer audience prefix.</summary>
    public const string CustomerPrefix = "/api/customer/v1";

    /// <summary>The staff audience prefix.</summary>
    public const string StaffPrefix = "/api/staff/v1";

    /// <summary>
    /// The workload audience prefix.
    /// </summary>
    /// <remarks>
    /// Named so the audience is recognisable, not because this deployable serves it. Execution-leg
    /// operations belong to RagCore; no route is mapped under this prefix here, so a request
    /// reaching it is a 404 from routing.
    /// </remarks>
    public const string WorkloadPrefix = "/api/workload/v1";

    /// <summary>Resolves the audience a path belongs to.</summary>
    /// <param name="path">The request path.</param>
    /// <param name="audience">The audience, when the path belongs to one.</param>
    /// <returns><see langword="false"/> for paths outside the API surface.</returns>
    public static bool TryResolve(PathString path, out Audience audience)
    {
        if (path.StartsWithSegments(CustomerPrefix, StringComparison.Ordinal))
        {
            audience = Audience.Customer;
            return true;
        }

        if (path.StartsWithSegments(StaffPrefix, StringComparison.Ordinal))
        {
            audience = Audience.Staff;
            return true;
        }

        if (path.StartsWithSegments(WorkloadPrefix, StringComparison.Ordinal))
        {
            audience = Audience.Workload;
            return true;
        }

        audience = Audience.Unknown;
        return false;
    }
}

/// <summary>
/// Query parameters that would claim authority, and are therefore refused.
/// </summary>
/// <remarks>
/// <b>No endpoint accepts a tenant, role or audience parameter and trusts it</b> (contracts §README
/// rule 1). This refuses them at the edge, before any endpoint can be tempted to read one.
/// </remarks>
internal static class ForbiddenParameters
{
    private static readonly string[] _always =
    [
        "tenant",
        "tenantid",
        "tid",
        "organisation",
        "organization",
        "role",
        "roles",
        "audience",
        "oid",
        "principalid",
    ];

    /// <summary>Finds an authority-claiming parameter in a query string.</summary>
    /// <param name="query">The query string.</param>
    /// <param name="audience">The audience the request was routed to.</param>
    /// <param name="offending">The parameter found, when one was.</param>
    /// <returns><see langword="true"/> when the request must be refused.</returns>
    public static bool TryFind(IQueryCollection query, Audience audience, out string? offending)
    {
        ArgumentNullException.ThrowIfNull(query);

        foreach (string name in query.Keys)
        {
            string normalised = name.ToLowerInvariant();

            // tenantId on the staff audience is the one exception, and it is a narrowing, never a
            // widening: it selects within the set the caller may already see and confers nothing
            // (contracts §README). The global query filter still applies underneath it, so a value
            // outside that set simply returns no rows.
            if (audience == Audience.Staff && string.Equals(normalised, "tenantid", StringComparison.Ordinal))
            {
                continue;
            }

            if (Array.Exists(_always, forbidden => string.Equals(normalised, forbidden, StringComparison.Ordinal)))
            {
                offending = name;
                return true;
            }
        }

        offending = null;
        return false;
    }
}

/// <summary>Log messages for identity handling.</summary>
internal static partial class IdentityLog
{
    /// <summary>Records a refused authority-claiming parameter.</summary>
    /// <param name="logger">The logger.</param>
    /// <param name="parameter">The parameter name. A name, never its value.</param>
    [LoggerMessage(
        EventId = 1101,
        Level = LogLevel.Warning,
        Message = "Refused a request supplying the authority parameter {Parameter}.")]
    public static partial void RefusedAuthorityParameter(ILogger logger, string? parameter);

    /// <summary>
    /// Records a refused identity context.
    /// </summary>
    /// <remarks>
    /// The reason is logged; the header values are not. They are unvalidated input on a path that
    /// reaches a log sink.
    /// </remarks>
    /// <param name="logger">The logger.</param>
    /// <param name="rejection">Why the headers were refused.</param>
    [LoggerMessage(
        EventId = 1102,
        Level = LogLevel.Warning,
        Message = "Refused an identity context: {Rejection}.")]
    public static partial void RefusedIdentity(ILogger logger, string rejection);

    /// <summary>Records a valid identity belonging to an organisation the platform does not know.</summary>
    /// <param name="logger">The logger.</param>
    [LoggerMessage(
        EventId = 1103,
        Level = LogLevel.Warning,
        Message = "Refused a request from an organisation absent from the tenant registry.")]
    public static partial void RefusedUnregisteredTenant(ILogger logger);
}
