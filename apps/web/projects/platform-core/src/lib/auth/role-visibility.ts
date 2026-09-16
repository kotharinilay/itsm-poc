import { inject } from '@angular/core';
import type { CanMatchFn } from '@angular/router';
import type { StaffRole } from '../contracts/primitives';
import { AuthService } from './auth.service';

/**
 * Presentation-only role gating.
 *
 * ## What this is
 *
 * A way to avoid showing somebody a menu item that the platform will refuse. That is the whole of
 * it. It is a courtesy, not a control.
 *
 * ## What this is not
 *
 * **Backend authorization remains authoritative.** Spec FR-SURF-004: no client surface makes an
 * authorization, tenancy or policy decision, and every client-side role check is re-decided
 * server-side. A route guard is not a security boundary — the person holds the browser, and can
 * reach any route in it. Removing every check in this file must change nothing about what the
 * platform permits. If it would, the defect is on the server.
 *
 * ## Set intersection, and no ordering
 *
 * `technician`, `senior_technician` and `administrator` are independent capabilities with no
 * hierarchy (contracts/staff-api.md §Role model). `administrator` does not imply `technician`. The
 * evaluation below is set intersection and nothing else; an empty intersection denies. There is no
 * comparison, no ranking and no sort anywhere in this file, and `RoleIntersectionTests` on the .NET
 * side and `test_roles.py` on the RagCore side assert the same rule independently.
 */
export function intersects(held: readonly StaffRole[], accepted: readonly StaffRole[]): boolean {
  // `some`/`includes` only. Any `<`, `>` or `sort` on a role would be a defect.
  return held.some((role) => accepted.includes(role));
}

/**
 * A `CanMatch` guard that hides a route the platform would refuse anyway.
 *
 * Read the name literally: it hides a route for convenience. It secures nothing. A person who
 * navigates past it reaches a surface whose every request is still authorized by the platform.
 */
export function canMatchForPresentation(accepted: readonly StaffRole[]): CanMatchFn {
  return () => {
    const auth = inject(AuthService);
    return intersects(auth.rolesForPresentation(), accepted);
  };
}
