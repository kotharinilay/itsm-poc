/**
 * Lifecycle states a surface renders. Presentation vocabulary only — these are labels for something
 * the platform already decided, never an input to a decision.
 */
export type PresentationState =
  'active' | 'pending' | 'suspended' | 'expired' | 'complete' | 'failed';

export interface StateDescriptor {
  /** Text label. The primary, non-visual carrier of the state. */
  readonly label: string;
  /**
   * A shape glyph rendered alongside the label. Spec FR-SURF-013 requires suspended, pending and
   * expired to be conveyed by more than colour alone; a glyph plus a label is what satisfies it,
   * and the colour below is the third, redundant channel rather than the only one.
   */
  readonly glyph: string;
  /** CSS modifier suffix. Colour is decoration here, never the sole signal. */
  readonly tone: 'neutral' | 'info' | 'warning' | 'danger' | 'success';
}

export const STATE_DESCRIPTORS: Readonly<Record<PresentationState, StateDescriptor>> = {
  active: { label: 'Active', glyph: '●', tone: 'info' },
  pending: { label: 'Pending', glyph: '◐', tone: 'warning' },
  suspended: { label: 'Suspended', glyph: '⏸', tone: 'warning' },
  expired: { label: 'Expired', glyph: '⊘', tone: 'danger' },
  complete: { label: 'Complete', glyph: '✔', tone: 'success' },
  failed: { label: 'Failed', glyph: '✕', tone: 'danger' },
};

export function describeState(state: PresentationState): StateDescriptor {
  return STATE_DESCRIPTORS[state];
}
