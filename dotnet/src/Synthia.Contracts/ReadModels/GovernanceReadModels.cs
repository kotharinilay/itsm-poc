using Synthia.SharedKernel.Governance;
using Synthia.SharedKernel.Identity;
using Synthia.SharedKernel.Work;

namespace Synthia.Contracts.ReadModels;

/// <summary>Work state as the staff surfaces show it. Projected from <c>vw_work_item_v1</c>.</summary>
/// <remarks>
/// <b>Authority fields are exposed read-only.</b> They are immutable at the database permission
/// boundary, not by application convention (spec FR-EXEC-008), and nothing in this deployable can
/// write them — it holds <c>SELECT</c> on published views and nothing else.
/// </remarks>
/// <param name="WorkItemId">Identifier.</param>
/// <param name="TenantId">The owning organisation. An authority field.</param>
/// <param name="SessionId">The 1:1 session.</param>
/// <param name="RequestedByOid">Who asked. An authority field.</param>
/// <param name="CaseReference">The system-of-record reference. An authority field once set.</param>
/// <param name="GovernedAction">The catalogue id. An authority field once set.</param>
/// <param name="State">Lifecycle state.</param>
/// <param name="ApprovalState">Where it stands against its approval requirement.</param>
/// <param name="ExpiresAt">The execution validity window, set on authorization.</param>
/// <param name="ClaimedAt">Set by the atomic claim.</param>
/// <param name="ClaimedBy">The executing principal.</param>
/// <param name="CreatedAt">Audit column.</param>
/// <param name="UpdatedAt">Audit column.</param>
/// <param name="Version">Optimistic-concurrency token.</param>
public sealed record WorkItemView(
    Guid WorkItemId,
    Guid TenantId,
    Guid SessionId,
    Guid RequestedByOid,
    string? CaseReference,
    string? GovernedAction,
    WorkItemState State,
    ApprovalState ApprovalState,
    DateTimeOffset? ExpiresAt,
    DateTimeOffset? ClaimedAt,
    string? ClaimedBy,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt,
    int Version);

/// <summary>A pending approval. Projected from <c>vw_approval_queue_v1</c>.</summary>
/// <remarks>
/// Carries the <b>fully disclosed</b> command set: a decision made against a summary is not an
/// informed decision. A pending approval may suspend indefinitely.
/// </remarks>
/// <param name="ApprovalId">Identifier.</param>
/// <param name="WorkItemId">The case awaiting a verdict. At most one approval per case.</param>
/// <param name="TenantId">The owning organisation.</param>
/// <param name="CatalogueId">The operation being approved.</param>
/// <param name="CatalogueVersion">The version bound at proposal time.</param>
/// <param name="DisclosedCommands">The full command set, as disclosed to the approver.</param>
/// <param name="RequestedAt">When approval was sought.</param>
/// <param name="ExpiresAt">When the pending request stops being decidable, where one applies.</param>
/// <param name="CreatedAt">Audit column.</param>
/// <param name="UpdatedAt">Audit column.</param>
/// <param name="Version">Optimistic-concurrency token.</param>
public sealed record ApprovalQueueEntry(
    Guid ApprovalId,
    Guid WorkItemId,
    Guid TenantId,
    string CatalogueId,
    int CatalogueVersion,
    string? DisclosedCommands,
    DateTimeOffset RequestedAt,
    DateTimeOffset? ExpiresAt,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt,
    int Version);

/// <summary>
/// Work that was approved and never executed. Projected from <c>vw_approval_unexecuted_v1</c>.
/// </summary>
/// <remarks>
/// <b>The dead-letter surface ADR-0002 requires.</b> Approved-but-unexecuted work MUST surface to
/// humans rather than expiring silently, and it recovers only through fresh authorization — never
/// by re-firing.
/// </remarks>
/// <param name="ApprovalId">Identifier.</param>
/// <param name="WorkItemId">The case.</param>
/// <param name="TenantId">The owning organisation.</param>
/// <param name="CatalogueId">The operation that was authorized.</param>
/// <param name="DecidedAt">When the verdict was recorded.</param>
/// <param name="DecidedByOid">Who decided.</param>
/// <param name="ExpiresAt">When the fifteen-minute execution window closed.</param>
/// <param name="Version">Optimistic-concurrency token.</param>
public sealed record UnexecutedApproval(
    Guid ApprovalId,
    Guid WorkItemId,
    Guid TenantId,
    string CatalogueId,
    DateTimeOffset DecidedAt,
    Guid DecidedByOid,
    DateTimeOffset? ExpiresAt,
    int Version);

/// <summary>A catalogue entry. Projected from <c>vw_governance_catalogue_v1</c>.</summary>
/// <remarks>
/// Carries <see cref="IsReferenceFixture"/> so fixtures are <b>visibly labelled</b>. A reference
/// fixture is never product and MUST NEVER be counted as one of the twelve use cases
/// (constitution Principle IX).
/// </remarks>
/// <param name="CatalogueId">Catalogue identifier.</param>
/// <param name="Version">Catalogue version. Composite key with the identifier.</param>
/// <param name="Kind">Whether the entry reads or acts.</param>
/// <param name="DefaultTreatment">The treatment deterministic governance assigns.</param>
/// <param name="AcceptedRoles">Evaluated by set intersection. Order is meaningless.</param>
/// <param name="IsReferenceFixture">True for the inert scaffold fixtures.</param>
/// <param name="RequiresElevation">Constrained to false by a database check constraint (ADR-0004).</param>
/// <param name="RiskTier">Non-destructive tiers only in the scaffold.</param>
/// <param name="VerificationTool">Null means the outcome can only be client-attested.</param>
public sealed record GovernanceCatalogueEntry(
    string CatalogueId,
    int Version,
    CapabilityKind Kind,
    ExecutionTreatment DefaultTreatment,
    IReadOnlyList<string> AcceptedRoles,
    bool IsReferenceFixture,
    bool RequiresElevation,
    string RiskTier,
    string? VerificationTool);

/// <summary>An audit record. Projected from <c>vw_audit_event_v1</c>.</summary>
/// <remarks>
/// <b>Never exposes credential references</b> — not values, not Key Vault references. Audit is
/// distinct from telemetry, with separate stores and separate retention, and telemetry MUST NEVER
/// answer an audit question (constitution Principle VIII).
/// </remarks>
/// <param name="AuditId">Identifier.</param>
/// <param name="TenantId">The organisation acted against.</param>
/// <param name="OccurredAt">When it happened. The default sort key for this resource.</param>
/// <param name="WorkItemId">The case this record concerns, where it concerns one.</param>
/// <param name="Action">What was done.</param>
/// <param name="RequestedByOid">Who asked.</param>
/// <param name="ApprovedByOid">Who approved.</param>
/// <param name="ExecutedBy">Which principal executed it.</param>
/// <param name="ExecutionMethod">By what means.</param>
/// <param name="Outcome">With what result.</param>
/// <param name="Verification">Server-confirmed, client-attested or contradicted.</param>
/// <param name="CorrelationId">The identifier tying this to its request and traces.</param>
/// <param name="RetainUntil">Seven years from occurrence by default.</param>
public sealed record AuditEventView(
    Guid AuditId,
    Guid TenantId,
    DateTimeOffset OccurredAt,
    Guid? WorkItemId,
    string Action,
    Guid? RequestedByOid,
    Guid? ApprovedByOid,
    string ExecutedBy,
    ExecutionMethod ExecutionMethod,
    string Outcome,
    VerificationOutcome? Verification,
    string CorrelationId,
    DateTimeOffset RetainUntil);

/// <summary>An organisation in the registry. Projected from <c>vw_tenant_v1</c>.</summary>
/// <remarks>Status and identifiers only — <b>no secret material</b> (contracts §read-views rule 2).</remarks>
/// <param name="TenantId">Platform identifier.</param>
/// <param name="EntraTenantId">The validated <c>tid</c> this maps to.</param>
/// <param name="DisplayName">Display name.</param>
/// <param name="Status">Admission state. Work does not execute unless active.</param>
/// <param name="CreatedAt">Audit column.</param>
/// <param name="UpdatedAt">Audit column.</param>
/// <param name="Version">Optimistic-concurrency token.</param>
public sealed record TenantView(
    Guid TenantId,
    Guid EntraTenantId,
    string DisplayName,
    TenantStatus Status,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt,
    int Version);

/// <summary>
/// Pre-aggregated platform counts. Projected from <c>vw_dashboard_rollup_v1</c>.
/// </summary>
/// <remarks>
/// <b>Aggregated and derived figures MUST NOT reveal any single organisation's contribution</b>
/// (constitution Principle IV). The rollup is derived and retained independently of the signals it
/// was computed from, so expiring chat content does not erase reporting history.
/// </remarks>
/// <param name="WindowStart">Start of the aggregation window.</param>
/// <param name="WindowEnd">End of the aggregation window.</param>
/// <param name="SessionCount">Sessions in the window.</param>
/// <param name="ApprovalCount">Approvals decided in the window.</param>
/// <param name="UnexecutedApprovalCount">Approved-but-unexecuted cases in the window.</param>
/// <param name="FeedbackRate">Share of agent messages carrying a signal.</param>
public sealed record DashboardRollup(
    DateTimeOffset WindowStart,
    DateTimeOffset WindowEnd,
    long SessionCount,
    long ApprovalCount,
    long UnexecutedApprovalCount,
    double FeedbackRate);

/// <summary>The typed filter set for the staff approval queue.</summary>
/// <param name="TenantId">A staff-only narrowing within what the caller may already see.</param>
public sealed record ApprovalQueueFilter(TenantId? TenantId)
{
    /// <summary>No narrowing.</summary>
    public static ApprovalQueueFilter None { get; } = new((TenantId?)null);
}

/// <summary>The typed filter set for audit search.</summary>
/// <param name="TenantId">A staff-only narrowing.</param>
/// <param name="WorkItemId">Narrow to one case.</param>
/// <param name="EventKind">Narrow to one action.</param>
/// <param name="OccurredFrom">Inclusive lower bound on occurrence.</param>
/// <param name="OccurredTo">Exclusive upper bound on occurrence.</param>
public sealed record AuditFilter(
    TenantId? TenantId,
    WorkItemId? WorkItemId,
    string? EventKind,
    DateTimeOffset? OccurredFrom,
    DateTimeOffset? OccurredTo)
{
    /// <summary>No narrowing.</summary>
    public static AuditFilter None { get; } = new(null, null, null, null, null);
}

/// <summary>The typed filter set for the organisation registry.</summary>
/// <param name="Status">Narrow to one admission state.</param>
public sealed record TenantRegistryFilter(TenantStatus? Status)
{
    /// <summary>No narrowing.</summary>
    public static TenantRegistryFilter None { get; } = new((TenantStatus?)null);
}
