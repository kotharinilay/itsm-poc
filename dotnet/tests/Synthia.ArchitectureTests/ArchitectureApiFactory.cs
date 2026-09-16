using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;

namespace Synthia.ArchitectureTests;

/// <summary>
/// Boots the application so the routing table can be walked.
/// </summary>
/// <remarks>
/// Configuration arrives as environment variables because under minimal hosting the application
/// reads its configuration in top-level statements, which run before a factory's configuration
/// callbacks do. See <c>Synthia.ContractTests.SynthiaApiFactory</c> for the same reasoning; the two
/// suites are separate assemblies and each carries its own copy rather than sharing a test helper
/// project that neither owns.
/// </remarks>
internal sealed class ArchitectureApiFactory : WebApplicationFactory<Program>
{
    private readonly Dictionary<string, string?> _previous = new(StringComparer.Ordinal);

    public ArchitectureApiFactory()
    {
        Dictionary<string, string?> settings = new(StringComparer.Ordinal)
        {
            ["ASPNETCORE_ENVIRONMENT"] = "Development",
            ["ReadDatabase__ConnectionString"] =
                "Host=architecture-tests.invalid;Port=5432;Database=synthia;Username=reader;Password=unused",
            ["Observability__ServiceName"] = "synthia-monolith-architecture-tests",
            ["Observability__DeploymentEnvironment"] = "test",

            // Required, and with no empty state: a process that cannot prove gateway provenance
            // does not start. These tests only walk the routing table, but they walk it on a
            // genuinely booted application — so they configure it the way a deployment must.
            // A syntactically valid hash belonging to no real certificate, and not a credential.
            ["EdgeTrust__GatewayCertificateThumbprints"] =
                "1111111111111111111111111111111111111111111111111111111111111111",
        };

        foreach (KeyValuePair<string, string?> pair in settings)
        {
            _previous[pair.Key] = Environment.GetEnvironmentVariable(pair.Key);
            Environment.SetEnvironmentVariable(pair.Key, pair.Value);
        }
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        ArgumentNullException.ThrowIfNull(builder);
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);

        if (!disposing)
        {
            return;
        }

        foreach (KeyValuePair<string, string?> pair in _previous)
        {
            Environment.SetEnvironmentVariable(pair.Key, pair.Value);
        }

        _previous.Clear();
    }
}
