using System.Reflection;
using Synthia.SharedKernel.Authorization;
using Synthia.SharedKernel.Identity;

namespace Synthia.AuthorizationTests;

/// <summary>
/// Roles are disjoint capability sets, never a hierarchy (T159).
/// </summary>
/// <remarks>
/// <b><c>administrator</c> does NOT imply <c>technician</c></b> (spec FR-AUTHZ-003). Implied
/// seniority is the classic route to silent privilege escalation, and the reason it stays silent is
/// that it looks reasonable in the diff that introduces it.
/// </remarks>
public sealed class NoImpliedPrivilegeTests
{
    [Fact]
    public void Administrator_does_not_imply_technician()
    {
        RoleSet administrator = RoleSet.Of(StaffRole.Administrator);

        // In the initial release technician may approve and administrator may not. If this ever
        // passes, an administrator can approve their own organisation's governed actions.
        Assert.False(RoleIntersection.Evaluate(administrator, RoleSet.Of(StaffRole.Technician)).IsPermitted);
    }

    [Fact]
    public void Technician_does_not_imply_administrator()
    {
        // The other direction, which is the one people remember to prevent. Both are asserted so
        // neither is left resting on the other being checked.
        RoleSet technician = RoleSet.Of(StaffRole.Technician);

        Assert.False(RoleIntersection.Evaluate(technician, RoleSet.Of(StaffRole.Administrator)).IsPermitted);
    }

    [Fact]
    public void Senior_technician_does_not_imply_technician()
    {
        // The name is the trap: "senior" reads like "technician and more". It is neither.
        RoleSet senior = RoleSet.Of(StaffRole.SeniorTechnician);

        Assert.False(RoleIntersection.Evaluate(senior, RoleSet.Of(StaffRole.Technician)).IsPermitted);
    }

    [Fact]
    public void No_role_is_comparable_to_another()
    {
        // Any implementation that sorts, ranks, compares or upgrades roles is a defect
        // (constitution Principle II). A role type implementing IComparable is how ranking gets in:
        // the operators exist, someone writes >=, and seniority is suddenly real.
        Assert.False(
            typeof(StaffRole).GetInterfaces().Any(contract =>
                contract == typeof(IComparable) ||
                (contract.IsGenericType && contract.GetGenericTypeDefinition() == typeof(IComparable<>))),
            "StaffRole is comparable. Roles are disjoint capability sets, and a comparable role is " +
            "one somebody will eventually rank.");

        string[] ordering = ["op_GreaterThan", "op_LessThan", "op_GreaterThanOrEqual", "op_LessThanOrEqual"];

        Assert.DoesNotContain(
            typeof(StaffRole).GetMethods(BindingFlags.Public | BindingFlags.Static),
            method => ordering.Contains(method.Name, StringComparer.Ordinal));
    }

    [Fact]
    public void A_role_set_is_order_independent()
    {
        // Token array order never decides anything. Two spellings of the same set must be the same
        // set, or an authorization outcome depends on how a header was serialised upstream.
        RoleSet oneWay = RoleSet.Of(StaffRole.Technician, StaffRole.Administrator);
        RoleSet otherWay = RoleSet.Of(StaffRole.Administrator, StaffRole.Technician);

        Assert.Equal(oneWay, otherWay);
        Assert.Equal(oneWay.GetHashCode(), otherWay.GetHashCode());
    }

    [Fact]
    public void A_staff_principal_on_the_customer_audience_holds_only_the_end_user_role()
    {
        // Any person acting on a customer surface is an end user — including staff — and their
        // staff roles MUST NOT be consulted there (constitution Principle II, spec FR-SURF-008).
        // Enforced by the type rather than by every call site remembering it.
        Assert.True(PrincipalFactory.TryCreate(
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            "administrator,technician",
            "delegated",
            "staff-portal",
            Audience.Customer,
            out AuthenticatedPrincipal? principal,
            out _));

        Assert.Equal(RoleSet.Of(StaffRole.EndUser), principal!.AuthorizableRoles);

        // The raw set is still recorded — losing it would destroy the audit trail of who the person
        // actually is — it simply is not what authorization consults here.
        Assert.True(principal.Roles.Contains(StaffRole.Administrator));
        Assert.False(
            RoleIntersection.Evaluate(principal.AuthorizableRoles, RoleSet.Of(StaffRole.Administrator))
                .IsPermitted);
    }

    [Fact]
    public void A_staff_principal_on_the_staff_audience_keeps_its_roles()
    {
        // The mirror of the test above. Without it, "customer audience strips roles" could be
        // satisfied by an implementation that strips them everywhere.
        Assert.True(PrincipalFactory.TryCreate(
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            "technician",
            "delegated",
            "staff-portal",
            Audience.Staff,
            out AuthenticatedPrincipal? principal,
            out _));

        Assert.True(
            RoleIntersection.Evaluate(principal!.AuthorizableRoles, RoleSet.Of(StaffRole.Technician))
                .IsPermitted);
    }
}
