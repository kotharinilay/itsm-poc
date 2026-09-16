using System.ComponentModel.DataAnnotations;

namespace Synthia.Api.Configuration;

/// <summary>
/// The runtime contract between this process and Azure Container Apps.
/// </summary>
/// <remarks>
/// <para>
/// The platform decides when to send <c>SIGTERM</c>; the process decides what it does with the time
/// it is given. These settings are the process half, and they are validated at start so a drain
/// shorter than the work it has to drain fails the deployment rather than the request.
/// </para>
/// <para>
/// <b>The drain is a grace period, not a guarantee</b> (plan Stage 10). On <c>SIGTERM</c> this API
/// stops accepting requests and finishes those in flight. Nothing is claimed here — the monolith is
/// read-only — so nothing is at risk of the approved-but-not-executed condition that a draining
/// <i>worker</i> can produce. That case belongs to RagCore.
/// </para>
/// </remarks>
public sealed class ContainerAppsOptions
{
    /// <summary>The configuration section this binds to.</summary>
    public const string Section = "ContainerApps";

    /// <summary>
    /// How long in-flight requests are given after <c>SIGTERM</c>, in seconds.
    /// </summary>
    /// <remarks>
    /// Twenty-five seconds, matching the platform's drain (constitution §Containers). Setting the
    /// host's own shutdown timeout to the same value is what makes the two agree: a host that gives
    /// up sooner drops requests the platform was still waiting for, and one that gives up later is
    /// killed mid-request anyway.
    /// </remarks>
    [Range(1, 120)]
    public int ShutdownTimeoutSeconds { get; set; } = 25;

    /// <summary>The port the container listens on.</summary>
    /// <remarks>
    /// 8080 — the chiseled image's non-root user cannot bind a privileged port, and would not be
    /// given the capability if it could (research R-011).
    /// </remarks>
    [Range(1024, 65535)]
    public int Port { get; set; } = 8080;

    /// <summary>The drain period as a duration.</summary>
    public TimeSpan ShutdownTimeout => TimeSpan.FromSeconds(ShutdownTimeoutSeconds);
}
