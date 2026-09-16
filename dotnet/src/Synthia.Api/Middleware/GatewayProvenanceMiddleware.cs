using Microsoft.Extensions.Options;
using Microsoft.Extensions.Primitives;
using Synthia.Api.Configuration;
using Synthia.Api.Errors;

namespace Synthia.Api.Middleware;

/// <summary>
/// Refuses any request that cannot prove it arrived through APIM.
/// </summary>
/// <remarks>
/// <para>
/// <b>This is the control that makes the identity contract evidence rather than input.</b>
/// <c>IdentityContextMiddleware</c> consumes the five <c>X-Idp-*</c> headers as authoritative; it
/// may only do so because this middleware has already run and refused anything that did not come
/// through the gateway that sets them.
/// </para>
/// <para>
/// <b>The gap this closes.</b> Network placement alone was the whole of the model: internal
/// ingress, a private VNet. The specification is explicit that this is <i>not sufficient alone</i>
/// (spec §10.3) — a VNet admits everything already inside it, including a compromised sidecar, a
/// misconfigured job or a second container app, any of which could have minted whatever tenant and
/// role it liked.
/// </para>
/// <para>
/// <b>How provenance is proved.</b> APIM presents a client certificate on the backend connection.
/// Container Apps ingress validates it and republishes it as <c>X-Forwarded-Client-Cert</c> —
/// <i>ingress sets that header itself</i>, replacing whatever arrived, which is precisely what
/// makes the hash in it evidence and not merely another thing a caller typed. This middleware
/// compares that hash against the configured allow-list. APIM also deletes any inbound copy before
/// forwarding, so the two ends agree without either relying on the other's diligence.
/// </para>
/// <para>
/// <b>Refusal, not sanitisation.</b> A request that cannot prove provenance is rejected whole.
/// Stripping the identity headers and continuing would hand an attacker a <c>200</c> for a probe
/// and leave the attempt indistinguishable, in the logs, from an ordinary unauthenticated call.
/// </para>
/// <para>
/// The single authoritative description of all of this is <c>build/policy/edge-trust.json</c>,
/// which this middleware and its RagCore counterpart both enforce and which
/// <c>EdgeTrustPolicyTests</c> reads directly.
/// </para>
/// </remarks>
internal sealed class GatewayProvenanceMiddleware
{
    /// <summary>Set by Container Apps ingress from the certificate it validated. Never by a caller.</summary>
    public const string ForwardedClientCertificateHeader = "X-Forwarded-Client-Cert";

    /// <summary>The XFCC element carrying the SHA-256 of the peer certificate, as lowercase hex.</summary>
    public const string HashElement = "Hash";

    /// <summary>
    /// The only path prefix served without provenance.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Health probes originate from the Container Apps infrastructure on the internal network. They
    /// do not traverse APIM, carry no certificate, and have nothing they could carry instead. They
    /// are also the sole anonymous surface (spec §13.6) and expose no identity, so a request that
    /// reaches one has gained nothing.
    /// </para>
    /// <para>
    /// A <i>prefix</i> rather than a list of exact paths, on purpose: an exact list grows an entry
    /// at a time, and the entry somebody adds without thinking is the one that matters. Extending
    /// this requires moving a route under <c>/health</c>, which is visible in review.
    /// </para>
    /// </remarks>
    public const string ExemptPathPrefix = "/health";

    private readonly RequestDelegate _next;
    private readonly ILogger<GatewayProvenanceMiddleware> _logger;
    private readonly IReadOnlySet<string> _accepted;

    /// <summary>Creates the middleware and binds the allow-list for the life of the process.</summary>
    /// <param name="next">The next component in the pipeline.</param>
    /// <param name="logger">Structured logger.</param>
    /// <param name="options">
    /// The edge trust options. Already validated at start, so the allow-list here is non-empty and
    /// well formed — this middleware never has to decide what to do about an unconfigured one,
    /// because such a process does not start.
    /// </param>
    public GatewayProvenanceMiddleware(
        RequestDelegate next,
        ILogger<GatewayProvenanceMiddleware> logger,
        IOptions<EdgeTrustOptions> options)
    {
        ArgumentNullException.ThrowIfNull(next);
        ArgumentNullException.ThrowIfNull(logger);
        ArgumentNullException.ThrowIfNull(options);

        _next = next;
        _logger = logger;
        _accepted = options.Value.AcceptedThumbprints();
    }

    /// <summary>Screens one request for gateway provenance, then runs the rest of the pipeline.</summary>
    /// <param name="context">The request.</param>
    /// <returns>A task that completes when the pipeline does.</returns>
    public async Task InvokeAsync(HttpContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        if (context.Request.Path.StartsWithSegments(ExemptPathPrefix, StringComparison.Ordinal))
        {
            await _next(context).ConfigureAwait(false);
            return;
        }

        if (!HasProvenance(context.Request))
        {
            // The reason is logged; the header value is not. It is unvalidated input on a path that
            // reaches a log sink, and the hash it carries is the only part worth reading — which is
            // exactly the part an attacker would like echoed back somewhere they can see it.
            ProvenanceLog.RefusedWithoutProvenance(_logger, context.Request.Path);

            await Problems.Forbidden(
                    context,
                    "This API is served only through the platform gateway. Identity is derived " +
                    "once, at the gateway, and a request that did not arrive through it carries " +
                    "no identity this service can accept.")
                .ExecuteAsync(context)
                .ConfigureAwait(false);
            return;
        }

        await _next(context).ConfigureAwait(false);
    }

    private bool HasProvenance(HttpRequest request)
    {
        StringValues values = request.Headers[ForwardedClientCertificateHeader];

        // Exactly one. Zero means no certificate was validated; more than one means two parties
        // both claimed to have validated something, and this process cannot know which to believe.
        if (values.Count != 1)
        {
            return false;
        }

        string? forwarded = ForwardedCertificateHash(values[0]);

        return forwarded is not null && _accepted.Contains(forwarded);
    }

    /// <summary>
    /// Extracts the peer certificate hash from one <c>X-Forwarded-Client-Cert</c> value.
    /// </summary>
    /// <remarks>
    /// <para>
    /// The header is <c>Key=Value;Key=Value</c> per element, with <c>,</c> separating elements when
    /// a chain is forwarded. Container Apps ingress sets <b>exactly one</b> element, for the peer
    /// it validated.
    /// </para>
    /// <para>
    /// <b>More than one element is refused rather than resolved.</b> A chain here means something
    /// between APIM and this process appended to the header, and there is no reading of that which
    /// is both safe and knowable from inside this method: taking the first trusts whatever was
    /// furthest away, taking the last trusts whatever was nearest, and either choice is a policy
    /// decision made by a parser. Refusing states the deployment has changed.
    /// </para>
    /// </remarks>
    /// <param name="headerValue">The raw header.</param>
    /// <returns>The hash, folded for comparison, or <see langword="null"/> when there is no single usable one.</returns>
    public static string? ForwardedCertificateHash(string? headerValue)
    {
        string raw = headerValue ?? string.Empty;

        if (raw.Contains(',', StringComparison.Ordinal))
        {
            return null;
        }

        foreach (string element in raw.Split(';'))
        {
            int separator = element.IndexOf('=', StringComparison.Ordinal);

            if (separator <= 0)
            {
                continue;
            }

            string key = element[..separator].Trim();

            if (!string.Equals(key, HashElement, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            string folded = EdgeTrustOptions.Normalise(element[(separator + 1)..]);

            return folded.Length == 0 ? null : folded;
        }

        return null;
    }
}

/// <summary>Log messages for gateway provenance.</summary>
internal static partial class ProvenanceLog
{
    /// <summary>
    /// Records a request refused for want of gateway provenance.
    /// </summary>
    /// <remarks>
    /// Warning rather than Information: on a correctly deployed platform this cannot happen from
    /// outside, so every occurrence is either a misconfigured gateway certificate or something
    /// inside the network reaching a backend directly. Both are worth waking up for.
    /// </remarks>
    /// <param name="logger">The logger.</param>
    /// <param name="path">The path requested. A path, never a header value.</param>
    [LoggerMessage(
        EventId = 1104,
        Level = LogLevel.Warning,
        Message = "Refused a request to {Path} that could not prove gateway provenance.")]
    public static partial void RefusedWithoutProvenance(ILogger logger, string path);
}
