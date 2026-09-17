import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { LiveAnnouncer } from 'design-system';
import { RealtimeService } from 'platform-core';

/**
 * The hand-off notice — **says plainly that a person will take the request** (spec FR-FALL-007).
 *
 * ## Why the wording is the feature
 *
 * The tempting copy is "we're looking into it", which is true of both outcomes and therefore tells
 * a user nothing. The two states below say which of them has happened, and they say what the person
 * should expect next:
 *
 * * **Handed over**: a person now has this. The user does not need to do anything, and somebody
 *   will come back to them.
 * * **Declined**: nobody has it, and the user will need to raise it elsewhere. Saying "I have
 *   passed this on" here would be a lie discovered only by waiting for a reply that never comes.
 *
 * The reason is shown alongside, because `FR-FALL-010` requires the user to be told **why** — and
 * "I could not find guidance specific to your organisation" and "this needs an approval I cannot
 * ask for here" lead to completely different expectations about what happens next.
 *
 * ## What a notification may and may not do here
 *
 * A `session.taken_over` notification tells this surface that somebody joined. **That is all it
 * tells it.** The envelope carries no authority-bearing value, and take-over transfers no requester
 * authority to the staff member (spec FR-SURF-009) — consent for this person's own account or
 * device still belongs to them, and nothing here grants, implies or offers it.
 *
 * The realtime channel is a **leaf**: this surface reflects a push when one arrives and the same
 * facts are readable from the authenticated API when one does not, so a client that never connects
 * is not a client that misses the outcome.
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
  private readonly destroyRef = inject(DestroyRef);

  /** Whether a member of staff has joined the conversation. */
  protected readonly staffPresent = signal(false);

  /**
   * Whether the request has been handed to a person.
   *
   * Distinct from {@link staffPresent}: an escalation is queued and somebody will pick it up; a
   * take-over is somebody already here. Collapsing them would tell a user to expect a reply in a
   * conversation nobody has joined.
   */
  protected readonly handedOver = signal(false);

  /** Whether the platform declined the request outright, so nobody is picking it up. */
  protected readonly declined = signal(false);

  /**
   * Why, in the platform's own words — the sentence `EscalationReason` carries.
   *
   * Taken from the platform rather than composed here, so the reason a technician reads on the
   * queue item and the reason the user is shown cannot drift apart.
   */
  protected readonly reason = signal('');

  constructor() {
    this.destroyRef.onDestroy(() => this.announcer.clear());
  }

  /** Reflect that the request has been queued for a person, and say why. */
  protected noteHandover(reason: string): void {
    this.handedOver.set(true);
    this.declined.set(false);
    this.reason.set(reason);
    // Assertive: this changes what the user should expect to happen next, and is not something to
    // discover on the next tab stop.
    this.announcer.announce(`${HANDOVER_HEADLINE} ${reason}`, 'assertive');
  }

  /** Reflect that the platform declined, and that nothing was passed on. */
  protected noteDecline(reason: string): void {
    this.declined.set(true);
    this.handedOver.set(false);
    this.reason.set(reason);
    this.announcer.announce(`${DECLINE_HEADLINE} ${reason}`, 'assertive');
  }

  /** Reflect a `session.taken_over` notification. It confers nothing; it reports presence. */
  protected noteTakeover(): void {
    this.staffPresent.set(true);
    this.announcer.announce('A member of the support team has joined this conversation.');
  }
}

/** The two headlines, kept beside the component so the announcement and the template agree. */
export const HANDOVER_HEADLINE = 'A member of the support team will take this from here.';
export const DECLINE_HEADLINE = 'This has not been passed on.';
