using Synthia.SharedKernel.Authorization;

namespace Synthia.SharedKernel.Identity;

/// <summary>The closed Gateway-derived header contract (specification §11.5).</summary>
/// <remarks>
/// Services do not invent alternative identity headers and do not parse the token to create a
/// second identity decision. These five names are the whole contract.
/// </remarks>
public static class IdentityHeaders
{
    /// <summary>Entra tenant of the current principal.</summary>
    public const string TenantId = "X-Idp-Tenant-Id";

    /// <summary>Entra object identifier of the current principal.</summary>
    public const string PrincipalId = "X-Idp-Principal-Id";

    /// <summary>The complete role set, in canonical order.</summary>
    public const string Roles = "X-Idp-Roles";

    /// <summary><c>delegated</c> or <c>app</c>.</summary>
    public const string CredentialClass = "X-Idp-Credential-Class";

    /// <summary>Client application identifier. Attribution only.</summary>
    public const string ClientSurface = "X-Idp-Client-Surface";
}

/// <summary>Why a set of identity headers was refused.</summary>
public enum IdentityRejection
{
    /// <summary>Not refused.</summary>
    None = 0,

    /// <summary>A required header was absent or empty.</summary>
    MissingHeader,

    /// <summary>A header was present but not well formed.</summary>
    MalformedHeader,

    /// <summary>The role header was absent, unordered, duplicated, or outside the canonical set.</summary>
    InvalidRoleSet,

    /// <summary>A sentinel role was combined with a staff role.</summary>
    SentinelCombinedWithRole,

    /// <summary>The credential class does not match the audience.</summary>
    CredentialClassNotAcceptedHere,
}

/// <summary>
/// Turns the Gateway-derived header contract into an <see cref="AuthenticatedPrincipal"/>.
/// </summary>
/// <remarks>
/// <b>The single place a principal comes into existence.</b> Identity is derived exactly once, at
/// the Gateway; this is where a service consumes that derivation, and it is deliberately the only
/// type that can construct <see cref="AuthenticatedPrincipal"/>.
/// </remarks>
public static class PrincipalFactory
{
    /// <summary>
    /// Attempts to build a principal from the closed header contract.
    /// </summary>
    /// <remarks>
    /// Fails closed on every ambiguity. Canonical ordering is a security property, not tidiness:
    /// it makes "token array order never decides anything" checkable at the boundary rather than
    /// trusted.
    /// </remarks>
    /// <param name="tenantId">The <c>X-Idp-Tenant-Id</c> value.</param>
    /// <param name="principalId">The <c>X-Idp-Principal-Id</c> value.</param>
    /// <param name="roles">The <c>X-Idp-Roles</c> value.</param>
    /// <param name="credentialClass">The <c>X-Idp-Credential-Class</c> value.</param>
    /// <param name="clientSurface">The <c>X-Idp-Client-Surface</c> value.</param>
    /// <param name="audience">The audience the Gateway routed to.</param>
    /// <param name="principal">The constructed principal, when accepted.</param>
    /// <param name="rejection">Why the headers were refused, when not accepted.</param>
    /// <returns><see langword="true"/> when a principal was constructed.</returns>
    public static bool TryCreate(
        string? tenantId,
        string? principalId,
        string? roles,
        string? credentialClass,
        string? clientSurface,
        Audience audience,
        out AuthenticatedPrincipal? principal,
        out IdentityRejection rejection)
    {
        principal = null;

        if (!Guid.TryParse(tenantId, out Guid tid) || !Guid.TryParse(principalId, out Guid oid))
        {
            rejection = string.IsNullOrWhiteSpace(tenantId) || string.IsNullOrWhiteSpace(principalId)
                ? IdentityRejection.MissingHeader
                : IdentityRejection.MalformedHeader;
            return false;
        }

        CredentialClass credential = credentialClass switch
        {
            "delegated" => Identity.CredentialClass.Delegated,
            "app" => Identity.CredentialClass.App,
            _ => Identity.CredentialClass.Unknown,
        };

        if (credential == Identity.CredentialClass.Unknown)
        {
            rejection = string.IsNullOrWhiteSpace(credentialClass)
                ? IdentityRejection.MissingHeader
                : IdentityRejection.MalformedHeader;
            return false;
        }

        if (!TryParseRoles(roles, out RoleSet roleSet, out rejection))
        {
            return false;
        }

        // The Workload audience is app-only; the customer and staff audiences are delegated.
        // A mismatch is an invalid identity context, not something to reconcile.
        bool classMatchesAudience = audience switch
        {
            Audience.Workload => credential == Identity.CredentialClass.App,
            Audience.Customer or Audience.Staff => credential == Identity.CredentialClass.Delegated,
            _ => false,
        };

        if (!classMatchesAudience)
        {
            rejection = IdentityRejection.CredentialClassNotAcceptedHere;
            return false;
        }

        principal = new AuthenticatedPrincipal(
            new HumanIdentity(new EntraTenantId(tid), new PrincipalId(oid)),
            roleSet,
            credential,
            audience,
            clientSurface ?? string.Empty);

        rejection = IdentityRejection.None;
        return true;
    }

    private static bool TryParseRoles(string? header, out RoleSet roles, out IdentityRejection rejection)
    {
        roles = RoleSet.Empty;

        if (string.IsNullOrWhiteSpace(header))
        {
            rejection = IdentityRejection.MissingHeader;
            return false;
        }

        string[] parts = header.Split(',', StringSplitOptions.None);
        List<StaffRole> parsed = new(parts.Length);

        foreach (string part in parts)
        {
            // No trimming: a whitespace-padded value is refused rather than repaired. Repairing it
            // would widen the set of accepted spellings beyond the set that was reviewed.
            if (!StaffRole.TryParse(part, out StaffRole role))
            {
                rejection = IdentityRejection.InvalidRoleSet;
                return false;
            }

            if (parsed.Contains(role))
            {
                rejection = IdentityRejection.InvalidRoleSet;
                return false;
            }

            parsed.Add(role);
        }

        // Canonical order: ascending ordinal. Checked, not assumed.
        for (int i = 1; i < parsed.Count; i++)
        {
            if (string.CompareOrdinal(parsed[i - 1].Name, parsed[i].Name) >= 0)
            {
                rejection = IdentityRejection.InvalidRoleSet;
                return false;
            }
        }

        // `end_user` and `none` are single-member sets and never combine with anything.
        bool hasSentinel = parsed.Contains(StaffRole.EndUser) || parsed.Contains(StaffRole.None);
        if (hasSentinel && parsed.Count > 1)
        {
            rejection = IdentityRejection.SentinelCombinedWithRole;
            return false;
        }

        roles = RoleSet.From(parsed);
        rejection = IdentityRejection.None;
        return true;
    }
}
