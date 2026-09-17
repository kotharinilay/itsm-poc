using Synthia.Api.Contracts;
using Synthia.Contracts.Querying;

namespace Synthia.Api.Querying;

/// <summary>
/// Declares a route's query contract once, where both the binder and the document read it.
/// </summary>
/// <remarks>
/// <para>
/// Before this existed the whitelist was named inside the handler and the OpenAPI document knew
/// nothing about it, so the published contract advertised no way to page or filter a collection the
/// endpoint only ever serves a page of. Restating the fields in a document transformer would have
/// fixed the document and introduced the drift the generated-contract rule exists to prevent.
/// </para>
/// <para>
/// So the whitelist moves onto the endpoint as metadata and the handler resolves it from there. The
/// metadata is <b>load-bearing</b>: a route that forgets it fails at the first request rather than
/// quietly validating against a different set from the one it publishes.
/// </para>
/// </remarks>
internal static class QueryDeclaration
{
    /// <summary>
    /// Declares the resource's sortable and filterable fields on a cursor-paged route.
    /// </summary>
    /// <param name="builder">The route being built.</param>
    /// <param name="whitelist">The resource's whitelist.</param>
    /// <returns>The same builder, for chaining.</returns>
    public static RouteHandlerBuilder PagedOver(this RouteHandlerBuilder builder, QueryWhitelist whitelist)
    {
        ArgumentNullException.ThrowIfNull(builder);

        return builder.WithMetadata(whitelist, new PagedMarker());
    }

    /// <summary>
    /// Declares the fields of a route that is sortable and filterable but <b>not</b> paged.
    /// </summary>
    /// <param name="builder">The route being built.</param>
    /// <param name="whitelist">The resource's whitelist.</param>
    /// <returns>The same builder, for chaining.</returns>
    public static RouteHandlerBuilder QueriedOver(this RouteHandlerBuilder builder, QueryWhitelist whitelist)
    {
        ArgumentNullException.ThrowIfNull(builder);

        return builder.WithMetadata(whitelist);
    }
}
