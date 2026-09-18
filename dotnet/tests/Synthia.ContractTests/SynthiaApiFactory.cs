using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;

namespace Synthia.ContractTests;

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
