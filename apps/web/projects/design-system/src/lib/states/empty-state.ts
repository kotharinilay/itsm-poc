import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * "There is genuinely nothing here."
 *
 * Spec FR-SURF-016 forbids presenting a failure as an empty result, so this component is reachable
 * only from the `empty` member of `AsyncState` — never from `failed`. `PartialFailureState` is the
 * component for the other case.
 */
@Component({
  selector: 'ds-empty-state',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="ds-empty" role="status">
      <p class="ds-empty__title">{{ title() }}</p>
      @if (detail().length > 0) {
        <p class="ds-empty__detail">{{ detail() }}</p>
      }
      <ng-content />
    </div>
  `,
  styles: `
    .ds-empty {
      padding: 2rem 1rem;
      text-align: center;
    }
    .ds-empty__title {
      font-weight: 600;
      margin: 0;
    }
    .ds-empty__detail {
      margin: 0.5rem 0 0;
    }
  `,
})
export class EmptyState {
  readonly title = input<string>('Nothing to show yet');
  readonly detail = input<string>('');
}
