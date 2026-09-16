namespace Synthia.SharedKernel.Identity;

/// <summary>Platform admission state for a customer organisation.</summary>
public enum TenantStatus
{
    /// <summary>Unset. Treated as not admitted.</summary>
    Unknown = 0,

    /// <summary>Admitted. Work may execute.</summary>
    Active,

    /// <summary>Temporarily withdrawn. Work does not execute.</summary>
    Suspended,

    /// <summary>Permanently withdrawn. Work does not execute.</summary>
    Offboarded,
}

/// <summary>
/// How a tenant came to be in scope for an operation. Recorded so the provenance of a tenant
/// binding is visible in audit rather than inferred.
/// </summary>
public enum TenantSource
{
    /// <summary>Unset. Never valid on a constructed context.</summary>
    Unknown = 0,

    /// <summary>Derived from the end user's own validated <c>tid</c>, then admitted by the registry.</summary>
    EndUserIdentity,

    /// <summary>Read from the durable work item a staff action or execution targets.</summary>
    WorkItem,

    /// <summary>Read from the durable platform object a staff action operates on.</summary>
    PlatformObject,
}

/// <summary>
/// The trusted tenant binding for one unit of work.
/// </summary>
/// <remarks>
/// <para>
/// <b>Tenant context MUST NEVER be accepted from an untrusted client field</b> (constitution
/// Principle I). There are exactly three legitimate provenances, and they are the three members of
/// <see cref="TenantSource"/>:
/// </para>
/// <list type="bullet">
///   <item>An end user's own <c>tid</c>, admitted against the registry.</item>
///   <item>The work item, for Workload execution — which never carries customer-tenant authority
///   of its own.</item>
///   <item>The platform object a staff action targets — never a value the staff member supplied.</item>
/// </list>
/// <para>
/// <b>There is no public constructor.</b> Instances come only from
/// <see cref="TenantAdmission"/>, whose methods each name their provenance. There is deliberately
/// no <c>FromRequest</c>, no <c>FromHeader</c> and no <c>Parse</c> — if a caller has a tenant
/// identifier from a client and wants a context for it, the API gives them nowhere to go, which is
/// the intended outcome.
/// </para>
/// </remarks>
public sealed class TenantContext
{
    internal TenantContext(TenantId tenantId, EntraTenantId entraTenantId, TenantStatus status, TenantSource source)
    {
        TenantId = tenantId;
        EntraTenantId = entraTenantId;
        Status = status;
        Source = source;
    }

    /// <summary>The platform identifier for the organisation.</summary>
    public TenantId TenantId { get; }

    /// <summary>The Entra tenant identifier the platform identifier maps to.</summary>
    public EntraTenantId EntraTenantId { get; }

    /// <summary>The organisation's admission state at the time this context was built.</summary>
    public TenantStatus Status { get; }

    /// <summary>Where this binding came from.</summary>
    public TenantSource Source { get; }

    /// <summary>
    /// Whether work may execute for this organisation.
    /// </summary>
    /// <remarks>
    /// Approved work MUST NOT execute if the target organisation is no longer active
    /// (spec FR-EXEC-003). Checked at execution rather than only at admission, because a
    /// suspension can land between the two.
    /// </remarks>
    public bool IsAdmitted => Status == TenantStatus.Active;
}

/// <summary>
/// The only way to construct a <see cref="TenantContext"/>.
/// </summary>
/// <remarks>
/// Each method names the provenance it represents, so a reviewer can see at the call site which of
/// the three legitimate sources is being claimed — and so a fourth cannot be added without adding
/// a method here and a member to <see cref="TenantSource"/>.
/// </remarks>
public static class TenantAdmission
{
    /// <summary>
    /// Admits an end user against registry state resolved from their own validated <c>tid</c>.
    /// </summary>
    /// <param name="tenantId">The platform identifier the registry returned.</param>
    /// <param name="entraTenantId">The <c>tid</c> from the validated token.</param>
    /// <param name="status">The admission state the registry holds.</param>
    /// <returns>The trusted context.</returns>
    public static TenantContext FromAdmittedIdentity(
        TenantId tenantId,
        EntraTenantId entraTenantId,
        TenantStatus status) =>
        new(tenantId, entraTenantId, status, TenantSource.EndUserIdentity);

    /// <summary>
    /// Binds the tenant of a durable work item, for Workload execution and resume.
    /// </summary>
    /// <param name="tenantId">The tenant recorded on the work item.</param>
    /// <param name="entraTenantId">The Entra tenant that identifier maps to.</param>
    /// <param name="status">The organisation's current admission state.</param>
    /// <returns>The trusted context.</returns>
    public static TenantContext FromWorkItem(
        TenantId tenantId,
        EntraTenantId entraTenantId,
        TenantStatus status) =>
        new(tenantId, entraTenantId, status, TenantSource.WorkItem);

    /// <summary>
    /// Binds the tenant of the platform object a staff action targets.
    /// </summary>
    /// <remarks>
    /// A staff token's <c>tid</c> is the Operator tenant and is <b>never</b> the customer target.
    /// The target comes from the object being operated on, which is why this method takes a tenant
    /// already read from durable state rather than anything from the request.
    /// </remarks>
    /// <param name="tenantId">The tenant recorded on the targeted object.</param>
    /// <param name="entraTenantId">The Entra tenant that identifier maps to.</param>
    /// <param name="status">The organisation's current admission state.</param>
    /// <returns>The trusted context.</returns>
    public static TenantContext FromPlatformObject(
        TenantId tenantId,
        EntraTenantId entraTenantId,
        TenantStatus status) =>
        new(tenantId, entraTenantId, status, TenantSource.PlatformObject);
}
