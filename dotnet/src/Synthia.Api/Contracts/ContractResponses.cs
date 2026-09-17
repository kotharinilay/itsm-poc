using Synthia.Contracts.Errors;

namespace Synthia.Api.Contracts;

/// <summary>
/// Declares what a route returns, so the emitted document carries it.
/// </summary>
/// <remarks>
/// <para>
/// Every handler in this deployable returns <see cref="IResult"/>, which is the right type for a
/// method that answers with a body on one path and a problem on another — and is a type the OpenAPI
/// generator can infer nothing from. Left alone, every operation published a bare
/// <c>200: OK</c> with no schema and no error responses: a document that named the routes and
/// described none of them.
/// </para>
/// <para>
/// <b>These are declarations, not definitions.</b> The success type is the read model the handler
/// already returns and <see cref="ProblemContract"/> is the error contract
/// <see cref="Errors.Problems"/> already builds — the same types, named once more where the
/// generator can see them. Nothing here describes a shape that is written down anywhere else.
/// </para>
/// <para>
/// <b>The error set is the same on every route, because the pipeline is.</b> 401 and 403 come from
/// the identity middleware before the handler runs, 500 from the exception handler after it, and
/// 404 is how a resource belonging to another organisation is reported — existence is itself
/// tenant-scoped information, so the answer is 404 and never 403. Publishing a narrower set per
/// route would describe a pipeline this deployable does not have.
/// </para>
/// </remarks>
internal static class ContractResponses
{
    /// <summary>The media type every problem response carries (RFC 9457).</summary>
    private const string ProblemMediaType = "application/problem+json";

    /// <summary>
    /// Declares the success body and the full RFC 9457 error contract for a route.
    /// </summary>
    /// <typeparam name="TBody">The type returned on success.</typeparam>
    /// <param name="builder">The route being built.</param>
    /// <returns>The same builder, for chaining.</returns>
    public static RouteHandlerBuilder Returns<TBody>(this RouteHandlerBuilder builder)
    {
        ArgumentNullException.ThrowIfNull(builder);

        return builder
            .Produces<TBody>(StatusCodes.Status200OK)
            .Produces<ProblemContract>(StatusCodes.Status400BadRequest, ProblemMediaType)
            .Produces<ProblemContract>(StatusCodes.Status401Unauthorized, ProblemMediaType)
            .Produces<ProblemContract>(StatusCodes.Status403Forbidden, ProblemMediaType)
            .Produces<ProblemContract>(StatusCodes.Status404NotFound, ProblemMediaType)
            .Produces<ProblemContract>(StatusCodes.Status500InternalServerError, ProblemMediaType);
    }
}
