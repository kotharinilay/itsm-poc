using Microsoft.AspNetCore.Mvc;
using Synthia.Api.Middleware;
using Synthia.Contracts.Errors;
using Synthia.SharedKernel.Identity;

namespace Synthia.Api.Errors;

/// <summary>
/// Builds the RFC 9457 responses this deployable emits.
/// </summary>
/// <remarks>
/// <b>Every problem a client sees comes from here</b>, which is what makes "internal exception
/// detail MUST NEVER reach a client" checkable rather than reviewed. Each factory takes a
/// client-safe <c>detail</c> written for the reader; none takes an exception.
/// </remarks>
internal static class Problems
{
    /// <summary>The media type every problem response carries.</summary>
    public const string MediaType = "application/problem+json";

    /// <summary>Input failed validation at the boundary.</summary>
    /// <param name="context">The request, for the instance and correlation values.</param>
    /// <param name="detail">A client-safe explanation.</param>
    /// <returns>A 400 problem response.</returns>
    public static IResult ValidationFailed(HttpContext context, string detail) =>
        Build(context, ProblemTypes.ValidationFailed, "Validation failed", StatusCodes.Status400BadRequest, detail);

    /// <summary>The request carried no usable identity context.</summary>
    /// <param name="context">The request.</param>
    /// <param name="detail">A client-safe explanation.</param>
    /// <returns>A 401 problem response.</returns>
    public static IResult Unauthenticated(HttpContext context, string detail) =>
        Build(context, ProblemTypes.Unauthenticated, "Unauthenticated", StatusCodes.Status401Unauthorized, detail);

    /// <summary>The principal holds no role this operation accepts.</summary>
    /// <param name="context">The request.</param>
    /// <param name="detail">A client-safe explanation.</param>
    /// <returns>A 403 problem response.</returns>
    public static IResult Forbidden(HttpContext context, string detail) =>
        Build(context, ProblemTypes.Forbidden, "Forbidden", StatusCodes.Status403Forbidden, detail);

    /// <summary>
    /// The resource does not exist, or does not exist for this caller.
    /// </summary>
    /// <remarks>
    /// Used <b>where existence itself is tenant-scoped information</b>. Returning 403 for another
    /// organisation's resource would confirm that it exists, which is a cross-organisation
    /// disclosure in its own right.
    /// </remarks>
    /// <param name="context">The request.</param>
    /// <returns>A 404 problem response.</returns>
    public static IResult NotFound(HttpContext context) =>
        Build(
            context,
            ProblemTypes.NotFound,
            "Not found",
            StatusCodes.Status404NotFound,
            "No such resource.");

    /// <summary>An unexpected fault. Carries no internal detail.</summary>
    /// <param name="context">The request.</param>
    /// <returns>A 500 problem response.</returns>
    public static IResult Unexpected(HttpContext context) =>
        Build(
            context,
            ProblemTypes.Unexpected,
            "Unexpected error",
            StatusCodes.Status500InternalServerError,
            "The request could not be completed. Quote the correlation identifier when reporting this.");

    /// <summary>Renders a problem as the payload written directly to a response.</summary>
    /// <param name="context">The request.</param>
    /// <param name="type">A <see cref="ProblemTypes"/> URI.</param>
    /// <param name="title">A short, client-safe summary.</param>
    /// <param name="status">The HTTP status code.</param>
    /// <param name="detail">A client-safe explanation.</param>
    /// <returns>The problem document.</returns>
    public static ProblemDetails Document(
        HttpContext context,
        string type,
        string title,
        int status,
        string detail)
    {
        ArgumentNullException.ThrowIfNull(context);

        ProblemDetails problem = new()
        {
            Type = type,
            Title = title,
            Status = status,
            Detail = detail,
            Instance = context.Request.Path.Value,
        };

        problem.Extensions["correlationId"] = CorrelationOf(context);

        return problem;
    }

    private static IResult Build(
        HttpContext context,
        string type,
        string title,
        int status,
        string detail) =>
        Results.Problem(Document(context, type, title, status, detail));

    private static string CorrelationOf(HttpContext context)
    {
        // Read from the response header rather than the scope: the header is already set by the
        // time any problem can be produced, and a problem raised while the scope is half-built
        // should still be traceable.
        string? correlation = context.Response.Headers[CorrelationMiddleware.HeaderName].FirstOrDefault();

        return string.IsNullOrEmpty(correlation) ? CorrelationId.New().Value : correlation;
    }
}
