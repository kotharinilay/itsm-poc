import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Busy indicator that announces itself. A silent spinner is invisible to a screen reader. */
@Component({
  selector: 'ds-loading-state',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="ds-loading" role="status" aria-live="polite" [attr.aria-busy]="true">
      <span class="ds-loading__spinner" aria-hidden="true"></span>
      <span class="ds-loading__label">{{ label() }}</span>
    </div>
  `,
  styles: `
    .ds-loading {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 1rem;
    }
    .ds-loading__spinner {
      inline-size: 1rem;
      block-size: 1rem;
      border: 2px solid currentcolor;
      border-block-start-color: transparent;
      border-radius: 50%;
      animation: ds-spin 0.8s linear infinite;
    }
    @keyframes ds-spin {
      to {
        transform: rotate(360deg);
      }
    }
    /* Respect a reduced-motion preference — WCAG 2.3.3. */
    @media (prefers-reduced-motion: reduce) {
      .ds-loading__spinner {
        animation: none;
        border-block-start-color: currentcolor;
        opacity: 0.5;
      }
    }
  `,
})
export class LoadingState {
  readonly label = input<string>('Loading…');
}
