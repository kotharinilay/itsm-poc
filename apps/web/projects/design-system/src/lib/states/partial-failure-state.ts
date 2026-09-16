import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import type { PresentableFailure } from './presentable-failure';

/**
 * Renders a failure — total or partial — as a failure.
 *
 * Spec FR-SURF-016: a failure MUST NOT be presented as an empty result. `partial` is the case this
 * component is named for: some data arrived and something else did not, and the person is told so
 * rather than being shown a quietly incomplete list.
 *
 * It emits a retry intent. It does not retry, and it decides nothing.
 */
@Component({
  selector: 'ds-partial-failure-state',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="ds-failure" [class.ds-failure--partial]="partial()" role="alert">
      <p class="ds-failure__title">
        <span class="ds-failure__glyph" aria-hidden="true">⚠</span>
        {{ partial() ? 'Some information could not be loaded' : failure().title }}
      </p>

      @if (partial()) {
        <p class="ds-failure__detail">{{ failure().title }}</p>
      } @else if (failure().detail) {
        <p class="ds-failure__detail">{{ failure().detail }}</p>
      }

      @if (failure().retryable) {
        <button type="button" class="ds-failure__retry" (click)="retry.emit()">Try again</button>
      }

      @if (failure().correlationId; as correlationId) {
        <p class="ds-failure__correlation">
          Reference: <code>{{ correlationId }}</code>
        </p>
      }
    </div>
  `,
  styles: `
    .ds-failure {
      padding: 1rem;
      border: 2px solid currentcolor;
      border-radius: 0.25rem;
    }
    .ds-failure__title {
      margin: 0;
      font-weight: 600;
    }
    .ds-failure__detail {
      margin: 0.5rem 0 0;
    }
    .ds-failure__retry {
      margin-block-start: 0.75rem;
    }
    .ds-failure__correlation {
      margin: 0.75rem 0 0;
      font-size: 0.875rem;
    }
  `,
})
export class PartialFailureState {
  readonly failure = input.required<PresentableFailure>();
  /** True when some data did arrive, so the message says "some" rather than "none". */
  readonly partial = input<boolean>(false);

  readonly retry = output<void>();
}
