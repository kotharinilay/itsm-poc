using System.Text.Json;
using System.Text.Json.Nodes;
using Synthia.Api.Contracts;

namespace Synthia.ContractTests;

/// <summary>
/// Emits this deployable's per-audience OpenAPI documents, and asserts what they may not carry.
/// </summary>
/// <remarks>
/// <para>
/// <b>Emission lives in a test because the document comes from the running application.</b> The
/// generator needs a built host; a build-time task would describe the assembly rather than the
/// service, and the two differ exactly where conventions and filters are applied. Running it here
/// means the artifact CI publishes is produced by the same generator that serves
/// <c>/openapi/{audience}.json</c> — what is reviewed is what is served.
/// </para>
/// <para>
/// <b>The comparison against the committed baseline is not done here.</b> RagCore emits documents
/// too, and one comparator for both stacks is the only way the rule cannot be weaker on one of them
/// — see <c>build/scripts/openapi_diff.py</c>, which CI runs over everything under
/// <c>build/contracts/</c> after both stacks have emitted.
/// </para>
/// <para>
/// Output is deterministic — sorted keys, trailing newline — so a document that has not changed
/// produces a byte-identical file. Without that, every build shows a diff and the comparator's
/// signal drowns in noise nobody reads.
/// </para>
/// </remarks>
public sealed class OpenApiEmissionTests : IClassFixture<WebApplicationFixture>
{
    private readonly WebApplicationFixture _factory;

    /// <summary>Creates the fixture.</summary>
    /// <param name="factory">The application under test.</param>
    public OpenApiEmissionTests(WebApplicationFixture factory)
    {
        ArgumentNullException.ThrowIfNull(factory);

        _factory = factory;
    }

    /// <summary>The audiences this deployable serves. Workload belongs to RagCore.</summary>
    public static TheoryData<string> Audiences
    {
        get
        {
            TheoryData<string> data = [];

            foreach (string audience in ContractOpenApi.Audiences)
            {
                data.Add(audience);
            }

            return data;
        }
    }

    /// <summary>The shared disclosure registry, applied by both stacks.</summary>
    private static JsonDocument DisclosurePolicy()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);

        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Synthia.sln")))
        {
            directory = directory.Parent;
        }

        Assert.True(directory?.Parent is not null, "Could not locate the repository root.");

        string path = Path.Combine(
            directory!.Parent!.FullName, "build", "policy", "openapi-disclosure.json");

        Assert.True(
            File.Exists(path),
            "The shared OpenAPI disclosure registry is missing: " + path +
            ". Both stacks read this one file; without it neither rule enforces anything.");

        return JsonDocument.Parse(File.ReadAllText(path));
    }

    private static DirectoryInfo ContractDirectory()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);

        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Synthia.sln")))
        {
            directory = directory.Parent;
        }

        Assert.True(directory?.Parent is not null, "Could not locate the repository root.");

        DirectoryInfo target = new(Path.Combine(
            directory!.Parent!.FullName, "build", "contracts", "dotnet"));

        target.Create();

        return target;
    }

    private async Task<JsonNode> DocumentAsync(string audience)
    {
        using HttpClient client = _factory.CreateClient();

        using HttpResponseMessage response =
            await client.GetAsync(new Uri($"/openapi/{audience}.json", UriKind.Relative));

        Assert.True(
            response.IsSuccessStatusCode,
            $"The {audience} OpenAPI document was not served: {response.StatusCode}. A document " +
            "that cannot be generated cannot be published, and a missing contract is a breaking " +
            "change to every client of it.");

        string body = await response.Content.ReadAsStringAsync();

        return JsonNode.Parse(body)
            ?? throw new InvalidOperationException($"The {audience} document was not valid JSON.");
    }

    /// <summary>Writes each audience document to the contract-artifact directory.</summary>
    /// <param name="audience">The audience being emitted.</param>
    [Theory]
    [MemberData(nameof(Audiences))]
    public async Task Emits_the_audience_document(string audience)
    {
        JsonNode document = await DocumentAsync(audience);

        await File.WriteAllTextAsync(
            Path.Combine(
                ContractDirectory().FullName,
                $"{audience}.{ContractOpenApi.ContractVersion}.openapi.json"),
            Canonical(document));

        Assert.NotNull(document["paths"]);
    }

    /// <summary>
    /// Renders a document so that an unchanged API produces byte-identical output.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Two properties, and both are load-bearing.</b> Object keys are sorted, because the
    /// generator's enumeration order is not part of the contract and a document that reorders on
    /// every build buries every real change in noise nobody reads. And the line ending is a bare
    /// line feed rather than <see cref="Environment.NewLine"/>: emitting on Windows and verifying
    /// on Linux otherwise produces a byte difference on every line of a document that did not
    /// change, which fails the stale-contract gate for a reason that has nothing to do with the API.
    /// </para>
    /// <para>
    /// Matches <c>ragcore/scripts/emit_contracts.py</c>, which sorts keys and ends with a newline
    /// for the same reasons. One comparator reads both stacks' output, so both must be canonical
    /// the same way.
    /// </para>
    /// </remarks>
    /// <param name="document">The generated document.</param>
    /// <returns>The canonical rendering, newline-terminated.</returns>
    private static string Canonical(JsonNode document)
    {
        const string LineFeed = "\n";

        string rendered = Sorted(document)
            .ToJsonString(new JsonSerializerOptions { WriteIndented = true })
            .ReplaceLineEndings(LineFeed);

        return rendered + LineFeed;
    }

    private static JsonNode Sorted(JsonNode? node)
    {
        switch (node)
        {
            case JsonObject map:
                JsonObject ordered = [];

                foreach (KeyValuePair<string, JsonNode?> entry in
                    map.OrderBy(entry => entry.Key, StringComparer.Ordinal))
                {
                    ordered[entry.Key] = Sorted(entry.Value);
                }

                return ordered;

            case JsonArray array:
                // Arrays are NOT sorted: order is meaningful in `required`, `enum` and `parameters`,
                // and reordering them would change the document rather than normalise it.
                JsonArray copied = [];

                foreach (JsonNode? item in array)
                {
                    copied.Add(Sorted(item));
                }

                return copied;

            default:
                return node?.DeepClone() ?? JsonValue.Create((string?)null)!;
        }
    }

    /// <summary>
    /// A document carries its own audience's paths and no other's.
    /// </summary>
    /// <param name="audience">The audience being checked.</param>
    /// <remarks>
    /// This is the rule the split exists for. A merged document would let a customer-facing client
    /// enumerate the staff surface, which is reconnaissance handed over for free.
    /// </remarks>
    [Theory]
    [MemberData(nameof(Audiences))]
    public async Task A_document_carries_only_its_own_audience(string audience)
    {
        JsonNode document = await DocumentAsync(audience);
        JsonObject paths = document["paths"]!.AsObject();

        foreach (KeyValuePair<string, JsonNode?> entry in paths)
        {
            Assert.StartsWith(
                $"/api/{audience}/{ContractOpenApi.ContractVersion}",
                entry.Key,
                StringComparison.Ordinal);
        }
    }

    /// <summary>
    /// A published document carries no secret, no credential and no internal-only detail.
    /// </summary>
    /// <param name="audience">The audience being checked.</param>
    /// <remarks>
    /// <para>
    /// Matched against <b>names</b> rather than descriptions. A description explaining that an
    /// operation carries no credential is correct documentation; a field called <c>apiKey</c> is a
    /// defect whatever it happens to hold today.
    /// </para>
    /// <para>
    /// <b>Derived authority is checked separately and positionally</b>, by
    /// <see cref="No_operation_offers_a_client_a_way_to_assert_authority"/>. It is deliberately not
    /// matched here: <c>tenantId</c> in a response is the organisation a row belongs to, reported to
    /// a caller already entitled to the row, and forbidding the name outright would force an audit
    /// read model to hide the organisation a record concerns — the field a staff reviewer opens it
    /// for.
    /// </para>
    /// </remarks>
    [Theory]
    [MemberData(nameof(Audiences))]
    public async Task A_document_discloses_nothing_it_must_not(string audience)
    {
        // Read from the shared registry rather than restated here. RagCore applies the same file,
        // so the two stacks cannot drift — and keeping the vocabulary as data means a list of
        // credential-shaped words is not sitting in source looking exactly like leaked credentials.
        using JsonDocument policy = DisclosurePolicy();

        string[] secretTerms = [.. policy.RootElement.GetProperty("secretTerms")
            .GetProperty("terms").EnumerateArray().Select(term => term.GetString()!)];

        string[] internalTerms = [.. policy.RootElement.GetProperty("internalTerms")
            .GetProperty("implementationDetail").EnumerateArray()
                .Select(term => term.GetString()!)];

        string[] structural = [.. policy.RootElement.GetProperty("structuralKeys")
            .GetProperty("keys").EnumerateArray().Select(key => key.GetString()!)];

        JsonNode document = await DocumentAsync(audience);
        List<string> findings = [];

        Walk(document, string.Empty, findings, secretTerms, internalTerms, structural);

        Assert.True(
            findings.Count == 0,
            $"The {audience} document publishes what it must not:" + Environment.NewLine +
            string.Join(Environment.NewLine, findings));
    }

    /// <summary>
    /// No operation publishes a way for a client to assert tenant, role or audience.
    /// </summary>
    /// <param name="audience">The audience being checked.</param>
    /// <remarks>
    /// <para>
    /// <b>A position rule, not a name rule.</b> The platform derives tenant, roles and audience and
    /// never accepts them (A1 §4.5, contracts §README rule 1), so what must not exist is a
    /// <i>channel</i> — a parameter or a request-body field. A name rule would be satisfied by
    /// renaming the field rather than by removing the channel.
    /// </para>
    /// <para>
    /// The one exception is read from the policy file rather than written here: <c>tenantId</c> is a
    /// staff-only <b>query</b> narrowing that selects within the set the caller may already see. It
    /// reaches the query as one more <c>WHERE</c> clause underneath the global scope filter, so a
    /// caller naming an organisation outside their scope receives no rows rather than that
    /// organisation's rows.
    /// </para>
    /// <para>
    /// This deployable is read-only (ADR-0001) so no route has a request body, and the request-body
    /// half of the rule is enforced by <c>build/scripts/openapi_validate.py</c> across both stacks'
    /// emitted artifacts. It is asserted here anyway: the day a body appears, this is what refuses
    /// it.
    /// </para>
    /// </remarks>
    [Theory]
    [MemberData(nameof(Audiences))]
    public async Task No_operation_offers_a_client_a_way_to_assert_authority(string audience)
    {
        using JsonDocument policy = DisclosurePolicy();

        string[] authority = [.. policy.RootElement.GetProperty("internalTerms")
            .GetProperty("derivedAuthority").EnumerateArray().Select(term => term.GetString()!)];

        JsonElement exceptions = policy.RootElement
            .GetProperty("authorityPositions").GetProperty("exceptions");

        JsonNode document = await DocumentAsync(audience);
        List<string> findings = [];

        foreach (KeyValuePair<string, JsonNode?> path in document["paths"]!.AsObject())
        {
            foreach (KeyValuePair<string, JsonNode?> operation in path.Value!.AsObject())
            {
                if (operation.Value?["parameters"] is not JsonArray parameters)
                {
                    continue;
                }

                foreach (JsonNode? parameter in parameters)
                {
                    string name = parameter?["name"]?.GetValue<string>() ?? string.Empty;
                    string location = parameter?["in"]?.GetValue<string>() ?? string.Empty;

                    if (!Array.Exists(authority, term =>
                            string.Equals(term, Normalise(name), StringComparison.Ordinal)))
                    {
                        continue;
                    }

                    if (Permitted(exceptions, name, location, audience))
                    {
                        continue;
                    }

                    findings.Add(
                        $"client-suppliable authority: {location} parameter '{name}' on " +
                        $"{operation.Key.ToUpperInvariant()} {path.Key}");
                }

                if (operation.Value?["requestBody"] is not null)
                {
                    findings.Add(
                        $"{operation.Key.ToUpperInvariant()} {path.Key} declares a request body. " +
                        "This deployable is read-only (ADR-0001); a body here is a write endpoint " +
                        "that has not been recognised as one.");
                }
            }
        }

        Assert.True(
            findings.Count == 0,
            $"The {audience} document publishes an authority channel:" + Environment.NewLine +
            string.Join(Environment.NewLine, findings));
    }

    private static bool Permitted(
        JsonElement exceptions,
        string name,
        string location,
        string audience)
    {
        foreach (JsonElement exception in exceptions.EnumerateArray())
        {
            bool matches =
                string.Equals(
                    Normalise(exception.GetProperty("name").GetString()!),
                    Normalise(name),
                    StringComparison.Ordinal) &&
                string.Equals(
                    exception.GetProperty("in").GetString(), location, StringComparison.Ordinal) &&
                exception.GetProperty("audiences").EnumerateArray()
                    .Any(allowed => string.Equals(
                        allowed.GetString(), audience, StringComparison.Ordinal));

            if (matches)
            {
                return true;
            }
        }

        return false;
    }

    private static void Walk(
        JsonNode? node,
        string path,
        List<string> findings,
        string[] secretTerms,
        string[] internalTerms,
        string[] structural)
    {
        switch (node)
        {
            case JsonObject map:
                foreach (KeyValuePair<string, JsonNode?> entry in map)
                {
                    string here = path.Length == 0 ? entry.Key : path + "." + entry.Key;

                    // Structural keys of the format itself. `security` describes HOW to
                    // authenticate, never with what.
                    if (!Array.Exists(structural, key =>
                        string.Equals(key, entry.Key, StringComparison.Ordinal)))
                    {
                        string normalised = Normalise(entry.Key);

                        if (Array.Exists(secretTerms, term =>
                            normalised.Contains(term, StringComparison.Ordinal)))
                        {
                            findings.Add($"secret-bearing name '{entry.Key}' at {here}");
                        }
                        else if (Array.Exists(internalTerms, term =>
                            string.Equals(normalised, term, StringComparison.Ordinal)))
                        {
                            findings.Add($"internal-only name '{entry.Key}' at {here}");
                        }
                    }

                    Walk(entry.Value, here, findings, secretTerms, internalTerms, structural);
                }

                break;

            case JsonArray array:
                for (int index = 0; index < array.Count; index++)
                {
                    Walk(
                        array[index], $"{path}[{index}]", findings, secretTerms, internalTerms,
                        structural);
                }

                break;
        }
    }

    private static string Normalise(string name) =>
        new([.. name.ToLowerInvariant().Where(char.IsLetterOrDigit)]);
}
