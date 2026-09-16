using System.ComponentModel.DataAnnotations;

namespace Synthia.Api.Configuration;

/// <summary>
/// Where secret material comes from.
/// </summary>
/// <remarks>
/// <b>Key Vault is the sole source of secret material</b> (constitution Principle IV), reached
/// through managed identity. There is deliberately no client-secret or certificate-path setting
/// here: a credential configured to read the vault would be a standing secret outside the vault,
/// which is the problem the vault exists to remove.
/// </remarks>
public sealed class KeyVaultOptions
{
    /// <summary>The configuration section this binds to.</summary>
    public const string Section = "KeyVault";

    /// <summary>
    /// The vault URI, or empty to resolve no secrets from a vault.
    /// </summary>
    /// <remarks>
    /// Empty is legitimate on a developer machine, where settings come from user secrets and
    /// environment variables. It is not a supported deployed configuration, and the deployment
    /// pipeline is what enforces that — a running process cannot tell which environment it wishes
    /// it were in.
    /// </remarks>
    public string VaultUri { get; set; } = string.Empty;

    /// <summary>How often a changed secret is picked up without a restart.</summary>
    /// <remarks>
    /// Reloading matters because a rotated secret should not need a deployment to take effect, and
    /// a rotation that needs one tends not to happen.
    /// </remarks>
    [Range(1, 1440)]
    public int ReloadIntervalMinutes { get; set; } = 60;

    /// <summary>Whether a vault URI is configured.</summary>
    public bool IsConfigured => !string.IsNullOrWhiteSpace(VaultUri);

    /// <summary>
    /// Whether the configured URI is one this process will actually dial.
    /// </summary>
    /// <remarks>
    /// <b>Not a <c>[Url]</c> annotation, for two reasons.</b> <c>[Url]</c> rejects the empty
    /// string, and empty is the legitimate developer-machine value. It also accepts <c>http</c> and
    /// <c>ftp</c>, and a secret fetched over plaintext is a secret in transit to anybody watching —
    /// so the rule is narrower than the annotation, not wider.
    /// </remarks>
    public bool IsValid =>
        !IsConfigured ||
        (Uri.TryCreate(VaultUri, UriKind.Absolute, out Uri? uri) &&
         string.Equals(uri.Scheme, Uri.UriSchemeHttps, StringComparison.Ordinal));
}
