/*
 * Public API Surface of staff-features.
 *
 * Staff-facing feature shells. Must not import customer-features or any application
 * (plan §Dependency direction, enforced by ESLint).
 */

export * from './lib/queue/queue-shell';
export * from './lib/reporting/reporting-shell';
export * from './lib/staff-features.routes';
export * from './lib/take-over/take-over-shell';
