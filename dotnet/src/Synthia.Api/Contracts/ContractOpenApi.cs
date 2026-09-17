using System.Text.Json.Nodes;
using Microsoft.AspNetCore.OpenApi;
using Microsoft.OpenApi;
using Synthia.Api.Middleware;
using Synthia.Api.Querying;
using Synthia.Contracts.Querying;

namespace Synthia.Api.Contracts;

/// <summary>
/// Registers the per-audience OpenAPI documents this deployable publishes.
/// </summary>
/// <remarks>
/// <para>
/// <b>One document per audience, and a merged document is prohibited</b> (contracts §README rule
/// 5): publishing them together would let a customer-facing client enumerate the staff surface,
/// which is reconnaissance handed over for free. The split is by path prefix because the prefix
/// <i>is</i> the audience — the same fact APIM routes on and <see cref="IdentityContextMiddleware"/>
/// resolves.
/// </para>
/// <para>
/// <b>Everything here is a transformation of the generated document, never a second description of
/// the API.</b> The paging and filtering parameters come from <see cref="ResourceQueries"/>, which
/// is the same object the binder validates against; the response bodies come from the endpoint
/// declarations. A hand-written document would be a copy with nothing keeping it true.
/// </para>
/// <para>
/// <b>What is stripped, and why.</b> The generator writes a <c>servers</c> block naming the host it
/// was generated on — <c>http://localhost/</c> from the test host, an internal address from a
/// container. That is configuration material describing the deployment rather than the contract, it
/// differs between the machine that emits and the machine that verifies, and it is exactly the kind
/// of value that must not be published (spec FR-DEMO-012). The public address is Front Door's and is
/// APIM's to state, not this process's.
/// </para>
/// </remarks>
internal static class ContractOpenApi
{
    /// <summary>The API version these documents describe. Part of the path and of the artifact name.</summary>
    public const string ContractVersion = "v1";

    /// <summary>The audiences this deployable serves.</summary>
    /// <remarks>
    /// The workload audience belongs to RagCore, which emits its own document. There is deliberately
    /// no empty workload document here: an empty contract reads as "this surface has no operations"
    /// rather than "this surface is somewhere else".
    /// </remarks>
    public static IReadOnlyList<string> Audiences { get; } = ["customer", "staff"];

    /// <summary>Registers one OpenAPI document per audience.</summary>
    /// <param name="services">The service collection.</param>
    /// <returns>The same collection, for chaining.</returns>
    public static IServiceCollection AddSynthiaOpenApi(this IServiceCollection services)
    {
        ArgumentNullException.ThrowIfNull(services);

        foreach (string audience in Audiences)
        {
            string prefix = $"api/{audience}/{ContractVersion}";
            string name = audience;

            services.AddOpenApi(name, options =>
            {
                options.ShouldInclude = description =>
                    description.RelativePath?.StartsWith(prefix, StringComparison.Ordinal) ?? false;

                options.AddDocumentTransformer((document, _, _) =>
                {
                    Describe(document, name);
                    return Task.CompletedTask;
                });

                options.AddOperationTransformer((operation, context, _) =>
                {
                    AddQueryParameters(operation, context);
                    return Task.CompletedTask;
                });
            });
        }

        return services;
    }

    /// <summary>
    /// Replaces the generator's defaults with the published identity of this contract.
    /// </summary>
    /// <remarks>
    /// The generator titles a document after the assembly and versions it after the assembly
    /// version. Neither is the contract: the assembly version moves on a patch release that changes
    /// no route, and the audience is not in the title at all. The version published here is the one
    /// in the path, because that is the version a client is pinned to.
    /// </remarks>
    /// <param name="document">The generated document.</param>
    /// <param name="audience">The audience it describes.</param>
    private static void Describe(OpenApiDocument document, string audience)
    {
        document.Info = new OpenApiInfo
        {
            Title = $"Synthia {char.ToUpperInvariant(audience[0])}{audience[1..]} API",
            Version = ContractVersion,
            Description =
                $"The {audience} audience. Generated from the running service; not " +
                "hand-maintained. Identity is derived at the gateway and no operation accepts a " +
                "tenant, role or audience parameter.",
        };

        // Configuration material, and it differs between the machine that emits and the machine
        // that verifies. See the type remarks.
        document.Servers?.Clear();
    }

    /// <summary>
    /// Publishes the paging, sorting and filtering parameters an endpoint actually accepts.
    /// </summary>
    /// <remarks>
    /// <para>
    /// These parameters are read from the query string inside the handler rather than bound as
    /// method arguments, because the binder validates them against the resource's whitelist and
    /// refuses an unknown field with a 400. The generator cannot see a parameter a handler reads
    /// for itself, so an undocumented endpoint would advertise no way to page a collection it
    /// only serves a page of.
    /// </para>
    /// <para>
    /// The whitelist is read off the endpoint's own metadata — the same instance the handler
    /// resolves through <see cref="QueryBinding.WhitelistOf"/> and validates against. There is one
    /// declaration, so the document cannot describe a filter set the endpoint does not enforce.
    /// </para>
    /// </remarks>
    /// <param name="operation">The operation being described.</param>
    /// <param name="context">The transformer context, carrying the endpoint metadata.</param>
    private static void AddQueryParameters(OpenApiOperation operation, OpenApiOperationTransformerContext context)
    {
        QueryWhitelist? whitelist = context.Description.ActionDescriptor.EndpointMetadata
            .OfType<QueryWhitelist>()
            .FirstOrDefault();

        if (whitelist is null)
        {
            return;
        }

        operation.Parameters ??= [];

        if (context.Description.ActionDescriptor.EndpointMetadata.OfType<PagedMarker>().Any())
        {
            Add(operation, "limit", "integer", null, [],
                "Page size. Clamped to the server maximum rather than refused.");

            Add(operation, "cursor", "string", null, [],
                "An opaque resume position from a previous page's nextCursor. Clients MUST NOT " +
                "construct or decode one.");
        }

        Add(
            operation,
            "sort",
            "string",
            null,
            [.. whitelist.SortableFields.Order(StringComparer.Ordinal)
                .SelectMany(field => new[] { field, "-" + field })
                .Order(StringComparer.Ordinal)],
            "Sort field, prefixed with '-' for descending. An unlisted field is a 400. Default: " +
            (whitelist.DefaultSort.Direction == SortDirection.Descending ? "-" : string.Empty) +
            whitelist.DefaultSort.Field + ".");

        foreach (FilterField filter in whitelist.Filters.OrderBy(field => field.Name, StringComparer.Ordinal))
        {
            (string type, string? format) = filter.Kind switch
            {
                FilterKind.Identifier => ("string", "uuid"),
                FilterKind.Timestamp => ("string", "date-time"),
                _ => ("string", (string?)null),
            };

            Add(operation, filter.Name, type, format, filter.Values, FilterDescription(filter));
        }
    }

    /// <summary>
    /// The published description of one filter.
    /// </summary>
    /// <remarks>
    /// <c>tenantId</c> carries its own sentence because it is the one query field that looks like
    /// authority and is not. Saying so in the contract is the point: a client reading it should not
    /// come away believing it selects whose data to read.
    /// </remarks>
    /// <param name="filter">The declared filter.</param>
    /// <returns>The description.</returns>
    private static string FilterDescription(FilterField filter) =>
        string.Equals(filter.Name, "tenantId", StringComparison.Ordinal)
            ? "Narrows the result to one organisation WITHIN the set the caller may already see. " +
              "It does not establish authority and cannot widen the result: naming an organisation " +
              "outside the caller's scope returns no rows."
            : $"Filters on {filter.Name}. An unlisted filter field is a 400.";

    private static void Add(
        OpenApiOperation operation,
        string name,
        string type,
        string? format,
        IReadOnlyList<string> values,
        string description)
    {
        // The generator may already have bound this one as a method argument on some future
        // endpoint. Declaring it twice would produce an invalid document.
        if (operation.Parameters!.Any(parameter =>
                string.Equals(parameter.Name, name, StringComparison.Ordinal)))
        {
            return;
        }

        OpenApiSchema schema = new() { Type = JsonSchemaType.String };

        if (string.Equals(type, "integer", StringComparison.Ordinal))
        {
            schema.Type = JsonSchemaType.Integer;
        }

        if (format is not null)
        {
            schema.Format = format;
        }

        if (values.Count > 0)
        {
            schema.Enum = [.. values.Select(value => (JsonNode)JsonValue.Create(value)!)];
        }

        operation.Parameters!.Add(new OpenApiParameter
        {
            Name = name,
            In = ParameterLocation.Query,
            Required = false,
            Description = description,
            Schema = schema,
        });
    }
}

/// <summary>
/// Marks a route as cursor-paged, so <c>limit</c> and <c>cursor</c> are published on it.
/// </summary>
/// <remarks>
/// A separate marker from the whitelist because not every whitelisted resource is paged: the step
/// trail is sortable and unpaged — a trail with a page boundary in it is not a trail — and
/// publishing a cursor on it would advertise a parameter the handler ignores.
/// </remarks>
internal sealed class PagedMarker;
