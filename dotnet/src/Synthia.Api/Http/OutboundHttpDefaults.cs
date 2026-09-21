using Microsoft.Extensions.Http.Resilience;

namespace Synthia.Api.Http;

/// <summary>
/// The resilience and timeout policy every outbound HTTP client in this deployable inherits.
/// </summary>
/// <remarks>
/// <para>
/// <b>This is a default, not an abstraction.</b> It configures clients rather than wrapping them,
/// which is why it is here despite the monolith currently creating none: it costs nothing while
/// there are no clients, and it means the first typed client someone adds is already correct
/// rather than correct-if-they-remembered.
/// </para>
/// <para>
/// <c>HttpClient</c> MUST NOT be instantiated manually and one-off unmanaged clients MUST NOT be
/// created (.claude/rules/20-dotnet.md BL-28). Manual instantiation causes socket exhaustion and stale DNS;
/// <c>IHttpClientFactory</c> pools handlers and recycles them. <c>NoManualHttpClientTests</c>
/// asserts nobody does it anyway.
/// </para>
/// <para>
/// <b>Every outbound call carries an explicit timeout.</b> That rule is specific to this platform:
/// work runs inside a fifteen-minute validity window, and one call without a timeout can hold work
/// past its expiry — turning a slow dependency into an expired approval (research R-020).
/// </para>
/// </remarks>
internal static class OutboundHttpDefaults
{
    /// <summary>The ceiling on a single attempt, including its handler chain.</summary>
    public static TimeSpan AttemptTimeout { get; } = TimeSpan.FromSeconds(8);

    /// <summary>
    /// The ceiling on a call including every retry.
    /// </summary>
    /// <remarks>
    /// <b>Shorter than the 25-second drain, and that is the constraint that sets it.</b> A call
    /// that can outlive the drain is a call that can be killed mid-flight on a scale-in, and the
    /// plan is explicit that an execution which cannot finish inside the drain is one whose timeout
    /// was set wrong (plan Stage 10). <c>ConfigurationRegistration</c> validates the relationship
    /// at start, so raising this past the drain fails the deployment rather than a request.
    /// </remarks>
    public static TimeSpan TotalTimeout { get; } = TimeSpan.FromSeconds(20);

    /// <summary>Applies the standard handler to every client the factory creates.</summary>
    /// <param name="services">The service collection owned by the composition root.</param>
    /// <returns>The same collection, for chaining.</returns>
    public static IServiceCollection AddSynthiaHttpDefaults(this IServiceCollection services)
    {
        ArgumentNullException.ThrowIfNull(services);

        services.ConfigureHttpClientDefaults(builder =>
        {
            // The standard handler distinguishes transient from non-transient failure for us:
            // it retries 5xx, 408 and timeouts, and does not retry a 400 or a 403. Retrying a
            // non-transient failure is how a bad request becomes five bad requests.
            builder.AddStandardResilienceHandler(options =>
            {
                options.AttemptTimeout.Timeout = AttemptTimeout;
                options.TotalRequestTimeout.Timeout = TotalTimeout;

                // The circuit breaker's sampling window must exceed the attempt timeout, or a
                // single slow call can fill the window on its own.
                options.CircuitBreaker.SamplingDuration = TimeSpan.FromSeconds(AttemptTimeout.TotalSeconds * 2);
            });
        });

        return services;
    }
}
