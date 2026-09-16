using Synthia.SharedKernel.Identity;
using Synthia.SharedKernel.Sessions;

namespace Synthia.Contracts.ReadModels;

/// <summary>
/// A session as the listings show it. Projected from <c>vw_session_summary_v1</c>.
/// </summary>
/// <remarks>
/// Carries no authority field. The step trail and the summary are progress information; what may
/// be done next is decided by RagCore against the durable work record, never inferred from a read
/// model (contracts §read-views).
/// </remarks>
/// <param name="SessionId">Opaque to clients.</param>
/// <param name="TenantId">The owning organisation. Present on every view, filtered on every query.</param>
/// <param name="State">One of the nine session states.</param>
/// <param name="CaseReference">The system-of-record reference, once the triage gate has fired.</param>
/// <param name="CreatedAt">Audit column.</param>
/// <param name="UpdatedAt">Audit column.</param>
/// <param name="ClosedAt">Set on a terminal transition.</param>
public sealed record SessionSummary(
    Guid SessionId,
    Guid TenantId,
    SessionState State,
    string? CaseReference,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt,
    DateTimeOffset? ClosedAt);

/// <summary>One turn of a conversation. Projected from <c>vw_session_message_v1</c>.</summary>
/// <remarks>
/// The view excludes any row past its content-retention window, so expired chat content cannot be
/// read back through a listing (contracts §read-views rule 4).
/// </remarks>
/// <param name="MessageId">Identifier.</param>
/// <param name="SessionId">The owning session.</param>
/// <param name="TenantId">The owning organisation.</param>
/// <param name="SenderKind">Who authored it.</param>
/// <param name="SenderOid">The author's Entra object id, or <see langword="null"/> for the agent.</param>
/// <param name="Body">The message text.</param>
/// <param name="CreatedAt">Audit column.</param>
public sealed record SessionMessage(
    Guid MessageId,
    Guid SessionId,
    Guid TenantId,
    SenderKind SenderKind,
    Guid? SenderOid,
    string Body,
    DateTimeOffset CreatedAt);

/// <summary>A progress entry in the step trail. Projected from <c>vw_session_step_v1</c>.</summary>
/// <param name="StepId">Identifier.</param>
/// <param name="SessionId">The owning session.</param>
/// <param name="TenantId">The owning organisation.</param>
/// <param name="Kind">A machine-readable step kind, so a client can convey state by more than colour.</param>
/// <param name="Summary">A short, client-safe description.</param>
/// <param name="CreatedAt">Audit column.</param>
public sealed record SessionStep(
    Guid StepId,
    Guid SessionId,
    Guid TenantId,
    string Kind,
    string Summary,
    DateTimeOffset CreatedAt);

/// <summary>The current thumbs signal on a message. Projected from <c>vw_message_feedback_v1</c>.</summary>
/// <remarks>Revised signals replace rather than accumulate, so this is a current value, not a history.</remarks>
/// <param name="MessageId">The rated message.</param>
/// <param name="SessionId">The owning session.</param>
/// <param name="TenantId">The owning organisation.</param>
/// <param name="Signal">The current signal.</param>
/// <param name="UpdatedAt">When it was last revised.</param>
public sealed record MessageFeedback(
    Guid MessageId,
    Guid SessionId,
    Guid TenantId,
    FeedbackSignal Signal,
    DateTimeOffset UpdatedAt);

/// <summary>The typed filter set for the customer session listing.</summary>
/// <remarks>
/// <b>Typed, not an expression language.</b> The filterable set is enumerated in
/// <c>contracts/README.md</c> and an unknown field is a 400, never silently ignored. There is no
/// <c>tenantId</c> member: on a customer resource the organisation is derived and a filter on it
/// would be meaningless.
/// </remarks>
/// <param name="State">Narrow to one session state.</param>
public sealed record SessionListFilter(SessionState? State)
{
    /// <summary>No narrowing.</summary>
    public static SessionListFilter None { get; } = new((SessionState?)null);
}

/// <summary>The typed filter set for a session's message history.</summary>
/// <param name="SenderKind">Narrow to one author kind.</param>
public sealed record SessionMessageFilter(SenderKind? SenderKind)
{
    /// <summary>No narrowing.</summary>
    public static SessionMessageFilter None { get; } = new((SenderKind?)null);
}

/// <summary>The typed filter set for the staff live-session listing.</summary>
/// <remarks>
/// <b><c>tenantId</c> is a staff-only narrowing, never a widening.</b> It selects within the set
/// the caller may already see and establishes no authority (contracts §README rule 1).
/// </remarks>
/// <param name="State">Narrow to one session state.</param>
/// <param name="TenantId">Narrow to one organisation the caller may already see.</param>
public sealed record StaffSessionFilter(SessionState? State, TenantId? TenantId)
{
    /// <summary>No narrowing.</summary>
    public static StaffSessionFilter None { get; } = new(null, null);
}
