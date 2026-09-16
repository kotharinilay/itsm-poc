import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { type AsyncState } from './async-state';
import { EmptyState } from './empty-state';
import { LoadingState } from './loading-state';
import { PartialFailureState } from './partial-failure-state';
import type { PresentableFailure } from './presentable-failure';

/**
 * The one place a surface maps an `AsyncState` onto what a person sees.
 *
 * Every branch of the union has a distinct rendering, which is how spec FR-SURF-016 is satisfied
 * structurally rather than by convention: there is no path from `failed` to `EmptyState`, so a
 * failure cannot be presented as an empty result even by a careless caller.
 *
 * Content is projected for the `ready` and `partial` branches; the host surface renders its own
 * data and this component stays free of any domain knowledge.
 */
@Component({
  selector: 'ds-async-state-container',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LoadingState, EmptyState, PartialFailureState],
  template: `
    @switch (state().status) {
      @case ('loading') {
        <ds-loading-state [label]="loadingLabel()" />
      }
      @case ('empty') {
        <ds-empty-state [title]="emptyTitle()" [detail]="emptyDetail()" />
      }
      @case ('failed') {
        <ds-partial-failure-state
          [failure]="failureOrFallback()"
          [partial]="false"
          (retry)="retry.emit()"
        />
      }
      @case ('partial') {
        <ds-partial-failure-state
          [failure]="failureOrFallback()"
          [partial]="true"
          (retry)="retry.emit()"
        />
      }
      @default {
        <!-- idle and ready: no state chrome. -->
      }
    }

    <!--
      One <ng-content>, deliberately. Angular projects into the first matching outlet only, so a
      second copy inside another branch would silently receive nothing. Both branches that show
      data share this one.
    -->
    @if (showsContent()) {
      <ng-content />
    }
  `,
})
export class AsyncStateContainer<T> {
  readonly state = input.required<AsyncState<T>>();

  readonly loadingLabel = input<string>('Loading…');
  readonly emptyTitle = input<string>('Nothing to show yet');
  readonly emptyDetail = input<string>('');

  readonly retry = output<void>();

  private static readonly UNKNOWN: PresentableFailure = {
    kind: 'unknown',
    title: 'Something went wrong',
    retryable: true,
  };

  /** `ready` and `partial` both render the caller's data; every other state does not. */
  protected readonly showsContent = computed(() => {
    const status = this.state().status;
    return status === 'ready' || status === 'partial';
  });

  protected readonly failureOrFallback = computed<PresentableFailure>(() => {
    const current = this.state();
    return current.status === 'failed' || current.status === 'partial'
      ? current.failure
      : AsyncStateContainer.UNKNOWN;
  });
}
