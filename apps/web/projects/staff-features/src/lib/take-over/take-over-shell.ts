import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { AsyncStateContainer, type AsyncState, idle } from 'design-system';
import { StaffApiClient, type LiveSession } from 'platform-core';

/**
 * Take-over shell — joining an end user's session as an additional sender.
 *
 * Structural shell only — no take-over behaviour is implemented.
 *
 * Take-over is **participation, not origination** (spec FR-SURF-009). A staff member joining a
 * session does not become its requester, does not gain the requester's authority over the work, and
 * cannot consent on that person's behalf. There is deliberately no control on this surface that
 * would start a session — see `staff-features.routes.ts`.
 */
@Component({
  selector: 'sf-take-over-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [AsyncStateContainer],
  templateUrl: './take-over-shell.html',
  styleUrl: './take-over-shell.css',
})
export class TakeOverShell {
  protected readonly api = inject(StaffApiClient);
  protected readonly sessions = signal<AsyncState<readonly LiveSession[]>>(idle());
}
