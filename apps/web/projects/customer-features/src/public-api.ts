/*
 * Public API Surface of customer-features.
 *
 * Customer-facing feature shells, shared by the customer portal and the desktop renderer. Must not
 * import staff-features or any application (plan §Dependency direction, enforced by ESLint).
 */

export * from './lib/chat/chat-shell';
export * from './lib/chat/feedback/feedback-control';
export * from './lib/consent/consent-shell';
export * from './lib/customer-features.routes';
export * from './lib/handoff/handoff-shell';
export * from './lib/session/session-shell';
