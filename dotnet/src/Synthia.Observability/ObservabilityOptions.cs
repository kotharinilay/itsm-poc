using System.ComponentModel.DataAnnotations;

namespace Synthia.Observability;

/// <summary>
/// What this deployable needs to be observable.
/// </summary>
/// <remarks>
/// Bound, validated with data annotations and validated at start (research R-019). A deployment
/// that cannot export telemetry should fail while someone is watching it deploy.
/// </remarks>
public sealed class ObservabilityOptions
{
    /// <summary>The configuration section this binds to.</summary>
    public const string Section = "Observability";

    /// <summary>The service name every span, metric and log record is tagged with.</summary>
    [Required(AllowEmptyStrings = false)]
    public string ServiceName { get; set; } = "synthia-monolith";

    /// <summary>The deployment environment, as OpenTelemetry names it.</summary>
    [Required(AllowEmptyStrings = false)]
    public string DeploymentEnvironment { get; set; } = "development";

    /// <summary>
    /// The Application Insights connection string, or empty to export nothing.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Empty is legitimate and means a developer machine: instrumentation is still collected and
    /// still costs the same, it simply has nowhere to go. It is <b>not</b> a way to turn telemetry
    /// off in a deployed environment, and <c>ValidateOnStart</c> cannot tell the difference — that
    /// is what the deployment configuration is for.
    /// </para>
    /// <para>
    /// Secret material. It resolves through managed identity and Key Vault, never a committed file.
    /// </para>
    /// </remarks>
    public string AzureMonitorConnectionString { get; set; } = string.Empty;
}
