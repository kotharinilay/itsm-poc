using Synthia.Api.Errors;
using Synthia.SharedKernel.Authorization;
using Synthia.SharedKernel.Identity;

namespace Synthia.Api.Authorization;

/// <summary>
/// Authorizes an endpoint by set intersection against the roles it accepts.
/// </summary>
/// <remarks>
/// <para>
/// <b>Authorization is set intersection</b>: <c>principal roles ∩ operation accepted roles ≠ ∅</c>.
/// An empty intersection denies, and an operation that accepts no roles denies everyone
/// (A1 §6). Any implementation that sorts, ranks, compares or upgrades roles
/// is a defect — so this one does none of those, and delegates the decision to
/// <see cref="RoleIntersection"/> rather than re-deciding it here.
/// </para>
/// <para>
/// The roles consulted are <see cref="AuthenticatedPrincipal.AuthorizableRoles"/>, not the raw set.
/// On the customer audience that returns <c>{end_user}</c> whoever the caller is, which is what
/// makes "any person acting on a customer surface is an end user, including staff" structural
/// rather than remembered.
/// </para>
/// </remarks>
internal sealed class RoleFilter : IEndpointFilter
{
    private readonly RoleSet _accepted;

    /// <summary>Declares the roles an endpoint accepts.</summary>
    /// <param name="accepted">The accepted set. Explicit, and never inferred from a hierarchy.</param>
    public RoleFilter(RoleSet accepted)
    {
        _accepted = accepted;
    }

    /// <inheritdoc/>
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(next);

        // Resolved from the request's own services rather than constructor-injected. An endpoint
        // filter is a singleton created when routes are mapped, and IPrincipalScope is scoped to a
        // request — so there is no constructor for it to arrive through.
        //
        // This is NOT the Service Locator .claude/rules/10-principles.md P-26 prohibits. That rule is about a business
        // service hiding its dependencies behind a provider; this is the framework's own per-request
        // accessor, used in the one layer whose signature the framework fixes.
        // ServiceResolutionTests asserts the exception stays confined here.
        IPrincipalScope scope = context.HttpContext.RequestServices.GetRequiredService<IPrincipalScope>();
        AuthenticatedPrincipal? principal = scope.Current;

        if (principal is null)
        {
            return Problems.Unauthenticated(
                context.HttpContext,
                "The request carried no usable identity context.");
        }

        AuthorizationDecision decision = RoleIntersection.Evaluate(principal.AuthorizableRoles, _accepted);

        if (!decision.IsPermitted)
        {
            // 403, not 404. The resource is a collection whose existence is not itself tenant-scoped
            // information — a staff member without the role knows the approval queue exists. The
            // 404 rule applies to a specific resource belonging to someone else (contracts §README).
            return Problems.Forbidden(
                context.HttpContext,
                "This operation is not available to the roles held.");
        }

        return await next(context).ConfigureAwait(false);
    }
}

/// <summary>Declares the roles an endpoint accepts.</summary>
internal static class RoleFilterExtensions
{
    /// <summary>
    /// Requires a non-empty intersection with the given roles.
    /// </summary>
    /// <remarks>
    /// Every operation declares its accepted set explicitly. There is no default and no inherited
    /// set, because a route that forgot to declare one would otherwise accept everybody.
    /// </remarks>
    /// <param name="builder">The route being built.</param>
    /// <param name="accepted">The roles this operation accepts.</param>
    /// <returns>The same builder, for chaining.</returns>
    public static RouteHandlerBuilder AcceptsRoles(this RouteHandlerBuilder builder, params StaffRole[] accepted)
    {
        ArgumentNullException.ThrowIfNull(builder);
        ArgumentNullException.ThrowIfNull(accepted);

        RoleSet set = RoleSet.Of(accepted);

        return builder.AddEndpointFilter(new RoleFilter(set));
    }
}
