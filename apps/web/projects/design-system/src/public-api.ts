/*
 * Public API Surface of design-system.
 *
 * The dependency floor: accessible primitives and shared state vocabulary, no business logic and no
 * dependency on any other workspace project (plan §Dependency direction, enforced by ESLint).
 */

// Accessibility foundation
export * from './lib/a11y/focusable';
export * from './lib/a11y/focus-trap';
export * from './lib/a11y/live-announcer';
export * from './lib/a11y/skip-link';

// State conveyed by more than colour (FR-SURF-013)
export * from './lib/status/presentation-state';
export * from './lib/status/status-indicator';

// Loading / empty / partial-failure infrastructure (FR-SURF-016)
export * from './lib/states/async-state';
export * from './lib/states/async-state-container';
export * from './lib/states/empty-state';
export * from './lib/states/loading-state';
export * from './lib/states/partial-failure-state';
export * from './lib/states/presentable-failure';
