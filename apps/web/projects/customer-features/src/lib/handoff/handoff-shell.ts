import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { LiveAnnouncer } from 'design-system';
import { RealtimeService } from 'platform-core';

/**
 * Hand-off shell — shows that a person has joined the conversation.
 *
 * Structural shell only.
 *
 * A `session.taken_over` notification tells this surface that somebody joined. That is all it tells
 * it: the envelope carries no authority-bearing value, and take-over transfers no requester
 * authority to the staff member (spec FR-SURF-009). Consent for this person's own account or device
 * still belongs to them.
 */
@Component({
  selector: 'cf-handoff-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './handoff-shell.html',
  styleUrl: './handoff-shell.css',
})
export class HandoffShell {
  protected readonly realtime = inject(RealtimeService);
  protected readonly announcer = inject(LiveAnnouncer);

  protected readonly staffPresent = signal(false);
}
