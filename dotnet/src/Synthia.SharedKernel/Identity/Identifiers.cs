namespace Synthia.SharedKernel.Identity;

/// <summary>
/// The Entra tenant identifier (<c>tid</c>) of a validated human token.
/// </summary>
/// <remarks>
/// Human identity is <c>(tid, oid)</c> and no other value is an identity key
/// (constitution Principle I). This type exists so a <c>tid</c> cannot be passed where an
/// <c>oid</c> is expected — a mistake a pair of bare <see cref="Guid"/> parameters invites.
/// </remarks>
/// <param name="Value">The validated Entra tenant identifier.</param>
public readonly record struct EntraTenantId(Guid Value)
{
    /// <summary>Renders the identifier for logging and correlation.</summary>
    /// <returns>The identifier in canonical form.</returns>
    public override string ToString() => Value.ToString("D", System.Globalization.CultureInfo.InvariantCulture);
}

/// <summary>
/// The Entra object identifier (<c>oid</c>) of the acting user or workload service principal.
/// </summary>
/// <param name="Value">The validated Entra object identifier.</param>
public readonly record struct PrincipalId(Guid Value)
{
    /// <summary>Renders the identifier for logging and correlation.</summary>
    /// <returns>The identifier in canonical form.</returns>
    public override string ToString() => Value.ToString("D", System.Globalization.CultureInfo.InvariantCulture);
}

/// <summary>
/// The platform's own identifier for a customer organisation.
/// </summary>
/// <remarks>
/// Distinct from <see cref="EntraTenantId"/> on purpose. The Entra <c>tid</c> is what a token
/// carries; this is what platform state is keyed by. Only the tenant registry maps one to the
/// other, and that mapping is the admission decision — it is never inferred from a request.
/// </remarks>
/// <param name="Value">The platform tenant identifier.</param>
public readonly record struct TenantId(Guid Value)
{
    /// <summary>Renders the identifier for logging and correlation.</summary>
    /// <returns>The identifier in canonical form.</returns>
    public override string ToString() => Value.ToString("D", System.Globalization.CultureInfo.InvariantCulture);
}

/// <summary>
/// A correlation identifier, originating at the public edge and propagated through every tier.
/// </summary>
/// <remarks>
/// Appears on every log record, trace, notification, trigger and audit record, so one user
/// request can be followed across an asynchronous, suspendable flow (spec FR-OPS-001).
/// </remarks>
public readonly record struct CorrelationId
{
    private readonly string? _value;

    private CorrelationId(string value) => _value = value;

    /// <summary>The correlation value. Never empty for a constructed instance.</summary>
    public string Value => _value ?? string.Empty;

    /// <summary>Creates a new correlation identifier when a request arrives without one.</summary>
    /// <returns>A fresh identifier.</returns>
    public static CorrelationId New() =>
        new(Guid.NewGuid().ToString("N", System.Globalization.CultureInfo.InvariantCulture));

    /// <summary>
    /// Accepts a client-supplied correlation identifier, but only when it is well formed.
    /// </summary>
    /// <remarks>
    /// A correlation identifier is diagnostic data, never authority — but it reaches log sinks and
    /// audit records, so an unbounded or control-character-bearing value is a log-injection vector.
    /// Malformed input is rejected rather than sanitised, and the caller generates a fresh one.
    /// </remarks>
    /// <param name="candidate">The inbound header value.</param>
    /// <param name="correlationId">The accepted identifier, when well formed.</param>
    /// <returns><see langword="true"/> when the candidate was accepted.</returns>
    public static bool TryAccept(string? candidate, out CorrelationId correlationId)
    {
        correlationId = default;
        if (string.IsNullOrWhiteSpace(candidate) || candidate.Length > 128)
        {
            return false;
        }

        foreach (char c in candidate)
        {
            bool allowed = char.IsAsciiLetterOrDigit(c) || c is '-' or '_' or '.';
            if (!allowed)
            {
                return false;
            }
        }

        correlationId = new CorrelationId(candidate);
        return true;
    }

    /// <summary>Renders the identifier.</summary>
    /// <returns>The correlation value.</returns>
    public override string ToString() => Value;
}

/// <summary>The durable authority record for a chat session.</summary>
/// <param name="Value">The work item identifier.</param>
public readonly record struct WorkItemId(Guid Value);

/// <summary>One conversation between an end user and the platform.</summary>
/// <param name="Value">The session identifier, opaque to clients.</param>
public readonly record struct SessionId(Guid Value);

/// <summary>A single proposed or executed action within a session.</summary>
/// <param name="Value">The operation identifier.</param>
public readonly record struct OperationId(Guid Value);

/// <summary>A staff member's recorded decision authorising a consequential operation.</summary>
/// <param name="Value">The approval identifier.</param>
public readonly record struct ApprovalId(Guid Value);

/// <summary>An end user's recorded agreement to an operation on their own account or device.</summary>
/// <param name="Value">The consent identifier.</param>
public readonly record struct ConsentId(Guid Value);

/// <summary>A durable business or security record, distinct from telemetry.</summary>
/// <param name="Value">The audit event identifier.</param>
public readonly record struct AuditEventId(Guid Value);

/// <summary>A single turn in a conversation.</summary>
/// <param name="Value">The message identifier.</param>
public readonly record struct MessageId(Guid Value);
