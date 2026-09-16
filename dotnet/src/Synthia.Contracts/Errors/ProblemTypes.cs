namespace Synthia.Contracts.Errors;

/// <summary>
/// The RFC 9457 problem types this platform emits.
/// </summary>
/// <remarks>
/// <b>Internal exception detail MUST NEVER reach a client.</b> These are the whole outward
/// vocabulary: a problem the client sees is one of these, with a message written for them rather
/// than lifted from an exception.
/// </remarks>
public static class ProblemTypes
{
    private const string Base = "https://synthia.synoptek.com/problems/";

    /// <summary>Input failed validation at the boundary.</summary>
    public const string ValidationFailed = Base + "validation-failed";

    /// <summary>The request carried no usable identity context.</summary>
    public const string Unauthenticated = Base + "unauthenticated";

    /// <summary>The principal holds no role this operation accepts.</summary>
    public const string Forbidden = Base + "forbidden";

    /// <summary>The resource does not exist, or does not exist for this caller.</summary>
    /// <remarks>
    /// Used where <b>existence itself is tenant-scoped information</b>. Returning 403 for another
    /// organisation's resource would confirm that it exists, which is a cross-organisation
    /// disclosure in its own right — so the answer is 404.
    /// </remarks>
    public const string NotFound = Base + "not-found";

    /// <summary>A concurrent change won; the caller should re-read and retry.</summary>
    public const string ConcurrencyConflict = Base + "concurrency-conflict";

    /// <summary>The execution validity window elapsed. Not an error condition.</summary>
    public const string AuthorizationExpired = Base + "authorization-expired";

    /// <summary>The organisation's budget or rate limit was reached.</summary>
    /// <remarks>
    /// Reported distinctly from a failure: the user is told the request was limited, not that it
    /// failed (spec FR-OPS-006).
    /// </remarks>
    public const string Throttled = Base + "throttled";

    /// <summary>
    /// A capability is entitled but its system is unreachable.
    /// </summary>
    /// <remarks>
    /// Distinct from not-entitled, and neither is presented to the user as a failure of their
    /// request (spec FR-EXT-022).
    /// </remarks>
    public const string TemporarilyUnavailable = Base + "temporarily-unavailable";

    /// <summary>An unexpected fault. Carries no internal detail.</summary>
    public const string Unexpected = Base + "unexpected";
}

/// <summary>
/// The problem-details shape both deployables emit, so a client parses one error contract.
/// </summary>
/// <remarks>
/// Mirrors RFC 9457 and adds <see cref="CorrelationId"/>, which is what turns a user-visible error
/// into something traceable across a suspendable, asynchronous flow.
/// </remarks>
/// <param name="Type">A <see cref="ProblemTypes"/> URI.</param>
/// <param name="Title">A short, client-safe summary.</param>
/// <param name="Status">The HTTP status code.</param>
/// <param name="Detail">A client-safe explanation. Never an exception message.</param>
/// <param name="Instance">The request path this problem occurred on.</param>
/// <param name="CorrelationId">The correlation identifier for this request.</param>
public sealed record ProblemContract(
    string Type,
    string Title,
    int Status,
    string? Detail,
    string? Instance,
    string CorrelationId);
