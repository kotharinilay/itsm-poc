import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { AsyncStateContainer, type AsyncState, LiveAnnouncer, idle } from 'design-system';
import { CustomerApiClient, type ConversationMessage } from 'platform-core';

/**
 * Chat surface shell.
 *
 * **Structural shell only.** It wires the surface to the centralised infrastructure and renders the
 * state vocabulary; it implements no conversation behaviour (constitution P-IX — scaffold
 * honestly). Sending, streaming and interrupt handling arrive with the golden paths in Stages 12
 * and 13.
 *
 * The infrastructure it depends on is deliberately all injected and all shared: one API client, one
 * announcer. A feature that reached for its own would be the start of the duplication the
 * constitution §Angular forbids.
 */
@Component({
  selector: 'cf-chat-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [AsyncStateContainer],
  templateUrl: './chat-shell.html',
  styleUrl: './chat-shell.css',
})
export class ChatShell {
  /** Injected, not constructor-parameterised — `inject()` where appropriate (constitution). */
  protected readonly api = inject(CustomerApiClient);
  protected readonly announcer = inject(LiveAnnouncer);

  /** No read is in flight yet: `idle` is the honest state for a shell. */
  protected readonly messages = signal<AsyncState<readonly ConversationMessage[]>>(idle());
}
