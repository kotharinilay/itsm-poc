using Synthia.Persistence.Conventions;
using Synthia.SharedKernel.Governance;
using Synthia.SharedKernel.Identity;
using Synthia.SharedKernel.Sessions;
using Synthia.SharedKernel.Work;

namespace Synthia.Persistence.Views;

/// <summary>The published views this deployable is granted <c>SELECT</c> on.</summary>
/// <remarks>
/// <b>Names are the contract</b> (contracts §read-views). A view is never altered in place: a new
/// version is added alongside, this constant list migrates, and the old view is dropped a release
/// later once unreferenced.
/// </remarks>
public static class PublishedViews
{
    /// <summary>The schema RagCore owns and publishes into.</summary>
    public const string Schema = "platform";

    /// <summary>Customer and staff session listings.</summary>
    public const string SessionSummary = "vw_session_summary_v1";

    /// <summary>Conversation history, excluding rows past their content-retention window.</summary>
    public const string SessionMessage = "vw_session_message_v1";

    /// <summary>Step trail. Progress entries only; carries no authority field.</summary>
    public const string SessionStep = "vw_session_step_v1";

    /// <summary>Work state, with authority fields exposed read-only.</summary>
    public const string WorkItem = "vw_work_item_v1";

    /// <summary>Pending approvals, with the fully disclosed command set.</summary>
    public const string ApprovalQueue = "vw_approval_queue_v1";

    /// <summary>Approved but never executed — the dead-letter surface ADR-0002 requires.</summary>
    public const string ApprovalUnexecuted = "vw_approval_unexecuted_v1";

    /// <summary>Audit search. Never exposes credential references.</summary>
    public const string AuditEvent = "vw_audit_event_v1";

    /// <summary>Catalogue browsing, carrying the reference-fixture label.</summary>
    public const string GovernanceCatalogue = "vw_governance_catalogue_v1";

    /// <summary>Organisation registry. Status and identifiers, no secret material.</summary>
    public const string Tenant = "vw_tenant_v1";

    /// <summary>Feedback on a session's messages. Current signal only.</summary>
    public const string MessageFeedback = "vw_message_feedback_v1";

    /// <summary>Pre-aggregated platform counts.</summary>
    public const string DashboardRollup = "vw_dashboard_rollup_v1";

    /// <summary>Every published view this deployable reads.</summary>
    public static IReadOnlyList<string> All { get; } =
    [
        SessionSummary,
        SessionMessage,
        SessionStep,
        WorkItem,
        ApprovalQueue,
        ApprovalUnexecuted,
        AuditEvent,
        GovernanceCatalogue,
        Tenant,
        MessageFeedback,
        DashboardRollup,
    ];
}

/// <summary>A row of <c>vw_session_summary_v1</c>.</summary>
public sealed class SessionSummaryRow : ITenantScopedRow, IAuditedRow
{
    /// <summary>Session identifier.</summary>
    public Guid SessionId { get; init; }

    /// <inheritdoc/>
    public Guid TenantId { get; init; }

    /// <summary>The Entra object identifier of the end user who owns the session.</summary>
    public Guid RequesterOid { get; init; }

    /// <summary>One of the nine session states.</summary>
    public SessionState State { get; init; }

    /// <summary>The system-of-record reference, once the triage gate has fired.</summary>
    public string? CaseReference { get; init; }

    /// <inheritdoc/>
    public DateTimeOffset CreatedAt { get; init; }

    /// <inheritdoc/>
    public DateTimeOffset UpdatedAt { get; init; }

    /// <summary>Set on a terminal transition.</summary>
    public DateTimeOffset? ClosedAt { get; init; }
}

/// <summary>A row of <c>vw_session_message_v1</c>.</summary>
public sealed class SessionMessageRow : ITenantScopedRow
{
    /// <summary>Message identifier.</summary>
    public Guid MessageId { get; init; }

    /// <summary>The owning session.</summary>
    public Guid SessionId { get; init; }

    /// <inheritdoc/>
    public Guid TenantId { get; init; }

    /// <summary>Who authored it.</summary>
    public SenderKind SenderKind { get; init; }

    /// <summary>The author, or <see langword="null"/> for the agent.</summary>
    public Guid? SenderOid { get; init; }

    /// <summary>The message text.</summary>
    public string Body { get; init; } = string.Empty;

    /// <summary>When it was written.</summary>
    public DateTimeOffset CreatedAt { get; init; }
}

/// <summary>A row of <c>vw_session_step_v1</c>.</summary>
public sealed class SessionStepRow : ITenantScopedRow
{
    /// <summary>Step identifier.</summary>
    public Guid StepId { get; init; }

    /// <summary>The owning session.</summary>
    public Guid SessionId { get; init; }

    /// <inheritdoc/>
    public Guid TenantId { get; init; }

    /// <summary>A machine-readable step kind.</summary>
    public string Kind { get; init; } = string.Empty;

    /// <summary>A short, client-safe description.</summary>
    public string Summary { get; init; } = string.Empty;

    /// <summary>When the step was recorded.</summary>
    public DateTimeOffset CreatedAt { get; init; }
}

/// <summary>A row of <c>vw_message_feedback_v1</c>.</summary>
public sealed class MessageFeedbackRow : ITenantScopedRow
{
    /// <summary>The rated message.</summary>
    public Guid MessageId { get; init; }

    /// <summary>The owning session.</summary>
    public Guid SessionId { get; init; }

    /// <inheritdoc/>
    public Guid TenantId { get; init; }

    /// <summary>The current signal. A revision replaces rather than accumulates.</summary>
    public FeedbackSignal Signal { get; init; }

    /// <summary>When it was last revised.</summary>
    public DateTimeOffset UpdatedAt { get; init; }
}

/// <summary>A row of <c>vw_work_item_v1</c>.</summary>
public sealed class WorkItemRow : ITenantScopedRow, IAuditedRow, IVersionedRow
{
    /// <summary>Work item identifier.</summary>
    public Guid WorkItemId { get; init; }

    /// <inheritdoc/>
    public Guid TenantId { get; init; }

    /// <summary>The 1:1 session.</summary>
    public Guid SessionId { get; init; }

    /// <summary>Who asked. An authority field.</summary>
    public Guid RequestedByOid { get; init; }

    /// <summary>The system-of-record reference. An authority field once set.</summary>
    public string? CaseReference { get; init; }

    /// <summary>The catalogue id. An authority field once set.</summary>
    public string? GovernedAction { get; init; }

    /// <summary>Lifecycle state.</summary>
    public WorkItemState State { get; init; }

    /// <summary>Where it stands against its approval requirement.</summary>
    public ApprovalState ApprovalState { get; init; }

    /// <summary>The execution validity window.</summary>
    public DateTimeOffset? ExpiresAt { get; init; }

    /// <summary>Set by the atomic claim.</summary>
    public DateTimeOffset? ClaimedAt { get; init; }

    /// <summary>The executing principal.</summary>
    public string? ClaimedBy { get; init; }

    /// <inheritdoc/>
    public DateTimeOffset CreatedAt { get; init; }

    /// <inheritdoc/>
    public DateTimeOffset UpdatedAt { get; init; }

    /// <inheritdoc/>
    public int Version { get; init; }
}

/// <summary>A row of <c>vw_approval_queue_v1</c>.</summary>
public sealed class ApprovalQueueRow : ITenantScopedRow, IAuditedRow, IVersionedRow
{
    /// <summary>Approval identifier.</summary>
    public Guid ApprovalId { get; init; }

    /// <summary>The case awaiting a verdict.</summary>
    public Guid WorkItemId { get; init; }

    /// <inheritdoc/>
    public Guid TenantId { get; init; }

    /// <summary>The operation being approved.</summary>
    public string CatalogueId { get; init; } = string.Empty;

    /// <summary>The version bound at proposal time.</summary>
    public int CatalogueVersion { get; init; }

    /// <summary>The full command set, as disclosed to the approver.</summary>
    public string? DisclosedCommands { get; init; }

    /// <summary>When approval was sought.</summary>
    public DateTimeOffset RequestedAt { get; init; }

    /// <summary>When the pending request stops being decidable, where one applies.</summary>
    public DateTimeOffset? ExpiresAt { get; init; }

    /// <inheritdoc/>
    public DateTimeOffset CreatedAt { get; init; }

    /// <inheritdoc/>
    public DateTimeOffset UpdatedAt { get; init; }

    /// <inheritdoc/>
    public int Version { get; init; }
}

/// <summary>A row of <c>vw_approval_unexecuted_v1</c>.</summary>
public sealed class ApprovalUnexecutedRow : ITenantScopedRow, IVersionedRow
{
    /// <summary>Approval identifier.</summary>
    public Guid ApprovalId { get; init; }

    /// <summary>The case.</summary>
    public Guid WorkItemId { get; init; }

    /// <inheritdoc/>
    public Guid TenantId { get; init; }

    /// <summary>The operation that was authorized.</summary>
    public string CatalogueId { get; init; } = string.Empty;

    /// <summary>When the verdict was recorded.</summary>
    public DateTimeOffset DecidedAt { get; init; }

    /// <summary>Who decided.</summary>
    public Guid DecidedByOid { get; init; }

    /// <summary>When the fifteen-minute execution window closed.</summary>
    public DateTimeOffset? ExpiresAt { get; init; }

    /// <inheritdoc/>
    public int Version { get; init; }
}

/// <summary>A row of <c>vw_governance_catalogue_v1</c>.</summary>
/// <remarks>
/// Not tenant-scoped: the catalogue is platform-wide, and entitlement — which <i>is</i>
/// tenant-scoped — is a separate concern that no published view exposes, because
/// <c>tenant_entitlement</c> carries credential references.
/// </remarks>
public sealed class GovernanceCatalogueRow
{
    /// <summary>Catalogue identifier.</summary>
    public string CatalogueId { get; init; } = string.Empty;

    /// <summary>Catalogue version. Composite key with the identifier.</summary>
    public int Version { get; init; }

    /// <summary>Whether the entry reads or acts.</summary>
    public CapabilityKind Kind { get; init; }

    /// <summary>The treatment deterministic governance assigns.</summary>
    public ExecutionTreatment DefaultTreatment { get; init; }

    /// <summary>Evaluated by set intersection. Order is meaningless.</summary>
    public IReadOnlyList<string> AcceptedRoles { get; init; } = [];

    /// <summary>True for the inert scaffold fixtures.</summary>
    public bool IsReferenceFixture { get; init; }

    /// <summary>Constrained to false by a database check constraint (ADR-0004).</summary>
    public bool RequiresElevation { get; init; }

    /// <summary>Non-destructive tiers only in the scaffold.</summary>
    public string RiskTier { get; init; } = string.Empty;

    /// <summary>Null means the outcome can only be client-attested.</summary>
    public string? VerificationTool { get; init; }
}

/// <summary>A row of <c>vw_audit_event_v1</c>.</summary>
public sealed class AuditEventRow : ITenantScopedRow
{
    /// <summary>Audit identifier.</summary>
    public Guid AuditId { get; init; }

    /// <inheritdoc/>
    public Guid TenantId { get; init; }

    /// <summary>When it happened. The default sort key for this resource.</summary>
    public DateTimeOffset OccurredAt { get; init; }

    /// <summary>
    /// The case this record concerns, where it concerns one.
    /// </summary>
    /// <remarks>
    /// <b>Present because the contract requires it, and worth saying why.</b>
    /// <c>contracts/README.md</c> whitelists <c>workItemId</c> as a filter on audit search, but
    /// data-model.md's <c>audit_event</c> table lists only the actor chain and does not name the
    /// column. The published view is where the two meet — read-views.md says names are the contract
    /// and shapes are defined by the owning migration — so <c>vw_audit_event_v1</c> must expose it
    /// for the filter to be honourable. Recorded here rather than resolved by quietly dropping the
    /// filter, which would have made an allow-listed field silently ignored.
    /// </remarks>
    public Guid? WorkItemId { get; init; }

    /// <summary>What was done.</summary>
    public string Action { get; init; } = string.Empty;

    /// <summary>Who asked.</summary>
    public Guid? RequestedByOid { get; init; }

    /// <summary>Who approved.</summary>
    public Guid? ApprovedByOid { get; init; }

    /// <summary>Which principal executed it.</summary>
    public string ExecutedBy { get; init; } = string.Empty;

    /// <summary>By what means.</summary>
    public ExecutionMethod ExecutionMethod { get; init; }

    /// <summary>With what result.</summary>
    public string Outcome { get; init; } = string.Empty;

    /// <summary>Server-confirmed, client-attested or contradicted.</summary>
    public VerificationOutcome? Verification { get; init; }

    /// <summary>The identifier tying this to its request and traces.</summary>
    public string CorrelationId { get; init; } = string.Empty;

    /// <summary>Seven years from occurrence by default.</summary>
    public DateTimeOffset RetainUntil { get; init; }
}

/// <summary>A row of <c>vw_tenant_v1</c>.</summary>
/// <remarks>
/// The registry is itself tenant-scoped: an organisation row belongs to that organisation, so the
/// same global filter applies and a staff caller narrows within it rather than widening past it.
/// </remarks>
public sealed class TenantRow : ITenantScopedRow, IAuditedRow, IVersionedRow
{
    /// <inheritdoc/>
    public Guid TenantId { get; init; }

    /// <summary>The validated <c>tid</c> this maps to.</summary>
    public Guid EntraTid { get; init; }

    /// <summary>Display name.</summary>
    public string DisplayName { get; init; } = string.Empty;

    /// <summary>Admission state.</summary>
    public TenantStatus Status { get; init; }

    /// <inheritdoc/>
    public DateTimeOffset CreatedAt { get; init; }

    /// <inheritdoc/>
    public DateTimeOffset UpdatedAt { get; init; }

    /// <inheritdoc/>
    public int Version { get; init; }
}

/// <summary>A row of <c>vw_dashboard_rollup_v1</c>.</summary>
/// <remarks>
/// Pre-aggregated and tenant-stamped. The aggregate-leakage rule is a property of what the view
/// publishes, not of how it is queried, and is asserted by <c>AggregateLeakageTests</c>.
/// </remarks>
public sealed class DashboardRollupRow : ITenantScopedRow
{
    /// <inheritdoc/>
    public Guid TenantId { get; init; }

    /// <summary>Start of the aggregation window.</summary>
    public DateTimeOffset WindowStart { get; init; }

    /// <summary>End of the aggregation window.</summary>
    public DateTimeOffset WindowEnd { get; init; }

    /// <summary>Sessions in the window.</summary>
    public long SessionCount { get; init; }

    /// <summary>Approvals decided in the window.</summary>
    public long ApprovalCount { get; init; }

    /// <summary>Approved-but-unexecuted cases in the window.</summary>
    public long UnexecutedApprovalCount { get; init; }

    /// <summary>Share of agent messages carrying a signal.</summary>
    public double FeedbackRate { get; init; }
}
