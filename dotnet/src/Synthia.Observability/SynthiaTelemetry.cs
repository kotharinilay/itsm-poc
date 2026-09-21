using System.Diagnostics;
using System.Diagnostics.Metrics;

namespace Synthia.Observability;

/// <summary>
/// The names this deployable emits telemetry under, and the tags it is allowed to attach.
/// </summary>
public static class SynthiaTelemetry
{
    /// <summary>The activity source every span this deployable starts belongs to.</summary>
    public const string ActivitySourceName = "Synthia.Monolith";

    /// <summary>The meter every instrument this deployable creates belongs to.</summary>
    public const string MeterName = "Synthia.Monolith";

    /// <summary>The span and log tag carrying the correlation identifier.</summary>
    public const string CorrelationTag = "synthia.correlation_id";

    /// <summary>The span and log tag carrying the organisation in scope.</summary>
    /// <remarks>
    /// The <b>platform</b> organisation identifier, never the Entra tenant and never a display
    /// name. An opaque identifier is enough to correlate and is not itself customer information.
    /// </remarks>
    public const string TenantTag = "synthia.tenant_id";

    /// <summary>The span tag carrying the audience a request was routed to.</summary>
    public const string AudienceTag = "synthia.audience";

    /// <summary>The activity source, for code that starts its own spans.</summary>
    public static ActivitySource ActivitySource { get; } = new(ActivitySourceName);

    /// <summary>The meter, for code that records its own measurements.</summary>
    public static Meter Meter { get; } = new(MeterName);

    /// <summary>
    /// The only values permitted in W3C baggage.
    /// </summary>
    /// <remarks>
    /// <b>Baggage crosses process and organisation boundaries in cleartext.</b> .claude/rules/20-dotnet.md
    /// BL-24 allows only explicitly permitted values there — correlation id, and tenant where permitted
    /// there. Anything else is a leak waiting for a downstream system to log it, so the
    /// allowed set is written down rather than left to judgement at each call site.
    /// </remarks>
    public static IReadOnlySet<string> AllowedBaggageKeys { get; } =
        new HashSet<string>(StringComparer.Ordinal) { CorrelationTag, TenantTag };
}
