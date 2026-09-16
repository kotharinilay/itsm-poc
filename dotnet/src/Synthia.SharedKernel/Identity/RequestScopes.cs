namespace Synthia.SharedKernel.Identity;

/// <summary>
/// How much of the platform the unit of work currently executing may see.
/// </summary>
/// <remarks>
/// Two legitimate shapes, and they are not the same rule wearing different clothes. An end user is
/// confined to their own organisation and their own records (spec FR-IDENT-006). Staff operate
/// <i>across</i> customer organisations using trusted platform context (spec FR-IDENT-007) — which
/// is a wider scope, not an absent one.
/// </remarks>
public enum TenantScopeKind
{
    /// <summary>
    /// Unset. <b>Denies everything.</b> A unit of work that reached a query without an established
    /// scope reads nothing, which is the only safe reading of a wiring mistake.
    /// </summary>
    None = 0,

    /// <summary>One customer organisation, admitted from the end user's own validated tenant.</summary>
    SingleOrganisation = 1,

    /// <summary>
    /// Every customer organisation, for a staff caller on the staff audience.
    /// </summary>
    /// <remarks>
    /// Derived from the audience the Gateway routed to and the credential class it carried, never
    /// from anything the caller supplied. A <c>tenantId</c> query parameter narrows within this
    /// scope and can never widen past it (contracts §README rule 1).
    /// </remarks>
    OperatorWide = 2,
}

/// <summary>
/// The trusted organisation scope for the unit of work currently executing.
/// </summary>
/// <remarks>
/// <para>
/// <b>This interface is what makes "there is no unfiltered query path" structural.</b> Persistence
/// builds a global query filter from it, so a query cannot be written that forgets the
/// organisation — forgetting it is not a thing the API offers. Tenant isolation must not rest on a
/// single chokepoint (constitution Principle IV), so this is one layer of several, not the only
/// one.
/// </para>
/// <para>
/// It lives in the shared kernel rather than in Contracts or Persistence because both sides need
/// it and the drawn dependency graph (plan §Dependency direction) gives them no other common
/// floor. The implementation is infrastructure and lives at the composition root.
/// </para>
/// </remarks>
public interface ITenantScope
{
    /// <summary>How much of the platform is in scope.</summary>
    TenantScopeKind Kind { get; }

    /// <summary>
    /// The organisation in scope, set only when <see cref="Kind"/> is
    /// <see cref="TenantScopeKind.SingleOrganisation"/>.
    /// </summary>
    TenantContext? Organisation { get; }
}

/// <summary>
/// The write half of <see cref="ITenantScope"/>, held only by the code that establishes identity.
/// </summary>
/// <remarks>
/// Split from the read interface deliberately: a read model that could rebind the scope mid-request
/// would defeat the filter it is being filtered by. Only the identity middleware is given this
/// type, and each method names the provenance it is claiming.
/// </remarks>
public interface ITenantScopeWriter : ITenantScope
{
    /// <summary>
    /// Binds one admitted customer organisation.
    /// </summary>
    /// <param name="organisation">
    /// A context built by <see cref="TenantAdmission"/> from the end user's own validated tenant
    /// and registry state — never from a client field.
    /// </param>
    void BindOrganisation(TenantContext organisation);

    /// <summary>
    /// Binds the operator-wide scope for a staff caller.
    /// </summary>
    /// <remarks>
    /// Takes no argument on purpose. There is nothing to supply, so there is nothing a caller could
    /// supply that would widen it.
    /// </remarks>
    void BindOperatorWide();
}

/// <summary>The correlation identifier for the unit of work currently executing.</summary>
/// <remarks>
/// A correlation identifier originates at the public edge and propagates through every tier,
/// appearing on every log record, trace, notification, trigger and audit record (constitution
/// Principle VIII). This is how a component reads it without being handed an <c>HttpContext</c>.
/// </remarks>
public interface ICorrelationScope
{
    /// <summary>The correlation identifier bound to this unit of work.</summary>
    CorrelationId Current { get; }
}

/// <summary>The write half of <see cref="ICorrelationScope"/>.</summary>
public interface ICorrelationScopeWriter : ICorrelationScope
{
    /// <summary>Binds the correlation identifier for this unit of work.</summary>
    /// <param name="correlationId">An accepted or freshly generated identifier.</param>
    void Bind(CorrelationId correlationId);
}

/// <summary>The authenticated principal for the unit of work currently executing.</summary>
public interface IPrincipalScope
{
    /// <summary>The principal, or <see langword="null"/> before identity has been established.</summary>
    AuthenticatedPrincipal? Current { get; }
}

/// <summary>The write half of <see cref="IPrincipalScope"/>.</summary>
public interface IPrincipalScopeWriter : IPrincipalScope
{
    /// <summary>Binds the principal for this unit of work.</summary>
    /// <param name="principal">A principal built by <see cref="PrincipalFactory"/>.</param>
    void Bind(AuthenticatedPrincipal principal);
}
