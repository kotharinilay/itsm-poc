using System.Reflection;
using Synthia.Contracts.Boundaries;

namespace Synthia.ArchitectureTests;

/// <summary>
/// The boundaries this deployable must carry no trace of.
/// </summary>
/// <remarks>
/// <para>
/// <b>Each boundary is real, and this is where it is enforced.</b> <c>PlatformBoundaries</c> records
/// which deployable owns the behaviour behind each one and what, if anything, this deployable does
/// about it. For every boundary marked <see cref="MonolithRelationship.None"/> the claim is total:
/// no client package, no type, no configuration section.
/// </para>
/// <para>
/// That claim is stronger than an interface nobody implements, and honest in a way a port would not
/// be — the behaviour lives in RagCore, which is written in Python and can never implement a .NET
/// abstraction. Declaring a port for it would be a speculative abstraction with no first provider,
/// let alone a second (.claude/rules/10-principles.md P-8).
/// </para>
/// </remarks>
public sealed class BoundaryOwnershipTests
{
    [Fact]
    public void Every_declared_boundary_names_an_owner_and_a_relationship()
    {
        // A register with an unset row is a register nobody has filled in, and the tests below
        // would quietly stop covering that boundary.
        List<string> incomplete = PlatformBoundaries.All
            .Where(boundary =>
                boundary.Owner == BoundaryOwner.Unknown ||
                boundary.Relationship == MonolithRelationship.Unknown ||
                string.IsNullOrWhiteSpace(boundary.Rationale))
            .Select(boundary => boundary.Name)
            .ToList();

        Assert.True(incomplete.Count == 0, string.Join("\n  ", incomplete));
    }

    [Fact]
    public void No_service_bus_client_reaches_this_deployable()
    {
        // The monolith is read-only and publishes nothing (ADR-0001). Both the publisher and the
        // resume consumer are RagCore workers, and a trigger is untrusted in any case: it carries
        // only workItemId, correlationId and kind (contracts §triggers).
        AssertNoPackage("Azure.Messaging.ServiceBus");
        AssertNoTypeNamed("ServiceBus");
    }

    [Fact]
    public void No_outbox_or_idempotency_machinery_reaches_this_deployable()
    {
        // Only a writer needs an outbox, and only a state-changing endpoint needs an idempotency
        // key. This deployable has neither. Its one interest in the outbox is the undispatchable
        // case, and that arrives as a published view — vw_approval_unexecuted_v1 — not as a table.
        AssertNoTypeNamed("Outbox");
        AssertNoTypeNamed("IdempotencyStore");
        AssertNoTypeNamed("IdempotencyRecord");
    }

    [Fact]
    public void No_provider_sdk_for_a_boundary_we_do_not_own_reaches_this_deployable()
    {
        // No provider type reaches inward (spec FR-EXT-011). ServiceNow, Graph, MCP and every model
        // provider sit behind RagCore adapters; a client library here would be a second path to a
        // system that is supposed to have exactly one.
        AssertNoPackage("Microsoft.Graph");
        AssertNoPackage("Azure.AI.OpenAI");
        AssertNoPackage("OpenAI");
        AssertNoPackage("Microsoft.Azure.SignalR");
    }

    [Fact]
    public void No_type_suggests_a_direct_model_call()
    {
        // No module holds a provider endpoint outside the model adapter, and that adapter is in
        // RagCore (A2 §9). Model access routes exclusively through the AI
        // Gateway, from the other deployable.
        AssertNoTypeNamed("Completion");
        AssertNoTypeNamed("Embedding");
        AssertNoTypeNamed("ChatClient");
    }

    [Fact]
    public void The_key_vault_boundary_is_consumed_as_infrastructure_and_nothing_more()
    {
        // Key Vault is the sole source of secret material (A2 P09), reached
        // through managed identity as a configuration source. That is infrastructure, not an
        // application dependency — so it appears in the composition root and nowhere else.
        PlatformBoundary vault = PlatformBoundaries.All.Single(b => b.Name == PlatformBoundaries.KeyVault);

        Assert.Equal(MonolithRelationship.ConsumesAsInfrastructure, vault.Relationship);

        IReadOnlyList<string> files = SourceTree.ProductionFilesContaining("AddAzureKeyVault");

        Assert.True(
            files.Count == 1 && files[0] == "ConfigurationRegistration.cs",
            "Key Vault is wired outside the composition root:\n  " + string.Join("\n  ", files));
    }

    [Fact]
    public void No_credential_type_is_constructed_outside_the_composition_root()
    {
        // A credential constructed deep in a service is a second identity for the process, and the
        // one nobody remembers when rotating or scoping the first.
        IReadOnlyList<string> files = SourceTree.ProductionFilesContaining("DefaultAzureCredential");

        Assert.True(
            files.Count <= 1 && (files.Count == 0 || files[0] == "ConfigurationRegistration.cs"),
            "A managed-identity credential is constructed outside the composition root:\n  " +
            string.Join("\n  ", files));
    }

    private static void AssertNoPackage(string assemblyNamePrefix)
    {
        List<string> offending = [];

        foreach (Assembly assembly in ProductionAssemblies.All)
        {
            foreach (AssemblyName referenced in assembly.GetReferencedAssemblies())
            {
                if (referenced.Name?.StartsWith(assemblyNamePrefix, StringComparison.OrdinalIgnoreCase) == true)
                {
                    offending.Add($"{assembly.GetName().Name} -> {referenced.Name}");
                }
            }
        }

        Assert.True(
            offending.Count == 0,
            $"A client for a boundary this deployable does not own has been referenced:\n  " +
            string.Join("\n  ", offending));
    }

    private static void AssertNoTypeNamed(string fragment)
    {
        List<string> offending = [];

        foreach (Assembly assembly in ProductionAssemblies.All)
        {
            foreach (Type type in assembly.GetTypes())
            {
                if (type.Name.Contains(fragment, StringComparison.OrdinalIgnoreCase))
                {
                    offending.Add($"{assembly.GetName().Name}.{type.Name}");
                }
            }
        }

        Assert.True(
            offending.Count == 0,
            $"A type named for a boundary this deployable does not own exists:\n  " +
            string.Join("\n  ", offending));
    }
}
