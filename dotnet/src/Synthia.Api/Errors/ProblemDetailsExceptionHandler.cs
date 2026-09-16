using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using Synthia.Contracts.Errors;

namespace Synthia.Api.Errors;

/// <summary>
/// Turns an unhandled exception into an RFC 9457 response that says nothing it should not.
/// </summary>
/// <remarks>
/// <para>
/// <b>Internal exception detail MUST NEVER reach a client</b> (constitution §Validation and
/// errors). The exception is logged in full, with the correlation identifier; the client receives a
/// problem type, a title, and that identifier. That pairing is the whole design — the client can
/// report a problem precisely without being told anything about the inside of the process.
/// </para>
/// <para>
/// Note what is absent: no <c>switch</c> on exception type mapping internal failures onto helpful
/// status codes. Expected outcomes are Result-shaped and handled at the endpoint; anything
/// reaching here is genuinely exceptional and a 500 is the honest answer (constitution §Validation
/// and errors).
/// </para>
/// </remarks>
internal sealed class ProblemDetailsExceptionHandler : IExceptionHandler
{
    private readonly ILogger<ProblemDetailsExceptionHandler> _logger;

    /// <summary>Creates the handler.</summary>
    /// <param name="logger">Structured logger.</param>
    public ProblemDetailsExceptionHandler(ILogger<ProblemDetailsExceptionHandler> logger)
    {
        ArgumentNullException.ThrowIfNull(logger);

        _logger = logger;
    }

    /// <inheritdoc/>
    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(httpContext);
        ArgumentNullException.ThrowIfNull(exception);

        if (exception is OperationCanceledException && cancellationToken.IsCancellationRequested)
        {
            // The caller went away, or the container is draining. Not a fault, and emitting a 500
            // for it would turn a normal scale-in into an error-rate spike. Cancellation is never
            // swallowed — it is recognised, recorded and allowed to end the request.
            ErrorLog.RequestCancelled(_logger);
            return false;
        }

        ErrorLog.Unhandled(_logger, exception);

        ProblemDetails problem = Problems.Document(
            httpContext,
            ProblemTypes.Unexpected,
            "Unexpected error",
            StatusCodes.Status500InternalServerError,
            "The request could not be completed. Quote the correlation identifier when reporting this.");

        httpContext.Response.StatusCode = StatusCodes.Status500InternalServerError;
        httpContext.Response.ContentType = Problems.MediaType;

        await httpContext.Response
            .WriteAsJsonAsync(problem, JsonConventions.Options, Problems.MediaType, cancellationToken)
            .ConfigureAwait(false);

        return true;
    }
}

/// <summary>Log messages for unhandled failures.</summary>
internal static partial class ErrorLog
{
    /// <summary>Records an unhandled exception in full, on the server side only.</summary>
    /// <param name="logger">The logger.</param>
    /// <param name="exception">The exception.</param>
    [LoggerMessage(
        EventId = 1201,
        Level = LogLevel.Error,
        Message = "Unhandled exception while serving a request.")]
    public static partial void Unhandled(ILogger logger, Exception exception);

    /// <summary>Records a request that ended because it was cancelled.</summary>
    /// <param name="logger">The logger.</param>
    [LoggerMessage(
        EventId = 1202,
        Level = LogLevel.Debug,
        Message = "Request cancelled by the caller or by shutdown.")]
    public static partial void RequestCancelled(ILogger logger);
}
