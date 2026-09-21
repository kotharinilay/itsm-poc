import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { AsyncStateContainer, type AsyncState, LiveAnnouncer, idle, ready } from 'design-system';
import {
  CustomerApiClient,
  MessageStreamClient,
  type ConversationMessage,
  type SessionId,
  type StepTrailEntry,
  type StreamEvent,
} from 'platform-core';
import type { Subscription } from 'rxjs';

/**
 * Chat surface — consumes the SSE stream and announces it accessibly.
 *
 * ## The stream carries no authority
 *
 * An `interrupt` event tells this surface that a decision is needed. **It is not the decision, and
 * this component cannot make one.** There is no branch below that records a consent, sets an
 * approval or enables an action because a frame arrived: the decision is made by calling the
 * consent or answer endpoint, authenticated, where it is recorded durably.
 *
 * **The stream ending is not a decision either** (contracts/customer-api.md). A dropped connection,
 * a timeout or a closed laptop leaves the work exactly where it was — suspended, indefinitely — so
 * `done` and a transport error are shown as what they are and never as a resolution.
 *
 * ## Accessibility (spec FR-SURF-011)
 *
 * Progressively delivered content is announced **as it arrives, announcing only the text not
 * already announced**. `LiveAnnouncer.announceDelta` is what does that, keyed by session: the naive
 * implementation writes the whole accumulated response into a live region on every token, and a
 * screen reader then reads the answer back from the beginning each time.
 *
 * Step frames are announced too, because a sighted user sees progress and a screen-reader user
 * would otherwise hear silence for the same period. They are announced as complete messages rather
 * than deltas — a step is a whole statement, not a continuation of the previous one.
 *
 * Every interrupt carries a machine-readable `kind`, so state is conveyed by **more than colour**.
 */
@Component({
  selector: 'cf-chat-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [AsyncStateContainer],
  templateUrl: './chat-shell.html',
  styleUrl: './chat-shell.css',
})
export class ChatShell {
  /** Injected, not constructor-parameterised — `inject()` where appropriate (FE-NG-3, .claude/rules/23-angular.md). */
  protected readonly api = inject(CustomerApiClient);
  protected readonly stream = inject(MessageStreamClient);
  protected readonly announcer = inject(LiveAnnouncer);
  private readonly destroyRef = inject(DestroyRef);

  /** No read is in flight yet: `idle` is the honest state before anything has been asked. */
  protected readonly messages = signal<AsyncState<readonly ConversationMessage[]>>(idle());

  /** The response as it accumulates. Rendered progressively; announced as deltas. */
  protected readonly streamed = signal('');

  /** The step trail, newest last. Identifiers and labels only — never command content. */
  protected readonly steps = signal<readonly StepTrailEntry[]>([]);

  /**
   * Which interruption the work is suspended on, or `null`.
   *
   * A kind, and nothing else. There is deliberately no `canApprove`, no `workItem` and no
   * disclosure of what would run: a client that needs a disclosure fetches it from an authenticated
   * API, where the caller is known.
   */
  protected readonly pendingInterrupt = signal<string | null>(null);

  /** Whether a turn is in flight. Drives the busy state; never gates anything consequential. */
  protected readonly sending = signal(false);

  /**
   * Set when the turn could not be completed.
   *
   * Distinct from "the turn finished with nothing to say", because a failure MUST NOT be presented
   * as an empty result (spec FR-SURF-016).
   */
  protected readonly failure = signal<string | null>(null);

  private subscription: Subscription | null = null;

  constructor() {
    // Unsubscribing aborts the request. Aborting is **not** a cancellation of the work:
    // disconnection never cancels work or changes any state (spec FR-SESS-017).
    this.destroyRef.onDestroy(() => this.subscription?.unsubscribe());
  }

  /** Send a turn and consume the response as it arrives. */
  protected send(sessionId: SessionId, content: string): void {
    const text = content.trim();
    if (text.length === 0 || this.sending()) {
      return;
    }

    this.subscription?.unsubscribe();
    this.reset(sessionId);
    this.sending.set(true);

    this.subscription = this.stream.send(sessionId, { content: text }).subscribe({
      next: (event) => this.apply(sessionId, event),
      error: () => this.fail(sessionId, 'The connection was lost before the turn finished.'),
    });
  }

  /**
   * Apply one stream event.
   *
   * Exhaustive over `StreamEvent` by construction: every kind is handled, and an unrecognised frame
   * never reaches here because `parseFrame` drops what it cannot type rather than guessing.
   */
  private apply(sessionId: SessionId, event: StreamEvent): void {
    switch (event.kind) {
      case 'token': {
        // Incremental by contract — `text` is what is new, never the accumulated message. The
        // announcer still takes the accumulation and computes the delta itself, so a server that
        // one day sent the whole message would not make a screen reader re-read it.
        const accumulated = this.streamed() + event.text;
        this.streamed.set(accumulated);
        this.announcer.announceDelta(sessionId, accumulated);
        break;
      }
      case 'step': {
        this.steps.update((trail) => [...trail, event.step]);
        this.announcer.announce(event.step.label);
        break;
      }
      case 'interrupt': {
        // Recorded and announced. **Nothing is enabled by it.** The decision is made by calling an
        // authenticated endpoint; this frame asks for nothing and can receive nothing.
        this.pendingInterrupt.set(event.interrupt);
        // A kind with no wording falls back to the generic sentence rather than announcing its
        // identifier. A new interrupt kind should not reach a user as `staff_approval`.
        this.announcer.announce(
          INTERRUPT_ANNOUNCEMENTS[event.interrupt] ?? INTERRUPT_FALLBACK,
          'assertive',
        );
        break;
      }
      case 'done': {
        // The TURN finished. Not a statement that anything was authorized, executed or resolved —
        // those are separate facts on separate records, read under the caller's own identity.
        this.sending.set(false);
        this.announcer.endStream(sessionId);
        break;
      }
      case 'error': {
        this.fail(sessionId, event.title);
        break;
      }
    }
  }

  private fail(sessionId: SessionId, title: string): void {
    this.sending.set(false);
    this.failure.set(title);
    this.announcer.endStream(sessionId);
    // Assertive: a failed turn is not something to discover on the next tab stop.
    this.announcer.announce(title, 'assertive');
  }

  private reset(sessionId: SessionId): void {
    this.streamed.set('');
    this.steps.set([]);
    this.pendingInterrupt.set(null);
    this.failure.set(null);
    this.announcer.endStream(sessionId);
    this.messages.set(ready([]));
  }
}

/**
 * What a suspension is announced as.
 *
 * A closed mapping rather than a rendering of the kind, so the announcement is a sentence rather
 * than an identifier — and so a new interrupt kind cannot ship without somebody writing what a
 * screen-reader user hears.
 *
 * None of these says a decision has been made, and none offers to make one.
 */
const INTERRUPT_FALLBACK = 'This is waiting on a decision before anything happens.';

const INTERRUPT_ANNOUNCEMENTS: Record<string, string> = {
  clarification: 'A question is waiting for your answer.',
  consent: 'Your permission is needed before anything happens.',
  staff_approval: 'This is waiting for a member of the support team to decide.',
  end_user_approval: 'Your permission is needed before anything happens.',
};
