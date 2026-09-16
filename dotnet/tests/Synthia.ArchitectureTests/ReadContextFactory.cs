using Microsoft.EntityFrameworkCore;
using Synthia.Persistence;
using Synthia.SharedKernel.Identity;

namespace Synthia.ArchitectureTests;

/// <summary>
/// Builds a read context for tests that inspect the model.
/// </summary>
/// <remarks>
/// <b>No connection is opened.</b> Everything asserted here — the mapping, the query filters, the
/// tracking behaviour, the refusal to save — is decided when EF builds the model, which happens
/// without ever reaching the server. A test needing rows is an integration test and belongs where a
/// real PostgreSQL can be started.
/// </remarks>
internal static class ReadContextFactory
{
    /// <summary>Creates a context bound to no organisation.</summary>
    /// <returns>The context. The caller disposes it.</returns>
    public static SynthiaReadContext Create()
    {
        DbContextOptions<SynthiaReadContext> options =
            new DbContextOptionsBuilder<SynthiaReadContext>()
                .UseNpgsql("Host=architecture-tests.invalid;Database=synthia;Username=reader;Password=unused")
                .UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking)
                .Options;

        return new SynthiaReadContext(options, new UnboundScope());
    }

    private sealed class UnboundScope : ITenantScope
    {
        public TenantScopeKind Kind => TenantScopeKind.None;

        public TenantContext? Organisation => null;
    }
}
