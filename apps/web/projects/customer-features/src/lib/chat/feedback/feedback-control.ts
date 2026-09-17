import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { LiveAnnouncer } from 'design-system';
import { CustomerApiClient, type MessageId } from 'platform-core';

/** The two signals, and a third state meaning "none recorded". */
export type FeedbackState = 'positive' | 'negative' | 'none';

/**
 * A per-message thumbs control — **keyboard-operable, announced, and with its state visible**.
 *
 * ## What the specification asks for, and where each part lives here
 *
 * * `FR-SESS-009`: a binary signal against one agent-authored message. Two buttons, two values.
 * * `SC-SESS-003`: **operable from the keyboard and announced to assistive technology**. They are
 *   `<button>` elements, so focus, Enter and Space come from the platform rather than from a
 *   `keydown` handler somebody has to get right. A `<div role="button">` would need `tabindex`,
 *   two key handlers and an `aria-pressed` — three chances to be wrong, for no gain.
 * * **The current state is visible**, not only announced: `aria-pressed` carries it for assistive
 *   technology and `data-state` drives a visible treatment, so the recorded signal is conveyed by
 *   more than colour.
 *
 * ## What it deliberately does not do
 *
 * **Feedback never influences authorization, governance treatment, retrieval scope or execution**
 * (spec FR-SESS-013). This component records a signal and reads nothing back into the conversation:
 * there is no branch here that changes what is shown, retried or offered because of what was
 * recorded.
 *
 * **It is revisable, not accumulating** (`FR-SESS-010`). Pressing the pressed button withdraws;
 * pressing the other replaces. Both are `PUT`/`DELETE` against the same message, so repeating
 * either is idempotent and two tabs cannot produce two signals.
 *
 * **Optimistic, and honest when it fails.** The state updates immediately because a thumbs control
 * that waits for a round trip feels broken, and reverts on failure with an announcement — a control
 * that silently kept the optimistic state would be showing a signal the platform does not hold.
 */
@Component({
  selector: 'cf-feedback-control',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feedback-control.html',
  styleUrl: './feedback-control.css',
})
export class FeedbackControl {
  private readonly api = inject(CustomerApiClient);
  private readonly announcer = inject(LiveAnnouncer);

  /** The agent-authored message this control rates. */
  readonly messageId = input.required<MessageId>();

  /** The signal already recorded, when the surface knows of one. */
  readonly initial = input<FeedbackState>('none');

  /** The signal currently shown. Initialised from {@link initial} on first read. */
  protected readonly state = signal<FeedbackState | null>(null);

  /** Set when the last attempt did not reach the platform. Rendered, not only announced. */
  protected readonly failed = signal(false);

  protected current(): FeedbackState {
    return this.state() ?? this.initial();
  }

  /**
   * Record, replace or withdraw.
   *
   * Pressing the already-pressed button withdraws it — which is what `aria-pressed` leads a
   * screen-reader user to expect, and what a sighted user expects from a toggle.
   */
  protected choose(signalValue: 'positive' | 'negative'): void {
    const previous = this.current();
    const next: FeedbackState = previous === signalValue ? 'none' : signalValue;

    this.state.set(next);
    this.failed.set(false);
    this.announcer.announce(ANNOUNCEMENTS[next]);

    const request =
      next === 'none'
        ? this.api.withdrawFeedback(this.messageId())
        : this.api.recordFeedback(this.messageId(), { signal: next });

    request.subscribe({
      error: () => {
        // Reverted, and said so. Keeping the optimistic state would show a signal the platform
        // does not hold, which is a small lie the user has no way to detect.
        this.state.set(previous);
        this.failed.set(true);
        this.announcer.announce('Your feedback could not be saved.', 'assertive');
      },
    });
  }
}

/**
 * What each state is announced as.
 *
 * Whole sentences rather than the enum value: "positive" read aloud on its own says nothing about
 * what just happened, and a control whose announcement is its internal vocabulary is one nobody
 * outside the team can use.
 */
const ANNOUNCEMENTS: Record<FeedbackState, string> = {
  positive: 'Marked as helpful.',
  negative: 'Marked as not helpful.',
  none: 'Feedback withdrawn.',
};
