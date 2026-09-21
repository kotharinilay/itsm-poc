namespace Synthia.SharedKernel.Governance;

/// <summary>
/// How an operation may proceed. Exactly one of four, assigned by deterministic policy from the
/// canonical operation catalogue.
/// </summary>
/// <remarks>
/// <para>
/// <b>The model MUST NEVER choose, influence or override this</b> (A3 §6.3).
/// There is no <c>Unknown</c> or <c>Default</c> member: a missing treatment is not a state this
/// type can represent, so "we could not determine the treatment, carry on" cannot be expressed.
/// A catalogue lookup that finds nothing is a refusal, not a default.
/// </para>
/// </remarks>
public enum ExecutionTreatment
{
    /// <summary>Proceeds without a human decision.</summary>
    Auto = 1,

    /// <summary>
    /// Requires the requester's consent, for an operation on their own account or device.
    /// Consent never satisfies a <see cref="StaffApproval"/> requirement.
    /// </summary>
    EndUserApproval = 2,

    /// <summary>
    /// Requires a staff verdict from a principal holding a role the operation accepts.
    /// </summary>
    StaffApproval = 3,

    /// <summary>
    /// Refused at the gate. Never surfaced to any human as an approvable proposal, and recorded
    /// as a denial.
    /// </summary>
    NotAllowed = 4,
}

/// <summary>Whether a capability reads state or changes it.</summary>
/// <remarks>
/// An <see cref="Action"/> capability MUST NOT be callable directly from the agent loop and passes
/// through deterministic governance and, where required, human approval (spec FR-EXT-013).
/// </remarks>
public enum CapabilityKind
{
    /// <summary>Unset. Treated as an action, because that is the safe reading.</summary>
    Unknown = 0,

    /// <summary>Retrieves state. No side effect.</summary>
    Read,

    /// <summary>Has a side effect.</summary>
    Action,
}

/// <summary>
/// What the platform actually knows about an execution's outcome.
/// </summary>
/// <remarks>
/// A client-reported result is a claim, not proof. The platform MUST NOT claim to know more than
/// it does (ADR-0004).
/// </remarks>
public enum VerificationOutcome
{
    /// <summary>Unset. Never valid on a recorded outcome.</summary>
    Unknown = 0,

    /// <summary>A server-side read tool confirmed the effect. Reported as resolved.</summary>
    ServerConfirmed,

    /// <summary>
    /// No server-side read path exists for this effect. Reported as <i>reported complete, not
    /// independently verified</i>, and MUST NOT be presented as confirmed resolution.
    /// </summary>
    ClientAttested,

    /// <summary>A server-side read disagreed with the claim. Treated as a failure.</summary>
    Contradicted,
}

/// <summary>
/// The identity of a catalogue entry, bound to the version in force when it was proposed.
/// </summary>
/// <remarks>
/// The version is part of the identity because an approval binds the operation version it was
/// granted against. A catalogue edit between approval and execution must not silently change what
/// a human authorised.
/// </remarks>
/// <param name="CatalogueId">The stable catalogue key.</param>
/// <param name="Version">The catalogue entry version bound at proposal time.</param>
public readonly record struct OperationIdentity(string CatalogueId, int Version)
{
    /// <summary>Renders the identity for logging and audit.</summary>
    /// <returns>The identity as <c>catalogueId@version</c>.</returns>
    public override string ToString() =>
        string.Create(System.Globalization.CultureInfo.InvariantCulture, $"{CatalogueId}@{Version}");
}

/// <summary>
/// A deterministic key that makes an external effect happen at most once.
/// </summary>
/// <remarks>
/// Idempotency boundary 2, protecting the <b>external</b> system. Boundary 1 is the atomic claim on
/// the work item, which protects the platform. Both are required; neither substitutes for the
/// other.
/// </remarks>
/// <param name="Value">The deterministic key.</param>
public readonly record struct IdempotencyKey(string Value)
{
    /// <summary>Renders the key.</summary>
    /// <returns>The key value.</returns>
    public override string ToString() => Value;
}
