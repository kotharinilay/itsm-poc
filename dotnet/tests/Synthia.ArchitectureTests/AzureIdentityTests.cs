using System.Text.Json;
using System.Text.RegularExpressions;

namespace Synthia.ArchitectureTests;

/// <summary>
/// Azure clients authenticate as a managed identity. Application-owned credentials are refused.
/// </summary>
/// <remarks>
/// <para>
/// <b>The rule is cross-platform and the registry is shared.</b> <c>build/policy/azure-identity.json</c>
/// lists every Azure resource this platform reaches, whether managed identity is required for it, and
/// the named reason wherever it is not. RagCore enforces the same file from
/// <c>ragcore/tests/security/test_azure_identity.py</c>, and the parity tests at the bottom of each
/// file assert the two cover the same resources — because two hand-maintained lists drift, and the
/// drift is invisible until the day the weaker of the two is the one that mattered. A rule that is
/// easier to satisfy on one stack than the other decides where the insecure code gets written.
/// </para>
/// <para>
/// <b>Structural, not runtime.</b> These read source rather than opening a connection, so the rule
/// holds in CI without an Azure subscription, and a failure names the file and the construct instead
/// of surfacing as an authentication error three layers down. A credential defect that only appears
/// once deployed is one that ships.
/// </para>
/// <para>
/// <b>Local development is not an exception.</b> <c>DefaultAzureCredential</c> resolves a developer
/// identity locally through the same code path it uses for a managed identity in production, so there
/// is no second branch to get wrong. A credential type that works only on a laptop is still a
/// violation here: the rule is about what the code can <i>express</i>, not where it happens to run.
/// </para>
/// <para>
/// <b>These pass today against a codebase with no Azure client in it</b>, and that is why they are
/// written now. The rule is cheap to satisfy before the clients exist and expensive to retrofit
/// afterwards, when the first violation is already load-bearing.
/// </para>
/// </remarks>
public sealed class AzureIdentityTests
{
    /// <summary>The repository root. The solution lives in <c>dotnet/</c>, one level below it.</summary>
    private static DirectoryInfo RepositoryRoot()
    {
        DirectoryInfo? root = ProjectGraph.SolutionDirectory().Parent;

        Assert.True(
            root is not null,
            "Could not locate the repository root above the solution directory. The shared Azure " +
            "identity policy lives at build/policy/azure-identity.json and both stacks read it.");

        return root!;
    }

    private static FileInfo PolicyFile() =>
        new(Path.Combine(RepositoryRoot().FullName, "build", "policy", "azure-identity.json"));

    private static JsonDocument Policy()
    {
        FileInfo file = PolicyFile();

        Assert.True(
            file.Exists,
            "The shared Azure identity policy is missing: " + file.FullName +
            ". Both deployables read this one file; without it neither rule enforces anything.");

        return JsonDocument.Parse(File.ReadAllText(file.FullName));
    }

    private static List<string> StringsFrom(JsonElement array) =>
        array.EnumerateArray().Select(element => element.GetString() ?? string.Empty).ToList();

    /// <summary>Every resource id the registry declares.</summary>
    private static List<string> RegisteredResourceIds()
    {
        using JsonDocument policy = Policy();

        return policy.RootElement.GetProperty("resources")
            .EnumerateArray()
            .Select(resource => resource.GetProperty("id").GetString() ?? string.Empty)
            .ToList();
    }

    private static JsonElement ResourceById(JsonDocument policy, string id) =>
        policy.RootElement.GetProperty("resources")
            .EnumerateArray()
            .Single(resource => string.Equals(
                resource.GetProperty("id").GetString(), id, StringComparison.Ordinal));

    // -----------------------------------------------------------------------
    // The registry itself must be usable before it can be enforced
    // -----------------------------------------------------------------------

    /// <summary>A malformed registry silently enforces nothing, which is worse than none at all.</summary>
    [Fact]
    public void The_policy_registry_covers_every_resource_exactly_once()
    {
        string[] expected =
        [
            "postgresql",
            "servicebus",
            "signalr",
            "keyvault",
            "aisearch",
            "foundry",
            "monitor",
            "redis",
        ];

        List<string> registered = RegisteredResourceIds();

        Assert.Equal(registered.Count, registered.Distinct(StringComparer.Ordinal).Count());
        Assert.Equal(
            expected.Order(StringComparer.Ordinal),
            registered.Order(StringComparer.Ordinal));
    }

    /// <summary>Required or conditional. There is deliberately no <c>optional</c>.</summary>
    [Fact]
    public void Every_resource_declares_its_managed_identity_position()
    {
        using JsonDocument policy = Policy();

        foreach (JsonElement resource in policy.RootElement.GetProperty("resources").EnumerateArray())
        {
            string? position = resource.GetProperty("managedIdentity").GetString();

            Assert.True(
                position is "required" or "conditional",
                resource.GetProperty("id").GetString() + " declares an unrecognised position: " +
                position + ". A resource is either reached by managed identity or carries a named " +
                "exemption; there is no third state.");
        }
    }

    /// <summary>A secret used to reach the secret store defeats the entire arrangement.</summary>
    [Fact]
    public void Key_vault_can_never_be_exempted()
    {
        using JsonDocument policy = Policy();
        JsonElement vault = ResourceById(policy, "keyvault");

        Assert.Equal("required", vault.GetProperty("managedIdentity").GetString());
        Assert.False(vault.GetProperty("exemptionPermitted").GetBoolean());
    }

    /// <summary>An exemption without an owner and a review date is a permanent exemption.</summary>
    /// <remarks>
    /// The registry ships with none. This exists for the day somebody adds one: the friction is the
    /// feature, because the exemption is the thing that needs review, not the credential.
    /// </remarks>
    [Fact]
    public void Every_exemption_is_fully_named()
    {
        using JsonDocument policy = Policy();

        string[] required =
            ["resource", "providerLimitation", "credentialType", "storedIn", "owner", "reviewBy"];

        foreach (JsonElement entry in policy.RootElement.GetProperty("exemptions").EnumerateArray())
        {
            if (entry.TryGetProperty("$comment", out _))
            {
                continue;
            }

            foreach (string property in required)
            {
                Assert.True(
                    entry.TryGetProperty(property, out _),
                    "An Azure identity exemption is missing '" + property + "'. Name the provider " +
                    "limitation, the credential used instead, where it is stored, who owns it and " +
                    "when it is reviewed.");
            }

            Assert.Equal("keyvault", entry.GetProperty("storedIn").GetString());
            Assert.NotEqual("keyvault", entry.GetProperty("resource").GetString());
        }
    }

    // -----------------------------------------------------------------------
    // The credential chain
    // -----------------------------------------------------------------------

    /// <summary>
    /// <c>ClientSecretCredential</c> and its relatives are how an application comes to own a secret.
    /// </summary>
    /// <remarks>
    /// Each is a perfectly good Azure SDK type and each is prohibited here: they all take a credential
    /// the application holds, which is precisely the thing managed identity exists to remove.
    /// </remarks>
    [Fact]
    public void No_production_code_constructs_an_application_owned_credential()
    {
        using JsonDocument policy = Policy();

        List<string> banned = StringsFrom(
            policy.RootElement.GetProperty("forbiddenEverywhere").GetProperty("credentialTypes"));

        List<string> offenders = [];

        foreach (string credentialType in banned)
        {
            IReadOnlyList<string> files = SourceTree.ProductionFilesContaining(credentialType);

            if (files.Count > 0)
            {
                offenders.Add(credentialType + " in " + string.Join(", ", files));
            }
        }

        Assert.True(
            offenders.Count == 0,
            "An application-owned Azure credential is constructed:" + Environment.NewLine +
            string.Join(Environment.NewLine, offenders));
    }

    /// <summary>A client that builds its own credential is a second, weaker auth path beside the first.</summary>
    /// <remarks>
    /// Constructing it once means one place to audit, one place to change, and one place for a
    /// reviewer to look when asking how this process authenticates.
    /// </remarks>
    [Fact]
    public void The_credential_is_constructed_in_at_most_one_file()
    {
        IReadOnlyList<string> constructors =
            SourceTree.ProductionFilesContaining("new DefaultAzureCredential");

        Assert.True(
            constructors.Count <= 1,
            "DefaultAzureCredential is constructed in more than one place: " +
            string.Join(", ", constructors) +
            ". Construct it once and share it; every client takes the shared credential.");
    }

    // -----------------------------------------------------------------------
    // What must never appear, anywhere
    // -----------------------------------------------------------------------

    /// <summary>A key inside a connection string is still a key.</summary>
    [Fact]
    public void No_credential_bearing_connection_string_appears_in_source()
    {
        using JsonDocument policy = Policy();

        List<string> tokens = StringsFrom(
            policy.RootElement.GetProperty("forbiddenEverywhere")
                .GetProperty("connectionStringTokens"));

        List<string> offenders = [];

        foreach (string token in tokens)
        {
            IReadOnlyList<string> files = SourceTree.ProductionFilesContaining(token);

            if (files.Count > 0)
            {
                offenders.Add(token + " in " + string.Join(", ", files));
            }
        }

        Assert.True(
            offenders.Count == 0,
            "A credential-bearing connection string appears in source:" + Environment.NewLine +
            string.Join(Environment.NewLine, offenders));
    }

    /// <summary>
    /// Committed configuration is the other half of the surface, and the half that gets missed.
    /// </summary>
    /// <remarks>
    /// A secret removed from source and left in <c>appsettings.json</c> has not been removed. The
    /// key name is what is matched, not a value: a key named <c>clientSecret</c> is a defect whether
    /// or not it currently holds anything, because the shape tells the next author where a secret is
    /// allowed to live.
    /// </remarks>
    [Fact]
    public void No_committed_configuration_declares_a_credential_key()
    {
        using JsonDocument policy = Policy();

        List<string> keys = StringsFrom(
            policy.RootElement.GetProperty("forbiddenEverywhere").GetProperty("configurationKeys"));

        DirectoryInfo source = new(Path.Combine(ProjectGraph.SolutionDirectory().FullName, "src"));

        List<string> offenders = [];

        foreach (FileInfo settings in source.GetFiles("appsettings*.json", SearchOption.AllDirectories))
        {
            if (settings.FullName.Contains(Path.DirectorySeparatorChar + "bin" + Path.DirectorySeparatorChar, StringComparison.Ordinal) ||
                settings.FullName.Contains(Path.DirectorySeparatorChar + "obj" + Path.DirectorySeparatorChar, StringComparison.Ordinal))
            {
                continue;
            }

            string text = File.ReadAllText(settings.FullName);

            foreach (string key in keys)
            {
                // Matched as a quoted JSON property name, so a legitimate word inside a descriptive
                // value does not trip a rule aimed at the key.
                if (text.Contains('"' + key + '"', StringComparison.OrdinalIgnoreCase))
                {
                    offenders.Add(settings.Name + ": " + key);
                }
            }
        }

        Assert.True(
            offenders.Count == 0,
            "Committed configuration declares a credential key:" + Environment.NewLine +
            string.Join(Environment.NewLine, offenders));
    }

    // -----------------------------------------------------------------------
    // PostgreSQL — the one where correct usage and a violation look alike
    // -----------------------------------------------------------------------

    /// <summary>Entra authentication presents the access token in the password position.</summary>
    /// <remarks>
    /// That is why this needs its own assertion: a connection string carrying a real password and one
    /// carrying a token look identical in a configuration file, and only one of them is allowed.
    /// </remarks>
    [Fact]
    public void No_postgresql_connection_string_carries_an_embedded_password()
    {
        Regex dsn = new(
            "postgres(ql)?(\\+\\w+)?://[^\\s:/@\"']+:[^\\s@\"']+@",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
            TimeSpan.FromSeconds(2));

        List<string> offenders = [];

        foreach (FileInfo file in SourceTree.ProductionFiles())
        {
            if (dsn.IsMatch(SourceTree.CodeOf(file)))
            {
                offenders.Add(file.Name);
            }
        }

        // The keyword form Npgsql also accepts, checked separately because it looks nothing like a
        // URI and would otherwise pass a rule written only against the URI shape.
        offenders.AddRange(SourceTree.ProductionFilesContaining("Password="));

        Assert.True(
            offenders.Count == 0,
            "A PostgreSQL connection string carries an embedded password: " +
            string.Join(", ", offenders.Distinct(StringComparer.Ordinal)) +
            ". Entra authentication supplies a token at connect time instead.");
    }

    // -----------------------------------------------------------------------
    // Per-resource coverage, so a new client cannot arrive unguarded
    // -----------------------------------------------------------------------

    /// <summary>
    /// One case per resource, so a failure names the resource that regressed rather than the rule.
    /// </summary>
    /// <param name="resourceId">The registered resource.</param>
    /// <remarks>
    /// A resource whose client has not been written yet passes trivially, and that is correct: the
    /// rule is in place before the client is, so the first implementation is written against it
    /// rather than retrofitted to it.
    /// </remarks>
    [Theory]
    [InlineData("postgresql")]
    [InlineData("servicebus")]
    [InlineData("signalr")]
    [InlineData("keyvault")]
    [InlineData("aisearch")]
    [InlineData("foundry")]
    [InlineData("monitor")]
    [InlineData("redis")]
    public void Each_resource_is_registered_and_carries_no_unnamed_exemption(string resourceId)
    {
        using JsonDocument policy = Policy();
        JsonElement resource = ResourceById(policy, resourceId);

        string? position = resource.GetProperty("managedIdentity").GetString();
        Assert.True(position is "required" or "conditional");

        // Conditional without a written condition is optional wearing a better word.
        if (position is "conditional")
        {
            Assert.True(
                resource.TryGetProperty("condition", out JsonElement condition) &&
                !string.IsNullOrWhiteSpace(condition.GetString()),
                resourceId + " is conditional but names no condition. State which configurations " +
                "support Entra authentication, or make it required.");
        }

        bool exempted = policy.RootElement.GetProperty("exemptions").EnumerateArray()
            .Where(entry => entry.TryGetProperty("resource", out _))
            .Any(entry => string.Equals(
                entry.GetProperty("resource").GetString(), resourceId, StringComparison.Ordinal));

        if (exempted)
        {
            Assert.False(
                resource.TryGetProperty("exemptionPermitted", out JsonElement permitted) &&
                !permitted.GetBoolean(),
                resourceId + " holds an exemption it is not permitted to hold.");
        }
    }

    // -----------------------------------------------------------------------
    // Cross-platform parity
    // -----------------------------------------------------------------------

    /// <summary>A rule enforced on one stack and not the other decides where insecure code lands.</summary>
    [Fact]
    public void The_ragcore_enforcer_exists_and_reads_the_shared_registry()
    {
        FileInfo enforcer = new(Path.Combine(
            RepositoryRoot().FullName, "ragcore", "tests", "security", "test_azure_identity.py"));

        Assert.True(
            enforcer.Exists,
            "The RagCore half of the Azure identity rule is missing. Both deployables reach Azure " +
            "resources; a rule that only binds the monolith is not a platform rule.");

        string source = File.ReadAllText(enforcer.FullName);

        Assert.Contains("azure-identity.json", source, StringComparison.Ordinal);
    }

    /// <summary>Each registered resource is named by the RagCore enforcer too.</summary>
    [Fact]
    public void Both_enforcers_cover_every_registered_resource()
    {
        FileInfo enforcer = new(Path.Combine(
            RepositoryRoot().FullName, "ragcore", "tests", "security", "test_azure_identity.py"));

        string source = File.ReadAllText(enforcer.FullName);

        List<string> missing = RegisteredResourceIds()
            .Where(id => !source.Contains('"' + id + '"', StringComparison.Ordinal))
            .ToList();

        Assert.True(
            missing.Count == 0,
            "The RagCore enforcer does not name these resources: " + string.Join(", ", missing));
    }
}
