using System.Text.Json;

namespace Synthia.ArchitectureTests;

/// <summary>
/// What APIM routes where, asserted from the shared routing registry.
/// </summary>
/// <remarks>
/// <para>
/// <c>build/infra/apim/apis.json</c> is where the routing table stopped being prose. Before it, the
/// rule that <c>/api/{audience}/v1/views/...</c> reaches this deployable and everything else reaches
/// RagCore lived in <c>contracts/README.md</c> and in a sentence in <c>tasks.md</c> — true, agreed,
/// and enforced by nothing.
/// </para>
/// <para>
/// <b>This file asserts the half that is this deployable's concern: the monolith is read-only</b>
/// (ADR-0001). It serves <c>views</c> routes and nothing else, and a routing entry that sent a
/// write here would not fail loudly — it would reach a service that serves the audience, find no
/// such route, and return a 404 indistinguishable from a client calling something that does not
/// exist. The identity, rate-limit and contract-import halves are asserted by RagCore in
/// <c>ragcore/tests/security/test_edge_topology.py</c>; both stacks read this one file, for the
/// reason every shared registry here exists — two hand-maintained lists drift, and the drift is
/// invisible until the day the weaker of the two is the one that mattered.
/// </para>
/// <para>
/// <b>Structural, not runtime.</b> This reads committed configuration, so the routing holds in CI
/// without an Azure subscription — which matters because a deployed environment is the scaffold's
/// longest-lead dependency, and a control checkable only there goes unchecked until then.
/// </para>
/// </remarks>
public sealed class ApimRoutingTests
{
    private const string MonolithBackend = "monolith";

    private static DirectoryInfo RepositoryRoot()
    {
        DirectoryInfo? root = ProjectGraph.SolutionDirectory().Parent;

        Assert.True(
            root is not null,
            "Could not locate the repository root above the solution directory. The shared APIM " +
            "routing registry lives at build/infra/apim/apis.json and both stacks read it.");

        return root!;
    }

    private static JsonDocument Registry()
    {
        FileInfo file = new(Path.Combine(
            RepositoryRoot().FullName, "build", "infra", "apim", "apis.json"));

        Assert.True(
            file.Exists,
            "The APIM routing registry is missing: " + file.FullName +
            ". Without it, which URL reaches which deployable is prose again.");

        return JsonDocument.Parse(File.ReadAllText(file.FullName));
    }

    private static List<JsonElement> Apis()
    {
        using JsonDocument registry = Registry();
        return registry.RootElement.GetProperty("apis").EnumerateArray()
            .Select(api => api.Clone()).ToList();
    }

    private static string Text(JsonElement element, string property) =>
        element.GetProperty(property).GetString() ?? string.Empty;

    // ----------------------------------------------------------------------------------------
    // The monolith is read-only, and the routing table is where that stops being a promise
    // ----------------------------------------------------------------------------------------

    [Fact]
    public void Every_route_to_this_deployable_is_a_read_view()
    {
        // ADR-0001: this deployable exposes no state-changing endpoint. The identity that runs it
        // holds no Service Bus, SignalR, AI Search or model role, so a write path added by mistake
        // fails at the platform — but it would fail AFTER being routed here, as a 500 nobody can
        // place. Refusing the route is the earlier and clearer half.
        List<string> violations = [];

        foreach (JsonElement api in Apis())
        {
            if (Text(api, "backend") != MonolithBackend)
            {
                continue;
            }

            string path = Text(api, "path");
            if (!path.EndsWith("/views", StringComparison.Ordinal))
            {
                violations.Add($"{Text(api, "id")} routes {path} to the read-only monolith");
            }
        }

        Assert.True(
            violations.Count == 0,
            "A non-view route is directed at the read-only deployable:\n  "
            + string.Join("\n  ", violations));
    }

    [Fact]
    public void Every_audience_this_deployable_serves_has_a_view_route()
    {
        // The converse. The customer and staff audiences each have a read half, and an audience
        // whose views are unrouted is a set of endpoints that exist, pass their own tests, and are
        // unreachable through the only path a client is allowed to use.
        List<string> served = Apis()
            .Where(api => Text(api, "backend") == MonolithBackend)
            .Select(api => Text(api, "audience"))
            .ToList();

        Assert.Contains("customer", served);
        Assert.Contains("staff", served);

        // The workload audience is the execution leg and has no read half. Asserted rather than
        // left implied, so adding one is a deliberate change to this file.
        Assert.DoesNotContain("workload", served);
    }

    [Fact]
    public void The_view_routes_are_more_specific_than_the_write_routes_they_sit_under()
    {
        // THE ENTIRE ROUTING RULE, and it rests on APIM resolving the longest matching path first.
        // /api/customer/v1/views must be a strict extension of /api/customer/v1, or the two APIs do
        // not overlap in the way that makes the split work — and the failure is a view request
        // reaching RagCore, which returns a 404 that looks like a client error.
        List<JsonElement> apis = Apis();
        List<string> violations = [];

        foreach (JsonElement view in apis.Where(api => Text(api, "path").EndsWith("/views", StringComparison.Ordinal)))
        {
            string viewPath = Text(view, "path");
            string audience = Text(view, "audience");

            bool sitsUnderAWriteRoute = apis.Any(api =>
                Text(api, "audience") == audience
                && Text(api, "backend") != MonolithBackend
                && viewPath.StartsWith(Text(api, "path") + "/", StringComparison.Ordinal));

            if (!sitsUnderAWriteRoute)
            {
                violations.Add($"{Text(view, "id")} at {viewPath} extends no route on its audience");
            }
        }

        Assert.True(
            violations.Count == 0,
            "A view route does not sit beneath the audience route it narrows:\n  "
            + string.Join("\n  ", violations));
    }

    // ----------------------------------------------------------------------------------------
    // The documents this deployable publishes are generated
    // ----------------------------------------------------------------------------------------

    [Fact]
    public void Every_document_this_deployable_serves_is_generated_and_present()
    {
        // Generated from the running service by the built-in OpenAPI generator, never hand-written
        // (spec FR-DEMO-013). A hand-maintained copy imported into the gateway drifts from what the
        // service accepts, and the drift is invisible until a client believes the document.
        List<string> violations = [];

        foreach (JsonElement api in Apis().Where(api => Text(api, "backend") == MonolithBackend))
        {
            JsonElement openApi = api.GetProperty("openApi");

            if (openApi.GetProperty("handWritten").GetBoolean())
            {
                violations.Add($"{Text(api, "id")} imports a hand-written document");
                continue;
            }

            string source = Text(openApi, "source");
            FileInfo document = new(Path.Combine(
                RepositoryRoot().FullName, source.Replace('/', Path.DirectorySeparatorChar)));

            if (!document.Exists)
            {
                violations.Add($"{Text(api, "id")} imports {source}, which is not present");
            }
        }

        Assert.True(
            violations.Count == 0,
            "An API served by this deployable does not import a generated document:\n  "
            + string.Join("\n  ", violations));
    }

    // ----------------------------------------------------------------------------------------
    // No shared secret reaches this deployable
    // ----------------------------------------------------------------------------------------

    [Fact]
    public void The_gateway_reaches_this_deployable_without_a_shared_secret()
    {
        // APIM presents a certificate it reads from Key Vault as its own managed identity. There is
        // no key, no subscription secret and no authorization header value: a credential the
        // application held would be one that could be exfiltrated and replayed, and this deployable
        // holds only the public hash of what APIM presents.
        using JsonDocument registry = Registry();
        JsonElement backend = registry.RootElement.GetProperty("backends").EnumerateArray()
            .Single(entry => Text(entry, "id") == MonolithBackend);

        JsonElement credentials = backend.GetProperty("credentials");

        Assert.Equal("client-certificate", Text(credentials, "type"));

        string[] forbidden =
        [
            "key", "apiKey", "api_key", "sharedSecret", "clientSecret", "password", "sasToken"
        ];

        foreach (string name in forbidden)
        {
            Assert.False(
                credentials.TryGetProperty(name, out _),
                $"The monolith backend declares `{name}`. APIM authenticates to it by presenting a "
                + "certificate read from Key Vault as a managed identity; there is no secret here.");
        }
    }

    [Fact]
    public void The_registry_names_the_container_app_this_deployable_actually_runs_as()
    {
        // The registry claims a backend is internal-only. Checking it against the manifest is what
        // makes that a fact rather than a note: the two files are edited by different people at
        // different times, and "internal ingress" is exactly the setting a troubleshooting session
        // flips and forgets.
        using JsonDocument registry = Registry();
        JsonElement backend = registry.RootElement.GetProperty("backends").EnumerateArray()
            .Single(entry => Text(entry, "id") == MonolithBackend);

        string relative = Text(backend, "containerApp");
        FileInfo manifest = new(Path.Combine(
            RepositoryRoot().FullName, relative.Replace('/', Path.DirectorySeparatorChar)));

        Assert.True(manifest.Exists, $"The registry names {relative}, which does not exist.");

        string text = File.ReadAllText(manifest.FullName);

        Assert.Contains("external: false", text, StringComparison.Ordinal);
        Assert.DoesNotContain("external: true", text, StringComparison.Ordinal);
    }

    // ----------------------------------------------------------------------------------------
    // Cross-platform parity
    // ----------------------------------------------------------------------------------------

    [Fact]
    public void The_ragcore_enforcer_reads_the_same_registry()
    {
        // The same parity assertion every shared registry here carries. A rule enforced on one
        // stack and not the other decides where the insecure change gets made.
        FileInfo enforcer = new(Path.Combine(
            RepositoryRoot().FullName,
            "ragcore", "tests", "security", "test_edge_topology.py"));

        Assert.True(
            enforcer.Exists,
            "The RagCore half of the routing enforcement is missing: " + enforcer.FullName);

        Assert.Contains(
            "apim\" / \"apis.json",
            File.ReadAllText(enforcer.FullName),
            StringComparison.Ordinal);
    }
}
