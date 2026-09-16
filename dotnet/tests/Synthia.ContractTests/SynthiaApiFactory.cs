using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;

namespace Synthia.ContractTests;

/// <summary>
/// The gateway this test suite pretends to be.
/// </summary>
/// <remarks>
/// <para>
/// <b>There is no test-only bypass of gateway provenance, and there must not be.</b> The suite
/// simulates APIM rather than disabling the check, because a bypass would mean the pipeline under
/// test is not the pipeline that ships — and the one control whose absence is invisible in
/// production would be the one control never exercised.
/// </para>
/// <para>
/// The value is a syntactically valid SHA-256 digest that corresponds to no real certificate. It is
/// not secret: a thumbprint is the hash of a <i>public</i> certificate, and the constitution's
/// no-credential-in-tests rule is about credentials, which this is not.
/// </para>
/// </remarks>
internal static class FakeGateway
{
    /// <summary>The certificate hash this suite's requests present.</summary>
    public const string CertificateHash =
        "1111111111111111111111111111111111111111111111111111111111111111";

    /// <summary>A syntactically valid hash belonging to some other gateway.</summary>
    /// <remarks>
    /// Used to assert that a well-formed certificate from the wrong holder is refused. The check
    /// must be an allow-list, not a format check — the latter would accept any certificate at all.
    /// </remarks>
    public const string UnknownCertificateHash =
        "2222222222222222222222222222222222222222222222222222222222222222";

    /// <summary>Formats a hash as Container Apps ingress forwards it.</summary>
    /// <param name="hash">The certificate hash.</param>
    /// <returns>The <c>X-Forwarded-Client-Cert</c> value.</returns>
    public static string ForwardedClientCert(string hash) =>
        $"Hash={hash};Subject=\"CN=synthia-gateway\";URI=";
}

/// <summary>
/// Boots the real application for contract tests.
/// </summary>
/// <remarks>
/// <para>
/// <b>Nothing is stubbed.</b> The pipeline, the middleware order, the routing table and the
/// serializer are the ones production runs — a contract test against a rearranged pipeline proves
/// nothing about the contract.
/// </para>
/// <para>
/// <b>No database is reached, and none is needed.</b> Every assertion here is about the shape of
/// the contract — casing, versioning, cursor envelope, problem details, the whitelist — and each
/// one is decided at the boundary, before a read model runs. A test needing rows is an integration
/// test and belongs where a real PostgreSQL can be started (plan Stage 11, Testcontainers).
/// </para>
/// <para>
/// <b>Configuration arrives as environment variables, not through
/// <c>ConfigureAppConfiguration</c>.</b> Under minimal hosting the application reads its
/// configuration in top-level statements, which run before the factory's configuration callbacks
/// do — so a setting supplied that way is invisible to the code that needs it. Environment
/// variables are read by <c>CreateBuilder</c> itself and are therefore in place in time. That makes
/// the variables process-global, which is why this assembly disables test parallelisation.
/// </para>
/// </remarks>
internal sealed class SynthiaApiFactory : WebApplicationFactory<Program>
{
    /// <summary>
    /// Syntactically valid and pointing nowhere.
    /// </summary>
    /// <remarks>
    /// It exists so start-up validation passes. If a test ever makes the application dial it, that
    /// test has drifted out of this suite, and the connection failure is the right way to find out.
    /// </remarks>
    public const string UnreachableDatabase =
        "Host=contract-tests.invalid;Port=5432;Database=synthia;Username=reader;Password=unused";

    private readonly EnvironmentScope _environment;

    /// <summary>Boots the application with a valid configuration.</summary>
    public SynthiaApiFactory()
        : this(new Dictionary<string, string?>(StringComparer.Ordinal))
    {
    }

    /// <summary>Boots the application with named settings removed or replaced.</summary>
    /// <param name="overrides">
    /// Settings to change. A <see langword="null"/> value removes the setting, which is how the
    /// configuration-validation tests express "this one is missing".
    /// </param>
    public SynthiaApiFactory(IReadOnlyDictionary<string, string?> overrides)
    {
        ArgumentNullException.ThrowIfNull(overrides);

        Dictionary<string, string?> settings = new(StringComparer.Ordinal)
        {
            ["ASPNETCORE_ENVIRONMENT"] = "Development",
            ["ReadDatabase__ConnectionString"] = UnreachableDatabase,

            // Deliberately no Observability__AzureMonitorConnectionString and no
            // KeyVault__VaultUri. Both are legitimately absent outside a deployed environment, and
            // asserting the application still starts without them is part of the contract.
            ["Observability__ServiceName"] = "synthia-monolith-tests",
            ["Observability__DeploymentEnvironment"] = "test",

            // Required, and deliberately with no empty state: a process without an allow-list
            // cannot tell an APIM-stamped identity header from a forged one. Supplied here rather
            // than defaulted in the application, so that "this setting is mandatory" is something
            // the suite demonstrates rather than something a comment asserts.
            ["EdgeTrust__GatewayCertificateThumbprints"] = FakeGateway.CertificateHash,
        };

        foreach (KeyValuePair<string, string?> pair in overrides)
        {
            settings[pair.Key] = pair.Value;
        }

        _environment = new EnvironmentScope(settings);
    }

    /// <inheritdoc/>
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        ArgumentNullException.ThrowIfNull(builder);
    }

    /// <summary>
    /// Stamps every request with gateway provenance, as Container Apps ingress would.
    /// </summary>
    /// <remarks>
    /// Applied to the client rather than to each call so that a test about casing, cursors or
    /// problem details is not also a test about the edge. Provenance itself is asserted by
    /// <c>GatewayProvenanceTests</c>, which uses <see cref="CreateDirectClient"/> to arrive the way
    /// an attacker would.
    /// </remarks>
    /// <param name="client">The client being configured.</param>
    protected override void ConfigureClient(HttpClient client)
    {
        ArgumentNullException.ThrowIfNull(client);

        base.ConfigureClient(client);

        client.DefaultRequestHeaders.TryAddWithoutValidation(
            "X-Forwarded-Client-Cert",
            FakeGateway.ForwardedClientCert(FakeGateway.CertificateHash));
    }

    /// <summary>
    /// A client that reaches the application without going through the gateway.
    /// </summary>
    /// <remarks>
    /// This is the attacker's position, and the one the whole edge model exists to refuse: inside
    /// the network, addressing the container directly, free to send any header it likes.
    /// </remarks>
    /// <returns>A client with no forwarded certificate.</returns>
    public HttpClient CreateDirectClient()
    {
        HttpClient client = CreateClient();
        client.DefaultRequestHeaders.Remove("X-Forwarded-Client-Cert");
        return client;
    }

    /// <inheritdoc/>
    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);

        if (disposing)
        {
            _environment.Dispose();
        }
    }
}

/// <summary>Sets environment variables for the life of a test, then puts them back.</summary>
/// <remarks>
/// Restoration matters more than it looks: a leaked variable makes the <i>next</i> test pass or
/// fail for a reason that is nowhere in its own source, which is the worst kind of flake to chase.
/// </remarks>
internal sealed class EnvironmentScope : IDisposable
{
    private readonly Dictionary<string, string?> _previous = new(StringComparer.Ordinal);

    public EnvironmentScope(IReadOnlyDictionary<string, string?> settings)
    {
        ArgumentNullException.ThrowIfNull(settings);

        foreach (KeyValuePair<string, string?> pair in settings)
        {
            _previous[pair.Key] = Environment.GetEnvironmentVariable(pair.Key);
            Environment.SetEnvironmentVariable(pair.Key, pair.Value);
        }
    }

    public void Dispose()
    {
        foreach (KeyValuePair<string, string?> pair in _previous)
        {
            Environment.SetEnvironmentVariable(pair.Key, pair.Value);
        }

        _previous.Clear();
    }
}
