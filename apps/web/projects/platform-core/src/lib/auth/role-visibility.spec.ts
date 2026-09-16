import type { StaffRole } from '../contracts/primitives';
import { STAFF_ROLES } from '../contracts/primitives';
import { intersects } from './role-visibility';

/**
 * Mirrors `dotnet/tests/Synthia.SharedKernel.Tests/RoleIntersectionTests.cs` and
 * `ragcore/tests/unit/test_roles.py`, so the rule is proven independently on all three stacks.
 */
describe('role visibility (presentation only)', () => {
  it('denies when the intersection is empty', () => {
    expect(intersects(['administrator'], ['technician'])).toBeFalse();
  });

  it('permits when the intersection is non-empty', () => {
    expect(intersects(['technician'], ['technician'])).toBeTrue();
  });

  it('denies when no role is held', () => {
    expect(intersects([], ['technician'])).toBeFalse();
  });

  it('denies when the operation accepts no role', () => {
    expect(intersects(['technician'], [])).toBeFalse();
  });

  // contracts/staff-api.md §Role model: administrator does not imply technician.
  it('does not let administrator imply technician', () => {
    expect(intersects(['administrator'], ['technician'])).toBeFalse();
  });

  it('does not let senior_technician imply technician', () => {
    expect(intersects(['senior_technician'], ['technician'])).toBeFalse();
  });

  it('implies nothing in either direction, for every ordered pair of distinct roles', () => {
    for (const held of STAFF_ROLES) {
      for (const accepted of STAFF_ROLES) {
        if (held !== accepted) {
          expect(intersects([held], [accepted]))
            .withContext(`${held} must not imply ${accepted}`)
            .toBeFalse();
        }
      }
    }
  });

  it('is unaffected by the order roles are listed in', () => {
    const forward: readonly StaffRole[] = ['administrator', 'technician'];
    const reverse: readonly StaffRole[] = ['technician', 'administrator'];
    expect(intersects(forward, ['technician'])).toBe(intersects(reverse, ['technician']));
  });

  it('matches on any held role, not only the first', () => {
    expect(intersects(['administrator', 'technician'], ['technician'])).toBeTrue();
  });
});
