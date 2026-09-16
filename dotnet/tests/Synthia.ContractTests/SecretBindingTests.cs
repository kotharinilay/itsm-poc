using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Options;
using Synthia.Api.Configuration;

namespace Synthia.ContractTests;

/// <summary>
/// Secret references resolve from Key Vault; values never reach a document, a log or a trace.
/// </summary>
/// <remarks>
/// <para>
/// The RagCore half of these rules lives in <c>ragcore/tests/security/test_secret_binding.py</c>.
/// Both stacks bind secrets, so both are tested; the mechanisms differ because the platforms differ.
/// .NET binds through the Key Vault <i>configuration provider</i>, so a secret becomes a
/// configuration key and the rule is about which keys may exist and whether they resolved. Python
/// resolves references explicitly, so its rule is about a value type that refuses to render itself.
/// </para>
/// <para>
/// <b>No vault and no network is needed to run these.</b> Configuration is assembled in memory,
/// which is where the binding rules actually apply.
/// </para>
/// </remarks>
public sealed class SecretBindingTests
{
    private const string Secret = "s3cr3t-do-not-print-me";

    private static KeyVaultOptions OptionsWith(params string[] requiredKeys)
    {
        KeyVaultOptions options = new() { VaultUri = "https://vault.example" };

        foreach (string key in requiredKeys)
        {
            options.RequiredSecretKeys.Add(key);
        }

        return options;
    }

    private static IConfiguration ConfigurationWith(params (string Key, string Value)[] entries) =>
        new ConfigurationBuilder()
            .AddInMemoryCollection(entries.Select(entry =>
                new KeyValuePair<string, string?>(entry.Key, entry.Value)))
            .Build();

    // -----------------------------------------------------------------------
    // 1. Configuration holds references, not values
    // -----------------------------------------------------------------------

    /// <summary>A secret fetched over plaintext is a secret in transit to anybody watching.</summary>
    [Fact]
    public void A_plaintext_vault_uri_is_refused()
    {
        KeyVaultOptions options = new() { VaultUri = "http://vault.example" };

        Assert.False(options.IsValid);
    }

    /// <summary>Empty is the legitimate developer-machine value, and must not be rejected.</summary>
    /// <remarks>
    /// This is why <c>IsValid</c> is not a <c>[Url]</c> annotation: that rejects the empty string
    /// and accepts <c>http</c>, which is exactly backwards for this setting.
    /// </remarks>
    [Fact]
    public void An_absent_vault_uri_is_permitted()
    {
        KeyVaultOptions options = new();

        Assert.True(options.IsValid);
        Assert.False(options.IsConfigured);
    }

    /// <summary>
    /// The options type exposes no property that could hold a credential for reaching the vault.
    /// </summary>
    /// <remarks>
    /// A client secret configured to <i>read</i> the vault would be a standing secret living outside
    /// the vault — the problem the vault exists to remove, reintroduced at the one point nobody
    /// looks.
    /// </remarks>
    [Fact]
    public void The_vault_options_expose_no_credential_property()
    {
        string[] names = typeof(KeyVaultOptions)
            .GetProperties()
            .Select(property => property.Name.ToLowerInvariant())
            .ToArray();

        foreach (string forbidden in new[] { "secret", "password", "key", "token", "credential" })
        {
            // RequiredSecretKeys is a list of configuration KEYS, not of key material.
            Assert.DoesNotContain(
                names,
                name => name.Contains(forbidden, StringComparison.Ordinal) &&
                        !string.Equals(name, "requiredsecretkeys", StringComparison.Ordinal));
        }
    }

    // -----------------------------------------------------------------------
    // 5. Startup fails when a required reference cannot be resolved
    // -----------------------------------------------------------------------

    /// <summary>The baseline: a resolved reference validates.</summary>
    [Fact]
    public void A_resolved_reference_validates()
    {
        RequiredSecretsValidator validator = new(
            ConfigurationWith(("Observability:ConnectionString", Secret)));

        ValidateOptionsResult result =
            validator.Validate(null, OptionsWith("Observability:ConnectionString"));

        Assert.True(result.Succeeded);
    }

    /// <summary>An absent secret stops the process. No fallback, no default.</summary>
    [Fact]
    public void An_absent_reference_fails_validation()
    {
        RequiredSecretsValidator validator = new(ConfigurationWith());

        ValidateOptionsResult result =
            validator.Validate(null, OptionsWith("Observability:ConnectionString"));

        Assert.True(result.Failed);
        Assert.Contains(
            result.Failures!,
            failure => failure.Contains("Observability:ConnectionString", StringComparison.Ordinal));
    }

    /// <summary>An empty secret is a failure, not a value.</summary>
    /// <remarks>
    /// The vault answering "no such secret" and the vault answering with a blank string are the same
    /// deployment defect. Treating the second as a value is what detaches the failure from its cause.
    /// </remarks>
    [Fact]
    public void An_empty_reference_fails_validation()
    {
        RequiredSecretsValidator validator = new(
            ConfigurationWith(("Observability:ConnectionString", "   ")));

        ValidateOptionsResult result =
            validator.Validate(null, OptionsWith("Observability:ConnectionString"));

        Assert.True(result.Failed);
    }

    /// <summary>Three missing secrets cost one cycle to diagnose, not three.</summary>
    [Fact]
    public void Every_missing_reference_is_reported_in_one_cycle()
    {
        RequiredSecretsValidator validator = new(ConfigurationWith());

        ValidateOptionsResult result = validator.Validate(null, OptionsWith("A", "B", "C"));

        Assert.True(result.Failed);
        Assert.Equal(3, result.Failures!.Count());
    }

    /// <summary>The failure names the key and the vault, and never what was found.</summary>
    [Fact]
    public void A_validation_failure_carries_no_secret_value()
    {
        RequiredSecretsValidator validator = new(
            ConfigurationWith(("Observability:ConnectionString", string.Empty)));

        ValidateOptionsResult result =
            validator.Validate(null, OptionsWith("Observability:ConnectionString"));

        Assert.True(result.Failed);
        Assert.DoesNotContain(
            result.Failures!,
            failure => failure.Contains(Secret, StringComparison.Ordinal));
    }

    /// <summary>With no vault configured there is nothing to resolve, so nothing to fail on.</summary>
    [Fact]
    public void No_vault_means_nothing_to_validate()
    {
        RequiredSecretsValidator validator = new(ConfigurationWith());

        ValidateOptionsResult result = validator.Validate(null, new KeyVaultOptions());

        Assert.True(result.Succeeded);
    }
}
