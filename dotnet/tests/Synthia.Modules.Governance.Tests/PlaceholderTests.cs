namespace Synthia.Modules.Governance.Tests;

/// <summary>
/// Stage 1 placeholder so the suite is real and green from the first commit, and CI is
/// proven to actually run this project rather than silently discovering nothing.
/// Replaced by behaviour tests as Synthia.Modules.Governance gains behaviour.
/// </summary>
public sealed class PlaceholderTests
{
    [Fact]
    public void Assembly_under_test_is_referenced()
    {
        Assert.NotNull(typeof(Synthia.Modules.Governance.AssemblyMarker).Assembly);
    }
}
