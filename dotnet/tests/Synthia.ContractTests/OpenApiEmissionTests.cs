using System.Text.Json;
using System.Text.Json.Nodes;

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
    public static TheoryData<string> Audiences => new() { "customer", "staff" };

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

        string rendered = document.ToJsonString(new JsonSerializerOptions { WriteIndented = true });

        await File.WriteAllTextAsync(
            Path.Combine(ContractDirectory().FullName, $"{audience}.v1.openapi.json"),
            rendered + Environment.NewLine);

        Assert.NotNull(document["paths"]);
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
            Assert.StartsWith($"/api/{audience}/v1", entry.Key, StringComparison.Ordinal);
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
    /// <c>tenantId</c>, <c>roles</c> and <c>audience</c> are in the internal list for a specific
    /// reason: <b>no endpoint accepts a tenant, role or audience parameter</b> (contracts §README
    /// rule 1). Publishing one would advertise exactly the thing the platform refuses, and a client
    /// that sent it would get a silent no-op rather than an error.
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

        JsonElement internals = policy.RootElement.GetProperty("internalTerms");

        string[] internalTerms =
        [
            .. internals.GetProperty("implementationDetail").EnumerateArray()
                .Select(term => term.GetString()!),
            .. internals.GetProperty("derivedAuthority").EnumerateArray()
                .Select(term => term.GetString()!),
        ];

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
