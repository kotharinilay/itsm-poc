/*
 * Public API Surface of platform-core.
 *
 * Shared client infrastructure: typed API contracts and clients, authentication, correlation,
 * realtime and browser security. May depend on design-system and nothing else in the workspace
 * (plan §Dependency direction, enforced by ESLint).
 */

// Typed contracts
export * from './lib/contracts/customer-contracts';
export * from './lib/contracts/paging';
export * from './lib/contracts/primitives';
export * from './lib/contracts/problem-details';
export * from './lib/contracts/staff-contracts';

// Centralized API infrastructure
export * from './lib/api/correlation';
export * from './lib/api/customer-api.client';
export * from './lib/api/message-stream.client';
export * from './lib/api/platform-api-error';
export * from './lib/api/platform-api.client';
export * from './lib/api/platform-api.config';
export * from './lib/api/platform.interceptors';
export * from './lib/api/staff-api.client';

// Centralized authentication integration
export * from './lib/auth/access-token-provider';
export * from './lib/auth/auth-session';
export * from './lib/auth/auth.service';
export * from './lib/auth/role-visibility';

// Centralized realtime / SignalR integration
export * from './lib/realtime/notification-envelope';
export * from './lib/realtime/realtime-connection';
export * from './lib/realtime/realtime.service';

// Browser security
export * from './lib/security/content-security-policy';
export * from './lib/security/sanitization-policy';

// Composition
export * from './lib/platform-core.providers';
