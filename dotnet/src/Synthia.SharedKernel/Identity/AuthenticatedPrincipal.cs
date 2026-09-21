using Synthia.SharedKernel.Authorization;

namespace Synthia.SharedKernel.Identity;

/// <summary>Whether a request arrived on a delegated (human) or app-only (workload) credential.</summary>
public enum CredentialClass
{
    /// <summary>Unset. A service refuses a request whose class it cannot determine.</summary>
    Unknown = 0,

    /// <summary>A human principal acting through a client surface.</summary>
    Delegated,

    /// <summary>The non-human execution principal: managed identity, app-only token.</summary>
    App,
}

/// <summary>The resource audience a request was addressed to.</summary>
/// <remarks>
/// <b>The surface decides which authorization model applies</b>, and a person cannot promote
/// themselves by anything they supply (spec FR-SURF-005). This value comes from the route the
/// Gateway matched, never from a request field.
/// </remarks>
public enum Audience
{
    /// <summary>Unset.</summary>
    Unknown = 0,

    /// <summary>Customer audience. Every caller is an end user, staff included.</summary>
    Customer,

    /// <summary>Staff audience. Reachable only from the staff portal.</summary>
    Staff,

    /// <summary>Workload audience. App-only execution operations.</summary>
    Workload,
}

/// <summary>
/// Human identity: <c>(tid, oid)</c>, and nothing else.
/// </summary>
/// <param name="TenantId">The Entra tenant of the principal.</param>
/// <param name="PrincipalId">The Entra object identifier of the principal.</param>
public readonly record struct HumanIdentity(EntraTenantId TenantId, PrincipalId PrincipalId);

/// <summary>
/// The principal for one request, derived exactly once at the Gateway.
/// </summary>
/// <remarks>
/// <para>
/// Services MUST NOT parse an access token and consume only the closed Gateway-derived header
/// contract (A1 §4.5). This type is the in-process shape of that contract.
/// </para>
/// <para>
/// <b>There is deliberately no public constructor and no setter.</b> An instance can only come from
/// <see cref="PrincipalFactory"/>, which is the single place the header contract is turned into a
/// principal. A handler cannot construct one with the roles it would like to have.
/// </para>
/// </remarks>
public sealed class AuthenticatedPrincipal
{
    internal AuthenticatedPrincipal(
        HumanIdentity identity,
        RoleSet roles,
        CredentialClass credentialClass,
        Audience audience,
        string clientSurface)
    {
        Identity = identity;
        Roles = roles;
        CredentialClass = credentialClass;
        Audience = audience;
        ClientSurface = clientSurface;
    }

    /// <summary>The <c>(tid, oid)</c> pair from the validated token.</summary>
    public HumanIdentity Identity { get; }

    /// <summary>
    /// The complete role set the Gateway emitted.
    /// </summary>
    /// <remarks>
    /// Collapsing this to a single value destroys authority: a principal holding
    /// <c>{technician, administrator}</c> arriving as <c>administrator</c> alone has silently lost
    /// the capability that lets them approve.
    /// </remarks>
    public RoleSet Roles { get; }

    /// <summary>Whether this is a delegated or app-only credential.</summary>
    public CredentialClass CredentialClass { get; }

    /// <summary>The audience the request was addressed to.</summary>
    public Audience Audience { get; }

    /// <summary>The client application identifier. Attribution only; never tenant authority.</summary>
    public string ClientSurface { get; }

    /// <summary>
    /// The roles that may be consulted for an authorization decision on this request.
    /// </summary>
    /// <remarks>
    /// <b>This is where the surface rule becomes structural rather than remembered.</b> Any person
    /// acting on a customer surface is an end user — including staff — and their staff roles MUST
    /// NOT be consulted there (A1 §6). Rather than trusting every call site to
    /// remember that, the customer audience returns a set that simply does not contain them.
    /// </remarks>
    public RoleSet AuthorizableRoles =>
        Audience == Audience.Customer ? RoleSet.Of(StaffRole.EndUser) : Roles;
}
