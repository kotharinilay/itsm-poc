using Microsoft.Extensions.Options;

namespace Synthia.Api.Configuration;

/// <summary>
/// Startup fails when a required secret reference does not resolve to a value.
/// </summary>
/// <remarks>
/// <para>
/// <b>Adding Key Vault as a configuration source does not prove anything resolved.</b>
/// <c>AddAzureKeyVault</c> succeeds when the vault is reachable, whether or not the secrets this
/// process actually needs are in it. A secret that is absent, or present and empty, then binds to
/// <see cref="string.Empty"/> and passes every annotation that does not happen to be
/// <c>[Required]</c> — surfacing hours later as an authentication failure somewhere unrelated, with
/// nothing pointing back here.
/// </para>
/// <para>
/// <b>An empty value is a failure, not a value.</b> That is the whole point of this type: the vault
/// answering "I have no such secret" and the vault answering with a blank string are the same
/// deployment defect, and neither should start.
/// </para>
/// <para>
/// <b>Every missing reference is reported in one cycle</b> rather than stopping at the first. A
/// deployment with three missing secrets should cost one cycle to diagnose, not three.
/// </para>
/// <para>
/// <b>No value is ever included in a message.</b> The failure names the configuration key and the
/// vault; it never echoes what was found, including when what was found was almost right.
/// </para>
/// </remarks>
public sealed class RequiredSecretsValidator : IValidateOptions<KeyVaultOptions>
{
    private readonly IConfiguration _configuration;

    /// <summary>Creates the validator.</summary>
    /// <param name="configuration">The assembled configuration, Key Vault included.</param>
    public RequiredSecretsValidator(IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(configuration);

        _configuration = configuration;
    }

    /// <summary>Validates that every required secret reference resolved.</summary>
    /// <param name="name">The options name. Unused; these options are not named.</param>
    /// <param name="options">The bound options.</param>
    /// <returns>Success, or a failure naming every key that did not resolve.</returns>
    public ValidateOptionsResult Validate(string? name, KeyVaultOptions options)
    {
        ArgumentNullException.ThrowIfNull(options);

        // With no vault configured there is nothing to resolve from, which is the developer-machine
        // case. A deployed environment without a vault is a deployment defect and the pipeline is
        // what catches it: a running process cannot tell which environment it wishes it were in.
        if (!options.IsConfigured || options.RequiredSecretKeys.Count == 0)
        {
            return ValidateOptionsResult.Success;
        }

        List<string> unresolved = options.RequiredSecretKeys
            .Where(key => string.IsNullOrWhiteSpace(_configuration[key]))
            .ToList();

        if (unresolved.Count == 0)
        {
            return ValidateOptionsResult.Success;
        }

        return ValidateOptionsResult.Fail(
            unresolved.Select(key =>
                "Required secret reference '" + key + "' did not resolve from " + options.VaultUri +
                ". Configuration holds secret names; the values live in Key Vault and are resolved " +
                "through managed identity at startup. An absent secret and an empty one are the " +
                "same deployment defect."));
    }
}
