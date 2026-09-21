using System.Diagnostics;
using Azure.Monitor.OpenTelemetry.AspNetCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using OpenTelemetry;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

namespace Synthia.Observability;

/// <summary>
/// Wires traces, metrics and structured logging.
/// </summary>
/// <remarks>
/// Called once, from the composition root. Nothing here holds business policy — cross-cutting
/// concerns must not become the place a rule hides (.claude/rules/10-principles.md P-8).
/// </remarks>
public static class ObservabilityRegistration
{
    /// <summary>
    /// Adds OpenTelemetry tracing, metrics and logging, exporting to Azure Monitor.
    /// </summary>
    /// <param name="services">The service collection owned by the composition root.</param>
    /// <param name="configuration">
    /// The root's configuration. Resource attributes are fixed for the lifetime of the process and
    /// are needed while the pipeline is being built, before any container exists — so they are read
    /// here rather than resolved. This is composition-root code; the rule against reading raw
    /// configuration keys binds application and domain code, and everything that consumes these
    /// values at runtime does so through <c>IOptions</c>.
    /// </param>
    /// <returns>The same collection, for chaining.</returns>
    public static IServiceCollection AddSynthiaObservability(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);

        ObservabilityOptions resourceAttributes =
            configuration.GetSection(ObservabilityOptions.Section).Get<ObservabilityOptions>()
            ?? new ObservabilityOptions();

        // Validated here as well as through ValidateOnStart below, because these values are needed
        // while the pipeline is being built — before the container exists to validate anything.
        // Without this, an empty service name fails inside the OpenTelemetry resource builder with
        // "The value cannot be an empty string. (Parameter 'serviceName')", which names neither the
        // setting nor the file it came from. Fail-fast is only useful if the message is usable.
        RequireAtStartup(
            !string.IsNullOrWhiteSpace(resourceAttributes.ServiceName),
            $"{ObservabilityOptions.Section}:{nameof(ObservabilityOptions.ServiceName)} must be set.");
        RequireAtStartup(
            !string.IsNullOrWhiteSpace(resourceAttributes.DeploymentEnvironment),
            $"{ObservabilityOptions.Section}:{nameof(ObservabilityOptions.DeploymentEnvironment)} must be set.");

        services.AddOptions<ObservabilityOptions>()
            .BindConfiguration(ObservabilityOptions.Section)
            .ValidateDataAnnotations()
            .ValidateOnStart();

        // W3C Trace Context, explicitly. A custom propagation header MUST NOT replace it
        // (.claude/rules/40-testing.md §40.8), and setting this here rather than relying on the runtime
        // default means a later dependency cannot quietly switch the process to hierarchical ids.
        Activity.DefaultIdFormat = ActivityIdFormat.W3C;
        Activity.ForceDefaultIdFormat = true;

        services.AddSingleton<IConfigureOptions<OpenTelemetryLoggerOptions>, ConfigureSynthiaLogging>();

        // AlwaysOnSampler is a decision, not a default left in place. Sampling is tail-based and
        // keyed on the correlation identifier, so a journey that suspends and resumes hours later
        // is sampled as one unit (plan Stage 10). A head sampler decides at the first span, before
        // the journey is known to be interesting, and would routinely keep the request half of an
        // approval and discard the resume half — which is precisely what SC-OPS-001 forbids. Head
        // sampling is therefore prohibited here and the decision is deferred to the collector.
        services.AddOpenTelemetry()
            .ConfigureResource(resource => ConfigureResource(resourceAttributes, resource))
            .WithTracing(tracing => tracing
                .AddSource(SynthiaTelemetry.ActivitySourceName)
                .AddAspNetCoreInstrumentation(options => options.RecordException = true)
                .AddHttpClientInstrumentation()
                .SetSampler(new AlwaysOnSampler()))
            .WithMetrics(metrics => metrics
                .AddMeter(SynthiaTelemetry.MeterName)
                .AddAspNetCoreInstrumentation()
                .AddHttpClientInstrumentation()
                .AddRuntimeInstrumentation());

        services.AddOpenTelemetry().UseAzureMonitorWhenConfigured(resourceAttributes);

        return services;
    }

    private static OpenTelemetryBuilder UseAzureMonitorWhenConfigured(
        this OpenTelemetryBuilder builder,
        ObservabilityOptions options)
    {
        // No connection string means no exporter, rather than an exporter that fails at start.
        // Instrumentation is still collected either way — it simply has nowhere to go, which is
        // the developer-machine case ObservabilityOptions describes. Whether a deployed
        // environment may run this way is a deployment question, not one a running process can
        // answer about itself.
        if (string.IsNullOrWhiteSpace(options.AzureMonitorConnectionString))
        {
            return builder;
        }

        // Bound through IConfigureOptions rather than passed as a literal, so the exporter's
        // connection string follows the same Key Vault path as every other secret and picks up a
        // rotation without a redeploy.
        builder.Services.AddSingleton<IConfigureOptions<AzureMonitorOptions>, ConfigureAzureMonitor>();
        builder.UseAzureMonitor();

        return builder;
    }

    private static void RequireAtStartup(bool satisfied, string failure)
    {
        if (!satisfied)
        {
            throw new OptionsValidationException(
                Options.DefaultName,
                typeof(ObservabilityOptions),
                [failure]);
        }
    }

    private static void ConfigureResource(ObservabilityOptions options, ResourceBuilder resource)
    {
        resource
            .AddService(options.ServiceName)
            .AddAttributes(
            [
                new KeyValuePair<string, object>("deployment.environment", options.DeploymentEnvironment),
            ]);
    }

    private sealed class ConfigureAzureMonitor : IConfigureOptions<AzureMonitorOptions>
    {
        private readonly IOptions<ObservabilityOptions> _observability;

        public ConfigureAzureMonitor(IOptions<ObservabilityOptions> observability)
        {
            ArgumentNullException.ThrowIfNull(observability);

            _observability = observability;
        }

        public void Configure(AzureMonitorOptions options)
        {
            ArgumentNullException.ThrowIfNull(options);

            options.ConnectionString = _observability.Value.AzureMonitorConnectionString;
        }
    }

    private sealed class ConfigureSynthiaLogging : IConfigureOptions<OpenTelemetryLoggerOptions>
    {
        public void Configure(OpenTelemetryLoggerOptions options)
        {
            ArgumentNullException.ThrowIfNull(options);

            // Scopes carry the correlation identifier onto every record written inside them, which
            // is what makes one request followable across tiers without threading an argument
            // through every signature.
            options.IncludeScopes = true;

            // Formatted messages are NOT included. The template stays constant and the values stay
            // structured attributes, which is what makes a log searchable — and it keeps a
            // customer value out of a pre-rendered string that a sink might index differently from
            // the attribute it came from.
            options.IncludeFormattedMessage = false;
            options.ParseStateValues = true;
        }
    }
}
