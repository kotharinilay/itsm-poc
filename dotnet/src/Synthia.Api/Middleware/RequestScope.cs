using Synthia.SharedKernel.Identity;

namespace Synthia.Api.Middleware;

/// <summary>
/// The per-request holder for identity, organisation scope and correlation.
/// </summary>
/// <remarks>
/// <para>
/// One object, registered once and resolved through six interfaces — three read halves and three
/// write halves. The split is the point: a read model receives <see cref="ITenantScope"/> and
/// cannot widen it, while only the identity middleware is handed
/// <see cref="ITenantScopeWriter"/>. Interface segregation here is a security control, not a
/// style preference (constitution Principle VI).
/// </para>
/// <para>
/// <b>Each value can be bound once.</b> A second bind throws rather than overwriting: within one
/// request, identity is derived exactly once, and code that rebinds it is either confused or
/// attacking.
/// </para>
/// </remarks>
internal sealed class RequestScope :
    ITenantScope,
    ITenantScopeWriter,
    IPrincipalScope,
    IPrincipalScopeWriter,
    ICorrelationScope,
    ICorrelationScopeWriter
{
    private bool _tenantBound;
    private bool _principalBound;
    private bool _correlationBound;

    public TenantScopeKind Kind { get; private set; } = TenantScopeKind.None;

    public TenantContext? Organisation { get; private set; }

    public AuthenticatedPrincipal? Current { get; private set; }

    CorrelationId ICorrelationScope.Current => CorrelationId;

    public CorrelationId CorrelationId { get; private set; }

    public void BindOrganisation(TenantContext organisation)
    {
        ArgumentNullException.ThrowIfNull(organisation);

        RefuseRebind(_tenantBound, "organisation scope");

        Organisation = organisation;
        Kind = TenantScopeKind.SingleOrganisation;
        _tenantBound = true;
    }

    public void BindOperatorWide()
    {
        RefuseRebind(_tenantBound, "organisation scope");

        Organisation = null;
        Kind = TenantScopeKind.OperatorWide;
        _tenantBound = true;
    }

    public void Bind(AuthenticatedPrincipal principal)
    {
        ArgumentNullException.ThrowIfNull(principal);

        RefuseRebind(_principalBound, "principal");

        Current = principal;
        _principalBound = true;
    }

    public void Bind(CorrelationId correlationId)
    {
        RefuseRebind(_correlationBound, "correlation identifier");

        CorrelationId = correlationId;
        _correlationBound = true;
    }

    private static void RefuseRebind(bool alreadyBound, string what)
    {
        if (alreadyBound)
        {
            throw new InvalidOperationException(
                $"The {what} for this request is already bound. Identity is derived exactly once " +
                "(constitution Principle I); rebinding it mid-request would mean two answers to " +
                "the same question, and the second one winning.");
        }
    }
}
