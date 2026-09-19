using System.Text.Json;
using Synthia.SharedKernel.Identity;

namespace Synthia.SharedKernel.Tests;

/// <summary>
/// The correlation rule belongs to the platform: <c>build/policy/correlation-id.json</c>.
/// </summary>
/// <remarks>
/// Each deployable implements the rule and each suite asserts its implementation against the shared
/// vectors, because the rules had drifted — RagCore accepted any printable string and the
/// Integrations Service hex only, so one journey's identifier was kept on one hop and replaced on
/// the next. This rule was already the right one; the test is what keeps the three from drifting
/// apart again.
/// </remarks>
public sealed class CorrelationPolicyTests
{
    private static JsonDocument Policy()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null &&
               !File.Exists(Path.Combine(directory.FullName, "build", "policy", "correlation-id.json")))
        {
            directory = directory.Parent;
        }

        Assert.True(
            directory is not null,
            "build/policy/correlation-id.json was not found above the test output. All three " +
            "deployables assert against it; without it this rule is checked against nothing.");

        return JsonDocument.Parse(
            File.ReadAllText(Path.Combine(directory!.FullName, "build", "policy", "correlation-id.json")));
    }

    public static TheoryData<string> Accepted() => Vectors("accept");

    public static TheoryData<string> Rejected() => Vectors("reject");

    private static TheoryData<string> Vectors(string property)
    {
        using JsonDocument policy = Policy();
        TheoryData<string> data = [];
        foreach (JsonElement vector in policy.RootElement.GetProperty(property).EnumerateArray())
        {
            data.Add(vector.GetString()!);
        }

        return data;
    }

    /// <summary>A well-formed identifier is kept, byte for byte.</summary>
    /// <param name="candidate">A vector from the policy's accept list.</param>
    [Theory]
    [MemberData(nameof(Accepted))]
    public void A_well_formed_identifier_is_kept(string candidate)
    {
        Assert.True(CorrelationId.TryAccept(candidate, out CorrelationId accepted));
        Assert.Equal(candidate, accepted.Value);
    }

    /// <summary>A malformed identifier is refused, so the middleware mints a fresh one.</summary>
    /// <param name="candidate">A vector from the policy's reject list.</param>
    [Theory]
    [MemberData(nameof(Rejected))]
    public void A_malformed_identifier_is_refused(string candidate)
    {
        Assert.False(CorrelationId.TryAccept(candidate, out _));
    }

    /// <summary>The length limit is the policy's, and it is inclusive.</summary>
    [Fact]
    public void The_length_limit_is_the_policys()
    {
        using JsonDocument policy = Policy();
        int limit = policy.RootElement.GetProperty("maxLength").GetInt32();

        Assert.True(CorrelationId.TryAccept(new string('a', limit), out _));
        Assert.False(CorrelationId.TryAccept(new string('a', limit + 1), out _));
    }
}
