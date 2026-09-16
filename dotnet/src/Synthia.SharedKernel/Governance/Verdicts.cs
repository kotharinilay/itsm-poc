namespace Synthia.SharedKernel.Governance;

/// <summary>
/// What a human decided on an approval request.
/// </summary>
/// <remarks>
/// <para>
/// <b>Exactly two members, and that is load-bearing.</b> This is deliberately not the work item's
/// approval state, which also carries <c>pending</c> and <c>expired</c>. Typing a verdict as that
/// wider enum would let an expiry be recorded as a human decision — a system-synthesized verdict,
/// which §17.7 and <c>FR-INTR-008</c> prohibit outright: <i>"No timeout, no auto-reject, no
/// system-synthesized verdict."</i>
/// </para>
/// <para>
/// Expiry is a work-item transition performed by the expiry sweeper. It is never a recorded human
/// decision, and <c>approved_by</c> always means a human approved (§17.8).
/// </para>
/// <para>
/// There is no <c>RejectAndTakeOver</c> member either. §17.6 lists it as a staff <i>action</i>, but
/// it is a rejection plus a session transition to <c>staff_controlled</c> — two things, recorded
/// separately. A third verdict value would make the takeover invisible to anything reading the
/// verdict alone.
/// </para>
/// </remarks>
public enum ApprovalVerdict
{
    /// <summary>Unset. Never valid on a recorded verdict.</summary>
    Unknown = 0,

    /// <summary>
    /// The operation proceeds as proposed, and <c>expires_at</c> is set. No modification of the
    /// operation is possible — the approval binds the exact operation presented.
    /// </summary>
    Approved = 1,

    /// <summary>The operation does not execute. The session escalates.</summary>
    Rejected = 2,
}

/// <summary>An end user's decision on an operation affecting their own account or device.</summary>
/// <remarks>
/// Two members, mirroring the consent verdict in the data model and the two consent trigger kinds.
/// A boolean would collapse this to <c>true</c>/<c>false</c> at every call site, which the
/// constitution prohibits as "a boolean parameter flag that hides behaviour" (Principle VI).
/// </remarks>
public enum ConsentVerdict
{
    /// <summary>Unset. Never valid on a recorded decision.</summary>
    Unknown = 0,

    /// <summary>The requester agreed. Never inferred from an affirmative chat message.</summary>
    Granted = 1,

    /// <summary>The requester refused. The work closes honestly rather than waiting to expire.</summary>
    Refused = 2,
}

/// <summary>
/// The lifecycle of one proposed or executed operation.
/// </summary>
/// <remarks>
/// Distinct from the work item's state: a work item is the durable authority record, an operation
/// is a single action within it.
/// <para>
/// <see cref="Gated"/> and <see cref="Refused"/> are why this type exists rather than being folded
/// into the work item. <see cref="Gated"/> records that deterministic governance evaluated this
/// operation at all, and <see cref="Refused"/> is how a <c>NOT_ALLOWED</c> outcome is recorded — a
/// denial audited as durably as a permission (<c>FR-AUDIT-003</c>).
/// </para>
/// </remarks>
public enum OperationStatus
{
    /// <summary>Unset.</summary>
    Unknown = 0,

    /// <summary>The agent proposed it. A proposal authorizes nothing.</summary>
    Proposed = 1,

    /// <summary>The control gate evaluated it. Treatment came from the catalogue, never the model.</summary>
    Gated = 2,

    /// <summary>Cleared to execute, within its validity window.</summary>
    Authorized = 3,

    /// <summary>Execution completed. See the verification outcome for what the platform knows.</summary>
    Executed = 4,

    /// <summary>
    /// Execution failed. Does not re-fire; requires fresh human authorization
    /// (<c>FR-EXEC-006</c>).
    /// </summary>
    Failed = 5,

    /// <summary>Refused at the gate. Never surfaced to a human as an approvable proposal.</summary>
    Refused = 6,
}

/// <summary>
/// The mechanism by which a consequential action was performed.
/// </summary>
/// <remarks>
/// §28.3 makes <c>executed_by</c> deliberately polymorphic and requires the execution
/// <i>mechanism</i> to be recorded distinctly from the <i>actor</i>: the same Workload principal
/// acting through Graph and through an MCP tool are different facts, and an audit record that
/// conflates them cannot answer "by what means" (§28.4).
/// </remarks>
public enum ExecutionMethod
{
    /// <summary>Unset.</summary>
    Unknown = 0,

    /// <summary>
    /// The Workload principal acted directly, app-only, with its tenant resolved from the work
    /// item.
    /// </summary>
    Workload = 1,

    /// <summary>
    /// The end user's endpoint ran a predefined, versioned, platform-owned script. The endpoint
    /// executes; it never decides. Deferred in this release pending ADR-0004's open items.
    /// </summary>
    DesktopScript = 2,

    /// <summary>
    /// No execution occurred. The operation was refused, expired, or cancelled before claim.
    /// </summary>
    None = 3,
}
