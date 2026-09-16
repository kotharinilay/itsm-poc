import { DOCUMENT, Injectable, OnDestroy, inject } from '@angular/core';

export type Politeness = 'polite' | 'assertive';

/**
 * Centralised ARIA live-region announcer.
 *
 * Spec FR-SURF-011 is the reason this is a service rather than a component: progressively delivered
 * response content must be announced **as it arrives, announcing only the text not already
 * announced**. A naive implementation writes the whole accumulated response into a live region on
 * every token, and a screen reader then reads the answer back from the beginning each time. That is
 * the defect this class exists to prevent.
 *
 * `announceDelta` keeps the previously announced prefix per stream key and emits only the suffix.
 */
@Injectable({ providedIn: 'root' })
export class LiveAnnouncer implements OnDestroy {
  private readonly document = inject(DOCUMENT);
  private readonly regions = new Map<Politeness, HTMLElement>();
  private readonly announced = new Map<string, string>();

  /** Announce a complete, self-contained message. */
  announce(message: string, politeness: Politeness = 'polite'): void {
    const text = message.trim();
    if (text.length === 0) {
      return;
    }
    this.regionFor(politeness).textContent = text;
  }

  /**
   * Announce only the part of `fullText` not yet announced for `streamKey`.
   *
   * Returns the delta that was announced, which is the empty string when nothing is new. A
   * `fullText` that no longer extends what was announced (a rewrite rather than an append) resets
   * the stream and announces the whole of the new text.
   */
  announceDelta(streamKey: string, fullText: string, politeness: Politeness = 'polite'): string {
    const previous = this.announced.get(streamKey) ?? '';

    if (fullText === previous) {
      return '';
    }

    const delta = fullText.startsWith(previous) ? fullText.slice(previous.length) : fullText;
    this.announced.set(streamKey, fullText);

    const trimmed = delta.trim();
    if (trimmed.length > 0) {
      this.regionFor(politeness).textContent = trimmed;
    }
    return delta;
  }

  /** Forget a stream once it is complete, so a later stream reusing the key starts clean. */
  endStream(streamKey: string): void {
    this.announced.delete(streamKey);
  }

  clear(politeness: Politeness = 'polite'): void {
    this.regionFor(politeness).textContent = '';
  }

  ngOnDestroy(): void {
    for (const region of this.regions.values()) {
      region.remove();
    }
    this.regions.clear();
    this.announced.clear();
  }

  private regionFor(politeness: Politeness): HTMLElement {
    const existing = this.regions.get(politeness);
    if (existing !== undefined) {
      return existing;
    }

    const region = this.document.createElement('div');
    region.setAttribute('aria-live', politeness);
    region.setAttribute('aria-atomic', 'false');
    region.setAttribute('role', politeness === 'assertive' ? 'alert' : 'status');
    region.classList.add('ds-visually-hidden');
    // Kept off-screen rather than display:none — a hidden region is not announced at all.
    region.style.cssText =
      'position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;' +
      'clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap;border:0;';

    this.document.body.appendChild(region);
    this.regions.set(politeness, region);
    return region;
  }
}
