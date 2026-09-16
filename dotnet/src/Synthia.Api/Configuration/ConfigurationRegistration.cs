using Azure.Extensions.AspNetCore.Configuration.Secrets;
using Azure.Identity;
using Microsoft.Extensions.Options;
using Synthia.Api.Http;

namespace Synthia.Api.Configuration;

/// <summary>
/// Binds and validates every option this deployable reads, and wires the Key Vault source.
/// </summary>
/// <remarks>
/// <para>
/// <b>A missing or malformed setting stops the process at start</b> (research R-019).
/// <c>ValidateOnStart()</c> turns a latent configuration defect into a failed deployment, which is
/// where it is cheapest — rather than a null three hours later on a path nobody tested.
/// </para>
/// <para>
/// Application and domain code MUST NOT read <c>Configuration["Foo:Bar"]</c>. Everything past this
/// file consumes <c>IOptions&lt;T&gt;</c>.
/// </para>
/// </remarks>
internal static class ConfigurationRegistration
{
    /// <summary>
    /// Adds Key Vault as a configuration source when one is configured.
    /// </summary>
    /// <remarks>
    /// Ordering matters and is fixed by the constitution: <c>appsettings.json</c>, then
    /// <c>appsettings.{Environment}.json</c>, then environment variables, then secret references —
    /// later overriding earlier. The vault is added last so a secret always wins over a placeholder
    /// left in a file.
    /// </remarks>
    /// <param name="builder">The host builder being configured.</param>
    /// <returns>The Key Vault options that were applied.</returns>
    public static KeyVaultOptions AddSynthiaKeyVault(this WebApplicationBuilder builder)
    {
        ArgumentNullException.ThrowIfNull(builder);

        KeyVaultOptions options =
            builder.Configuration.GetSection(KeyVaultOptions.Section).Get<KeyVaultOptions>()
            ?? new KeyVaultOptions();

        if (!options.IsConfigured)
        {
            return options;
        }

        // Validated here as well as through ValidateOnStart, because the source is added while the
        // configuration is still being assembled — before the container exists to validate
        // anything. Without this, a plaintext URI fails inside the Azure SDK with "Bearer token
        // authentication is not permitted for non TLS protected (https) endpoints", which names
        // neither the setting nor the file it came from.
        if (!options.IsValid)
        {
            throw new OptionsValidationException(
                Options.DefaultName,
                typeof(KeyVaultOptions),
                [$"{KeyVaultOptions.Section}:{nameof(KeyVaultOptions.VaultUri)} must be an " +
                 "absolute https URI. Secret material is not fetched over plaintext."]);
        }

        // DefaultAzureCredential resolves the managed identity in Container Apps and the developer's
        // own signed-in identity locally. Zero standing secrets either way: nothing this process
        // holds can be exfiltrated and replayed, because it holds nothing.
        builder.Configuration.AddAzureKeyVault(
            new Uri(options.VaultUri),
            new DefaultAzureCredential(),
            new AzureKeyVaultConfigurationOptions
            {
                ReloadInterval = TimeSpan.FromMinutes(options.ReloadIntervalMinutes),
            });

        return options;
    }

    /// <summary>
    /// Registers every options type, bound and validated at start.
    /// </summary>
    /// <param name="services">The service collection owned by the composition root.</param>
    /// <returns>The same collection, for chaining.</returns>
    public static IServiceCollection AddSynthiaConfiguration(this IServiceCollection services)
    {
        ArgumentNullException.ThrowIfNull(services);

        services.AddOptions<KeyVaultOptions>()
            .BindConfiguration(KeyVaultOptions.Section)
            .ValidateDataAnnotations()
            .Validate(
                options => options.IsValid,
                "KeyVault:VaultUri must be an absolute https URI when set. Secret material is not " +
                "fetched over plaintext.")
            .ValidateOnStart();

        services.AddOptions<ContainerAppsOptions>()
            .BindConfiguration(ContainerAppsOptions.Section)
            .ValidateDataAnnotations()
            .Validate(
                options => options.ShutdownTimeout >= OutboundHttpDefaults.TotalTimeout,
                "The drain period must be at least as long as the longest outbound call this " +
                "process can make, or a request in flight cannot finish inside it. An execution " +
                "that cannot finish inside the drain is one whose timeout was set wrong " +
                "(plan Stage 10).")
            .ValidateOnStart();

        // The host's own drain must match the platform's, or the two disagree about how long an
        // in-flight request has. A host that gives up sooner drops requests Container Apps was
        // still waiting for; one that gives up later is killed mid-request anyway (plan Stage 10).
        services.AddSingleton<IConfigureOptions<HostOptions>, ConfigureShutdownTimeout>();

        // ReadDatabaseOptions and ObservabilityOptions are registered by the components that own
        // them — Synthia.Persistence and Synthia.Observability. Each binds and validates its own
        // section, so a component cannot be added without its configuration being checked too.
        return services;
    }

    private sealed class ConfigureShutdownTimeout : IConfigureOptions<HostOptions>
    {
        private readonly IOptions<ContainerAppsOptions> _runtime;

        public ConfigureShutdownTimeout(IOptions<ContainerAppsOptions> runtime)
        {
            ArgumentNullException.ThrowIfNull(runtime);

            _runtime = runtime;
        }

        public void Configure(HostOptions options)
        {
            ArgumentNullException.ThrowIfNull(options);

            options.ShutdownTimeout = _runtime.Value.ShutdownTimeout;
        }
    }
}
