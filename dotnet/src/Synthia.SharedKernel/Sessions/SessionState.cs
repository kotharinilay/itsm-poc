namespace Synthia.SharedKernel.Sessions;

/// <summary>
/// The nine states a conversation can hold (spec FR-SESS-015).
/// </summary>
/// <remarks>
/// <b>Nine, not four.</b> The three <c>Awaiting*</c> states persist indefinitely — losing the
/// realtime connection changes nothing, because the connection is a notification leaf and never a
/// link on a consequential path (A3 §6.3).
/// </remarks>
public enum SessionState
{
    /// <summary>Unset. Never valid on a persisted row.</summary>
    Unknown = 0,

    /// <summary>A problem is being articulated. A greeting alone creates no session.</summary>
    Conversational = 1,

    /// <summary>The agent is working the problem.</summary>
    Resolving = 2,

    /// <summary>Suspended on a clarifying question. Persists indefinitely.</summary>
    AwaitingUser = 3,

    /// <summary>Suspended on the requester's consent. Persists indefinitely.</summary>
    AwaitingConsent = 4,

    /// <summary>Suspended on a staff approval verdict. Persists indefinitely.</summary>
    AwaitingApproval = 5,

    /// <summary>A staff member has taken over. Take-over never transfers requester authority.</summary>
    StaffControlled = 6,

    /// <summary>Terminal. The request was resolved.</summary>
    Resolved = 7,

    /// <summary>Terminal. The request left the platform for a human.</summary>
    Escalated = 8,

    /// <summary>Terminal. The requester declined to proceed.</summary>
    ClosedDeclined = 9,
}

/// <summary>Who authored a message.</summary>
public enum SenderKind
{
    /// <summary>Unset.</summary>
    Unknown = 0,

    /// <summary>The session's requester.</summary>
    EndUser = 1,

    /// <summary>The platform agent.</summary>
    Agent = 2,

    /// <summary>A staff member in a taken-over session. Confers no requester authority.</summary>
    Staff = 3,
}

/// <summary>A revisable per-message quality signal.</summary>
/// <remarks>
/// Feedback MUST NOT be read by governance, retrieval or execution. It is never an input to an
/// authorization outcome (contracts §customer-api).
/// </remarks>
public enum FeedbackSignal
{
    /// <summary>Unset.</summary>
    Unknown = 0,

    /// <summary>Positive.</summary>
    Positive = 1,

    /// <summary>Negative.</summary>
    Negative = 2,
}
