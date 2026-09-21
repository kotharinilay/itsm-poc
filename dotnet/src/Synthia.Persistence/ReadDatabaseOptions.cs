using System.ComponentModel.DataAnnotations;

namespace Synthia.Persistence;

/// <summary>
/// Everything this deployable needs to reach PostgreSQL, and nothing more.
/// </summary>
/// <remarks>
/// <para>
/// Bound with <c>BindConfiguration</c>, validated with <c>ValidateDataAnnotations()</c> and
/// <c>ValidateOnStart()</c> (research R-019). <b>A missing setting stops the process at start</b>,
/// which turns a latent configuration defect into a failed deployment — where it is cheapest.
/// </para>
/// <para>
/// The connection string names a principal granted <c>SELECT</c> on published views only. It is
/// secret material and resolves through managed identity and Key Vault in every deployed
/// environment; the local value in <c>appsettings.Development.json</c> is a developer database.
/// </para>
/// </remarks>
public sealed class ReadDatabaseOptions
{
    /// <summary>The configuration section this binds to.</summary>
    public const string Section = "ReadDatabase";

    /// <summary>The Npgsql connection string for the read principal.</summary>
    [Required(AllowEmptyStrings = false)]
    public string ConnectionString { get; set; } = string.Empty;

    /// <summary>
    /// How long a single query may run before it is cancelled, in seconds.
    /// </summary>
    /// <remarks>
    /// Bounded deliberately. A read that outlives its caller holds a pooled connection and a
    /// request thread for nothing, and a listing that is slow enough to matter is a missing index,
    /// not a reason to wait longer.
    /// </remarks>
    [Range(1, 120)]
    public int CommandTimeoutSeconds { get; set; } = 30;

    /// <summary>
    /// Whether to surface parameter values and raw SQL in exceptions and logs.
    /// </summary>
    /// <remarks>
    /// <b>Off everywhere but a developer machine.</b> Parameter values on a tenant-scoped query are
    /// customer data, and logs and telemetry MUST NOT leak sensitive customer payloads or any
    /// cross-tenant information (.claude/rules/20-dotnet.md BL-24).
    /// </remarks>
    public bool EnableSensitiveDataLogging { get; set; }
}
