namespace Synthia.SharedKernel.Authorization;

/// <summary>
/// Why an authorization attempt was refused. Never surfaced verbatim to a caller — a refusal
/// reason is operational and audit detail, not a client contract.
/// </summary>
public enum DenialReason
{
    /// <summary>The attempt was not refused.</summary>
    None = 0,

    /// <summary>The principal holds no role the operation accepts.</summary>
    EmptyIntersection,

    /// <summary>The operation declares no accepted roles, so it denies everyone.</summary>
    OperationAcceptsNoRoles,

    /// <summary>The principal holds no roles at all.</summary>
    PrincipalHoldsNoRoles,
}

/// <summary>
/// The outcome of one authorization evaluation, carrying the role set held at decision time.
/// </summary>
/// <remarks>
/// The held set is recorded because a decision is evaluated against the roles held <b>at the
/// moment of decision</b>, and a later role change must not retroactively alter it
/// (spec FR-AUTHZ-011).
/// </remarks>
public readonly record struct AuthorizationDecision
{
    private AuthorizationDecision(bool isPermitted, RoleSet rolesHeld, DenialReason reason)
    {
        IsPermitted = isPermitted;
        RolesHeldAtDecision = rolesHeld;
        Reason = reason;
    }

    /// <summary>Whether the operation is permitted.</summary>
    public bool IsPermitted { get; }

    /// <summary>The roles the principal held when this decision was made.</summary>
    public RoleSet RolesHeldAtDecision { get; }

    /// <summary>Why the attempt was refused. <see cref="DenialReason.None"/> when permitted.</summary>
    public DenialReason Reason { get; }

    /// <summary>Records a permitted decision.</summary>
    /// <param name="rolesHeld">The roles held at decision time.</param>
    /// <returns>The decision.</returns>
    public static AuthorizationDecision Permit(RoleSet rolesHeld) =>
        new(true, rolesHeld, DenialReason.None);

    /// <summary>Records a refusal.</summary>
    /// <param name="rolesHeld">The roles held at decision time.</param>
    /// <param name="reason">Why the attempt was refused.</param>
    /// <returns>The decision.</returns>
    public static AuthorizationDecision Deny(RoleSet rolesHeld, DenialReason reason) =>
        new(false, rolesHeld, reason);
}

/// <summary>
/// The platform's only staff authorization primitive: <b>set intersection</b>.
/// </summary>
/// <remarks>
/// <para>
/// <c>principal roles ∩ operation accepted roles ≠ ∅</c>
/// </para>
/// <para>
/// There is no other way to decide a staff operation. No ranking, no precedence, no implied
/// capability. An empty intersection denies, and an operation that accepts no roles denies
/// everyone — the second is not a special case of the first, so both are named explicitly here
/// and tested separately.
/// </para>
/// <para>
/// This is a pure function on purpose. It is not a port and has no infrastructure behind it: it
/// needs no database, no clock and no configuration, so anything that appears to require those to
/// make an authorization decision is doing something else and should be looked at.
/// </para>
/// </remarks>
public static class RoleIntersection
{
    /// <summary>
    /// Decides whether a principal may perform an operation.
    /// </summary>
    /// <param name="principalRoles">The roles the principal holds.</param>
    /// <param name="operationAcceptedRoles">The roles the operation accepts, declared explicitly.</param>
    /// <returns>The decision, carrying the role set held at decision time.</returns>
    public static AuthorizationDecision Evaluate(RoleSet principalRoles, RoleSet operationAcceptedRoles)
    {
        if (operationAcceptedRoles.IsEmpty)
        {
            // An operation that accepts no roles denies everyone. This is a TOTAL denial, never an
            // implicit allow (spec FR-AUTHZ-010) — the failure mode where "no roles configured"
            // silently means "anyone" is the exact thing this branch exists to prevent.
            return AuthorizationDecision.Deny(principalRoles, DenialReason.OperationAcceptsNoRoles);
        }

        if (principalRoles.IsEmpty)
        {
            return AuthorizationDecision.Deny(principalRoles, DenialReason.PrincipalHoldsNoRoles);
        }

        return principalRoles.Intersects(operationAcceptedRoles)
            ? AuthorizationDecision.Permit(principalRoles)
            : AuthorizationDecision.Deny(principalRoles, DenialReason.EmptyIntersection);
    }

    /// <summary>
    /// Convenience overload for an operation declaring its accepted roles inline.
    /// </summary>
    /// <param name="principalRoles">The roles the principal holds.</param>
    /// <param name="operationAcceptedRoles">The roles the operation accepts.</param>
    /// <returns>The decision.</returns>
    public static AuthorizationDecision Evaluate(RoleSet principalRoles, params StaffRole[] operationAcceptedRoles) =>
        Evaluate(principalRoles, RoleSet.Of(operationAcceptedRoles));
}
