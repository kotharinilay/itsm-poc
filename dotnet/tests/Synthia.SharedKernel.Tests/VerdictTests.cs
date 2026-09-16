using Synthia.SharedKernel.Governance;

namespace Synthia.SharedKernel.Tests;

/// <summary>
/// Verdict and status types (contract-freeze findings F-1, F-2, F-6, F-7).
/// </summary>
/// <remarks>
/// Mirrors <c>ragcore/tests/unit/test_verdicts.py</c>. These exist because the first version of the
/// approval port took the work item's approval state as its verdict parameter, which made
/// "record an expiry as a human verdict" type-check. §17.7 and <c>FR-INTR-008</c> prohibit a
/// system-synthesized verdict outright; the narrower type is what makes it unrepresentable rather
/// than merely forbidden.
/// </remarks>
public sealed class VerdictTests
{
    [Fact]
    public void Approval_verdict_has_exactly_two_decided_values()
    {
        // Unknown is the unset sentinel every C# enum needs at 0 so a default-constructed value is
        // not silently a real verdict. It is not a decision a human can record.
        ApprovalVerdict[] decided = Enum.GetValues<ApprovalVerdict>()
            .Where(v => v != ApprovalVerdict.Unknown)
            .ToArray();

        Assert.Equal(2, decided.Length);
        Assert.Contains(ApprovalVerdict.Approved, decided);
        Assert.Contains(ApprovalVerdict.Rejected, decided);
    }

    [Theory]
    [InlineData("Expired")]
    [InlineData("Pending")]
    [InlineData("Timeout")]
    [InlineData("Auto")]
    [InlineData("RejectAndTakeOver")]
    public void Approval_verdict_carries_no_member_that_would_be_synthesized(string forbidden)
    {
        // §17.7: "No timeout, no auto-reject, no system-synthesized verdict."
        // RejectAndTakeOver is excluded for a different reason (§17.6): it is a rejection PLUS a
        // session transition, recorded as two facts. A third verdict value would make the takeover
        // invisible to anything reading the verdict alone.
        Assert.DoesNotContain(forbidden, Enum.GetNames<ApprovalVerdict>(), StringComparer.Ordinal);
    }

    [Fact]
    public void Consent_verdict_has_exactly_two_decided_values()
    {
        ConsentVerdict[] decided = Enum.GetValues<ConsentVerdict>()
            .Where(v => v != ConsentVerdict.Unknown)
            .ToArray();

        Assert.Equal(2, decided.Length);
        Assert.Contains(ConsentVerdict.Granted, decided);
        Assert.Contains(ConsentVerdict.Refused, decided);
    }

    [Fact]
    public void Operation_status_matches_the_data_model()
    {
        string[] expected = ["Proposed", "Gated", "Authorized", "Executed", "Failed", "Refused"];

        string[] actual = Enum.GetNames<OperationStatus>()
            .Where(n => !string.Equals(n, "Unknown", StringComparison.Ordinal))
            .ToArray();

        Assert.Equal(expected.Order(StringComparer.Ordinal), actual.Order(StringComparer.Ordinal));
    }

    [Fact]
    public void Operation_status_can_record_a_refusal()
    {
        // FR-AUDIT-003: decisions that deny are recorded as durably as decisions that permit.
        // Without this member a NOT_ALLOWED outcome has nowhere to be written.
        Assert.Contains("Refused", Enum.GetNames<OperationStatus>(), StringComparer.Ordinal);
        Assert.Contains("Gated", Enum.GetNames<OperationStatus>(), StringComparer.Ordinal);
    }

    [Fact]
    public void Execution_method_matches_the_data_model()
    {
        string[] expected = ["Workload", "DesktopScript", "None"];

        string[] actual = Enum.GetNames<ExecutionMethod>()
            .Where(n => !string.Equals(n, "Unknown", StringComparison.Ordinal))
            .ToArray();

        Assert.Equal(expected.Order(StringComparer.Ordinal), actual.Order(StringComparer.Ordinal));
    }

    [Fact]
    public void Execution_treatment_still_has_no_default_member()
    {
        // Guarding a property established in Phase 2 and easy to erode: a missing treatment must
        // not be representable, so "we could not determine it, carry on" cannot be expressed.
        // Unlike the verdict enums, this one deliberately has NO Unknown at 0.
        Assert.DoesNotContain("Unknown", Enum.GetNames<ExecutionTreatment>(), StringComparer.Ordinal);
        Assert.DoesNotContain("Default", Enum.GetNames<ExecutionTreatment>(), StringComparer.Ordinal);
        Assert.DoesNotContain("None", Enum.GetNames<ExecutionTreatment>(), StringComparer.Ordinal);
        Assert.Equal(4, Enum.GetValues<ExecutionTreatment>().Length);
    }
}
