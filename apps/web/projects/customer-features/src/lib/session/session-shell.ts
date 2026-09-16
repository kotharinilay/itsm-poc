import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { AsyncStateContainer, type AsyncState, StatusIndicator, idle } from 'design-system';
import { CustomerApiClient, RealtimeService, type SessionSummary } from 'platform-core';

/**
 * Session listing shell.
 *
 * Structural shell only — no session behaviour is implemented.
 *
 * It holds the seam for spec FR-SESS-019: `RealtimeService.resyncRequired` increments on every
 * reconnect, and this surface responds by re-reading the listing from the API. It never rebuilds
 * from notifications it may have missed, because the channel is allowed to drop them.
 */
@Component({
  selector: 'cf-session-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [AsyncStateContainer, StatusIndicator],
  templateUrl: './session-shell.html',
  styleUrl: './session-shell.css',
})
export class SessionShell {
  protected readonly api = inject(CustomerApiClient);
  protected readonly realtime = inject(RealtimeService);

  protected readonly sessions = signal<AsyncState<readonly SessionSummary[]>>(idle());
}
