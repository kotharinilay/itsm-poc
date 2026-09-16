import { Directive, ElementRef, OnDestroy, effect, inject, input } from '@angular/core';
import { focusableWithin } from './focusable';

/**
 * Confines Tab/Shift+Tab to the host element while it is active, and restores focus to whatever was
 * focused before it opened.
 *
 * Required by spec FR-SURF-012: consent prompts and approval decisions carry consequential outcomes
 * and MUST be fully operable by keyboard alone. A dialog a keyboard user can tab out of — into
 * content the dialog is covering — is not operable.
 *
 * This is a presentation affordance. It constrains where focus goes; it decides nothing.
 */
@Directive({
  selector: '[dsFocusTrap]',
  host: {
    // One handler rather than the `keydown.Tab` pseudo-event: with `typeCheckHostBindings` the
    // pseudo-event still types `$event` as a bare `Event`, so the narrowing happens here instead.
    '(keydown)': 'onKeydown($event)',
  },
})
export class FocusTrap implements OnDestroy {
  /** Whether the trap is armed. A closed dialog leaves focus alone. */
  readonly dsFocusTrap = input<boolean>(true);

  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private previouslyFocused: HTMLElement | null = null;

  constructor() {
    effect(() => {
      if (this.dsFocusTrap()) {
        this.arm();
      } else {
        this.release();
      }
    });
  }

  ngOnDestroy(): void {
    this.release();
  }

  protected onKeydown(event: Event): void {
    if (!this.dsFocusTrap() || !(event instanceof KeyboardEvent) || event.key !== 'Tab') {
      return;
    }

    const focusable = focusableWithin(this.host.nativeElement);
    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (first === undefined || last === undefined) {
      // Nothing to move to; keep focus on the container rather than letting it escape.
      event.preventDefault();
      return;
    }

    const active = this.activeElement();

    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
      return;
    }

    if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  private arm(): void {
    const active = this.activeElement();
    if (active !== null && !this.host.nativeElement.contains(active)) {
      this.previouslyFocused = active;
    }

    const focusable = focusableWithin(this.host.nativeElement);
    const target = focusable[0] ?? this.host.nativeElement;

    if (target === this.host.nativeElement && !target.hasAttribute('tabindex')) {
      target.setAttribute('tabindex', '-1');
    }
    target.focus();
  }

  private release(): void {
    const restoreTo = this.previouslyFocused;
    this.previouslyFocused = null;
    if (restoreTo !== null && restoreTo.isConnected) {
      restoreTo.focus();
    }
  }

  private activeElement(): HTMLElement | null {
    const active = this.host.nativeElement.ownerDocument.activeElement;
    return active instanceof HTMLElement ? active : null;
  }
}
