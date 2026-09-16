using Microsoft.Extensions.Options;

namespace Synthia.ContractTests;

/// <summary>
/// Configuration fails fast (T150, quickstart V17).
/// </summary>
/// <remarks>
/// <b>A missing required setting stops the process at start</b>, rather than surfacing as a null
/// three hours later on a path nobody tested (research R-019). That turns a latent configuration
/// defect into a failed deployment, which is where it is cheapest — and it means a container that
/// started is a container whose configuration is known good.
/// </remarks>
public sealed class ConfigurationValidationTests
{
    [Fact]
    public void A_missing_connection_string_stops_the_process_at_start()
    {
        using SynthiaApiFactory factory = Without("ReadDatabase__ConnectionString");

        OptionsValidationException failure = Assert.Throws<OptionsValidationException>(
            () => factory.CreateClient());

        Assert.Contains("ConnectionString", string.Join(" ", failure.Failures), StringComparison.Ordinal);
    }

    [Fact]
    public void An_empty_service_name_stops_the_process_at_start()
    {
        // Emptied rather than removed. The service name carries a working default, so absence is
        // legitimate; what is not legitimate is a deployment that configures it to nothing and
        // ships telemetry nobody can attribute. That is what [Required(AllowEmptyStrings = false)]
        // actually guarantees, so that is what is asserted.
        using SynthiaApiFactory factory = With("Observability__ServiceName", string.Empty);

        Assert.Throws<OptionsValidationException>(() => factory.CreateClient());
    }

    [Fact]
    public void A_vault_uri_that_is_not_https_stops_the_process_at_start()
    {
        // A secret fetched over plaintext is a secret in transit to anybody watching.
        using SynthiaApiFactory factory = With("KeyVault__VaultUri", "http://vault.example.com");

        Assert.Throws<OptionsValidationException>(() => factory.CreateClient());
    }

    [Fact]
    public void An_out_of_range_command_timeout_stops_the_process_at_start()
    {
        // Bounds are validated, not only presence. A setting that is present and absurd is the
        // harder failure to find, because everything starts and one query hangs.
        using SynthiaApiFactory factory = With("ReadDatabase__CommandTimeoutSeconds", "9000");

        Assert.Throws<OptionsValidationException>(() => factory.CreateClient());
    }

    [Fact]
    public void A_drain_shorter_than_the_longest_outbound_call_stops_the_process_at_start()
    {
        // The cross-setting rule: a drain must outlast the calls it has to drain, or an in-flight
        // request cannot finish inside it (plan Stage 10). Data annotations cannot express this, so
        // it is a Validate() predicate — and it is still checked at start, not at first use.
        using SynthiaApiFactory factory = With("ContainerApps__ShutdownTimeoutSeconds", "1");

        Assert.Throws<OptionsValidationException>(() => factory.CreateClient());
    }

    [Fact]
    public void A_fully_configured_process_starts()
    {
        // The negative tests above are only meaningful if the positive one holds: otherwise they
        // would pass against an application that could never start at all.
        using SynthiaApiFactory factory = new();
        using HttpClient client = factory.CreateClient();

        Assert.NotNull(client);
    }

    private static SynthiaApiFactory Without(string setting) =>
        new(new Dictionary<string, string?>(StringComparer.Ordinal) { [setting] = null });

    private static SynthiaApiFactory With(string setting, string value) =>
        new(new Dictionary<string, string?>(StringComparer.Ordinal) { [setting] = value });
}
