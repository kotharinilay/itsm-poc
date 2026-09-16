import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { type PresentationState, describeState } from './presentation-state';

/**
 * Renders a lifecycle state as glyph + text + colour.
 *
 * Spec FR-SURF-013: a suspended, pending or expired state MUST be conveyed by more than colour
 * alone. Centralising it here is what stops the eleventh surface from shipping a bare coloured dot.
 */
@Component({
  selector: 'ds-status-indicator',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './status-indicator.html',
  styleUrl: './status-indicator.css',
})
export class StatusIndicator {
  readonly state = input.required<PresentationState>();
  /** Optional context, e.g. "awaiting your approval". Appended to the accessible name. */
  readonly qualifier = input<string>('');

  protected readonly descriptor = computed(() => describeState(this.state()));

  protected readonly accessibleName = computed(() => {
    const qualifier = this.qualifier().trim();
    const label = this.descriptor().label;
    return qualifier.length === 0 ? label : `${label} — ${qualifier}`;
  });
}
