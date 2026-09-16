import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { SkipLink } from 'design-system';
import { AuthService, intersects, type StaffRole } from 'platform-core';

interface NavItem {
  readonly path: string;
  readonly label: string;
  readonly accepts: readonly StaffRole[];
}

/**
 * Staff portal shell (spec FR-SURF-001).
 *
 * ## Module visibility by role — and what that does not mean
 *
 * The navigation below hides links whose operations the platform would refuse. Spec FR-SURF-003
 * asks the portal to present only the modules the signed-in person's roles grant, and this is that.
 *
 * It is **presentation only**. Backend authorization remains authoritative: every request from
 * every one of these surfaces is re-decided server-side, and a person who types a hidden URL
 * reaches a page whose every call is still refused (FR-SURF-004). If hiding a link were the only
 * thing stopping someone, the defect would be on the server.
 *
 * Membership is set intersection, with no ordering: `administrator` does not imply `technician`
 * (contracts/staff-api.md §Role model).
 *
 * ## No session origination
 *
 * There is no "new session" or "raise a request" control here, and there is no route behind one
 * (FR-SURF-006). Staff needing their own support use a customer surface.
 */
@Component({
  selector: 'app-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, SkipLink],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly auth = inject(AuthService);

  private static readonly NAV: readonly NavItem[] = [
    { path: '/queue', label: 'Approval queue', accepts: ['technician'] },
    { path: '/sessions', label: 'Live sessions', accepts: ['technician'] },
    { path: '/reporting', label: 'Reporting', accepts: ['technician', 'administrator'] },
  ];

  /** Links worth showing. A courtesy filter, never a control. */
  protected readonly visibleNav = computed<readonly NavItem[]>(() => {
    const held = this.auth.rolesForPresentation();
    return App.NAV.filter((item) => intersects(held, item.accepts));
  });
}
