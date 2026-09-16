using System.ComponentModel.DataAnnotations;
using System.Globalization;
using Microsoft.Extensions.Options;

namespace Synthia.Api.Configuration;

/// <summary>
/// How this process proves a request arrived through APIM.
/// </summary>
/// <remarks>
/// <para>
/// <b>APIM is the identity/trust boundary.</b> This service consumes the closed <c>X-Idp-*</c>
/// contract and never parses a token, which is only safe while it can tell an APIM-stamped header
/// from one a caller typed. The certificate hash configured here is what tells them apart
/// (<c>GatewayProvenanceMiddleware</c>, <c>build/policy/edge-trust.json</c>).
/// </para>
/// <para>
/// <b>Required, with no default and no environment branch.</b> Every other option type in this
/// folder has a defensible empty state; this one does not. An unconfigured vault fails loudly on
/// the first secret it needs, whereas an unconfigured allow-list fails <i>silently</i>, by
/// accepting forged identity, and produces a service that looks perfectly healthy. There is
/// consequently no local bypass — which matches how identity is already treated here, since a
/// developer running this process directly must already supply the five <c>X-Idp-*</c> headers by
/// hand.
/// </para>
/// <para>
/// <b>Not secret material.</b> A thumbprint is the hash of a public certificate, so it is ordinary
/// configuration rather than a Key Vault reference. Holding it gets an attacker nothing without
/// the private key APIM holds, and routing it through the vault would wrongly suggest otherwise.
/// </para>
/// </remarks>
internal sealed class EdgeTrustOptions
{
    /// <summary>The configuration section this binds from.</summary>
    public const string SectionName = "EdgeTrust";

    /// <summary>
    /// SHA-256 hashes of the accepted gateway client certificates, comma-separated.
    /// </summary>
    /// <remarks>
    /// Comma-separated because rotation is an <b>overlap</b>: the outgoing and incoming hashes sit
    /// here together while APIM is cut over, so there is no instant at which neither is accepted.
    /// A single value would make every rotation a synchronised swap with a window in which the
    /// platform is either down or, worse, briefly unguarded.
    /// </remarks>
    [Required(AllowEmptyStrings = false)]
    public string GatewayCertificateThumbprints { get; init; } = string.Empty;

    /// <summary>The parsed allow-list, folded for comparison.</summary>
    /// <returns>The accepted hashes. Never empty for a validated instance.</returns>
    public IReadOnlySet<string> AcceptedThumbprints() =>
        ParseThumbprints(GatewayCertificateThumbprints);

    /// <summary>Parses a comma-separated allow-list into its comparison form.</summary>
    /// <param name="configured">The raw setting value.</param>
    /// <returns>
    /// The accepted hashes. Empty when nothing is configured — the caller decides that this is
    /// fatal, so that the parsing rule and the start-up rule stay separable.
    /// </returns>
    public static IReadOnlySet<string> ParseThumbprints(string? configured)
    {
        HashSet<string> accepted = new(StringComparer.Ordinal);

        foreach (string entry in (configured ?? string.Empty).Split(','))
        {
            string folded = Normalise(entry);

            if (folded.Length > 0)
            {
                accepted.Add(folded);
            }
        }

        return accepted;
    }

    /// <summary>
    /// Folds one configured or forwarded hash to its comparison form.
    /// </summary>
    /// <remarks>
    /// Quotes and colons are stripped because a thumbprint copied from a certificate viewer
    /// carries them, and a control that silently matches nothing rejects every request — an outage
    /// whose cause is a formatting difference nobody can see.
    /// </remarks>
    /// <param name="value">The raw value.</param>
    /// <returns>The folded value.</returns>
    public static string Normalise(string? value) =>
        (value ?? string.Empty)
            .Trim()
            .Trim('"')
            .Replace(":", string.Empty, StringComparison.Ordinal)
            .ToLowerInvariant();

    /// <summary>Whether a folded value is a well-formed SHA-256 digest.</summary>
    /// <param name="folded">A value already passed through <see cref="Normalise"/>.</param>
    /// <returns><see langword="true"/> when it is 64 lowercase hex characters.</returns>
    public static bool IsSha256Digest(string folded)
    {
        ArgumentNullException.ThrowIfNull(folded);

        if (folded.Length != 64)
        {
            return false;
        }

        foreach (char character in folded)
        {
            bool isHex = (character >= '0' && character <= '9')
                || (character >= 'a' && character <= 'f');

            if (!isHex)
            {
                return false;
            }
        }

        return true;
    }
}

/// <summary>
/// Refuses a malformed or absent allow-list at start-up rather than at the first request.
/// </summary>
/// <remarks>
/// Fail-closed, and fatal on purpose. A process that started without this control would accept
/// forged identity headers and produce no error, no failed probe and no unusual log line — the
/// defect is invisible in exactly the way a security defect must not be.
/// </remarks>
internal sealed class EdgeTrustOptionsValidator : IValidateOptions<EdgeTrustOptions>
{
    /// <inheritdoc/>
    public ValidateOptionsResult Validate(string? name, EdgeTrustOptions options)
    {
        ArgumentNullException.ThrowIfNull(options);

        IReadOnlySet<string> accepted = options.AcceptedThumbprints();

        if (accepted.Count == 0)
        {
            return ValidateOptionsResult.Fail(
                "EdgeTrust:GatewayCertificateThumbprints is required. Without it this process " +
                "cannot distinguish a request that came through APIM from one that did not, and " +
                "would accept forged identity headers while looking perfectly healthy.");
        }

        foreach (string thumbprint in accepted)
        {
            if (!EdgeTrustOptions.IsSha256Digest(thumbprint))
            {
                return ValidateOptionsResult.Fail(string.Format(
                    CultureInfo.InvariantCulture,
                    "EdgeTrust:GatewayCertificateThumbprints must contain 64-character hex " +
                    "SHA-256 digests; found an entry of length {0}. A truncated thumbprint " +
                    "matches nothing, and a control that matches nothing refuses every request.",
                    thumbprint.Length));
            }
        }

        return ValidateOptionsResult.Success;
    }
}
