namespace Synthia.SharedKernel.Work;

/// <summary>
/// The lifecycle of the durable authority record.
/// </summary>
/// <remarks>
/// <c>Open → AwaitingDecision → Authorized → Claimed → Executed | Failed</c>, plus the terminal
/// states below. A failed authorized action does <b>not</b> re-fire; it requires fresh human
/// authorization (spec FR-EXEC-006).
/// </remarks>
public enum WorkItemState
{
    /// <summary>Unset.</summary>
    Unknown = 0,

    /// <summary>Raised, no decision sought yet.</summary>
    Open = 1,

    /// <summary>Suspended on a human decision.</summary>
    AwaitingDecision = 2,

    /// <summary>Authority recorded. Execution has not started.</summary>
    Authorized = 3,

    /// <summary>Claimed by an executing principal. The claim is atomic and wins once.</summary>
    Claimed = 4,

    /// <summary>Execution completed and its outcome was recorded.</summary>
    Executed = 5,

    /// <summary>Execution ran and failed. Terminal without fresh authorization.</summary>
    Failed = 6,

    /// <summary>The validity window elapsed with no claim. Not an error (spec FR-EXEC-001).</summary>
    Expired = 7,

    /// <summary>Cancelled before the claim.</summary>
    Cancelled = 8,

    /// <summary>Handed to a human.</summary>
    Escalated = 9,
}

/// <summary>Where a work item stands against its approval requirement.</summary>
public enum ApprovalState
{
    /// <summary>Unset.</summary>
    Unknown = 0,

    /// <summary>No approval is required for this work.</summary>
    None = 1,

    /// <summary>An approval has been requested and may suspend indefinitely.</summary>
    Pending = 2,

    /// <summary>Approved. Execution validity is fifteen minutes from the decision.</summary>
    Approved = 3,

    /// <summary>Refused. The work closes without execution.</summary>
    Rejected = 4,

    /// <summary>The approval window elapsed.</summary>
    Expired = 5,
}
