using System.Diagnostics;
using Synthia.Observability;
using Synthia.SharedKernel.Identity;

namespace Synthia.Api.Middleware;

/// <summary>
/// Establishes the correlation identifier for a request, before anything logs.
/// </summary>
/// <remarks>
/// <para>
/// <b>Accepted only when well formed; generated when missing or invalid; echoed in the response</b>
/// (constitution §Correlation). An arriving value is client input: it is validated, never trusted
/// for authority, and never used as a key for anything.
/// </para>
/// <para>
/// This runs <b>before</b> request logging, which is what makes every record of a request carry
/// its identifier — including the record of the request failing.
/// </para>
/// </remarks>
internal sealed class CorrelationMiddleware
{
    /// <summary>The header a correlation identifier arrives and departs on.</summary>
    public const string HeaderName = "X-Correlation-Id";

    private readonly RequestDelegate _next;
    private readonly ILogger<CorrelationMiddleware> _logger;

    /// <summary>Creates the middleware.</summary>
    /// <param name="next">The next component in the pipeline.</param>
    /// <param name="logger">Structured logger.</param>
    public CorrelationMiddleware(RequestDelegate next, ILogger<CorrelationMiddleware> logger)
    {
        ArgumentNullException.ThrowIfNull(next);
        ArgumentNullException.ThrowIfNull(logger);

        _next = next;
        _logger = logger;
    }

    /// <summary>Binds the correlation identifier and runs the rest of the pipeline.</summary>
    /// <param name="context">The request.</param>
    /// <param name="scope">The per-request correlation holder.</param>
    /// <returns>A task that completes when the pipeline does.</returns>
    public async Task InvokeAsync(HttpContext context, ICorrelationScopeWriter scope)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(scope);

        string? supplied = context.Request.Headers[HeaderName].FirstOrDefault();

        if (!CorrelationId.TryAccept(supplied, out CorrelationId correlationId))
        {
            correlationId = CorrelationId.New();

            if (!string.IsNullOrEmpty(supplied))
            {
                // Logged at the moment of replacement, because the identifier the client used to
                // find this request is not the one the rest of the trail carries. Without this,
                // "my correlation id returns nothing" has no explanation anywhere.
                CorrelationLog.Replaced(_logger);
            }
        }

        scope.Bind(correlationId);

        context.Response.Headers[HeaderName] = correlationId.Value;

        // Onto the trace as a tag and as baggage. The tag makes this request findable; the baggage
        // carries it to whatever this request talks to. Baggage crosses boundaries in cleartext, so
        // only the explicitly allowed values go in it (constitution Principle VIII).
        Activity? activity = Activity.Current;
        activity?.SetTag(SynthiaTelemetry.CorrelationTag, correlationId.Value);
        activity?.SetBaggage(SynthiaTelemetry.CorrelationTag, correlationId.Value);

        using IDisposable? loggingScope = _logger.BeginScope(
            new Dictionary<string, object> { [SynthiaTelemetry.CorrelationTag] = correlationId.Value });

        await _next(context).ConfigureAwait(false);
    }
}

/// <summary>Log messages for correlation handling.</summary>
/// <remarks>
/// Source-generated. Correlation runs on every request, which makes it a high-volume path and
/// exactly what <c>LoggerMessage</c> generation exists for (constitution §Logging).
/// </remarks>
internal static partial class CorrelationLog
{
    /// <summary>
    /// Records that a supplied identifier was rejected and replaced.
    /// </summary>
    /// <remarks>
    /// <b>The rejected value is deliberately not logged.</b> It is unvalidated client input on a
    /// path that reaches a log sink, and a malformed correlation identifier is exactly the shape a
    /// log-injection attempt arrives in.
    /// </remarks>
    /// <param name="logger">The logger.</param>
    [LoggerMessage(
        EventId = 1001,
        Level = LogLevel.Debug,
        Message = "Replaced a malformed correlation identifier supplied by the client.")]
    public static partial void Replaced(ILogger logger);
}
