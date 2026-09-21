/**
 * The desktop session integration boundary.
 *
 * This file exists to make a *negative* fact explicit and testable: the main process takes no part
 * in the session. It holds no token, observes no sign-in, caches no identity and answers no
 * question about who the user is.
 *
 * That is not an omission to be filled in later. Sign-in is interactive against the Entra
 * authority and happens in the renderer, against the platform, over HTTPS — and every decision
 * that follows is made server-side and re-verified server-side (FE-EL-1, .claude/rules/24-electron.md). A
 * main process that held the token would be a second place to attack for a capability the host
 * does not need, on a machine inside a customer network that the platform does not control.
 *
 * So the boundary is declared here as a **descriptor** rather than an implementation. The renderer
 * can ask the host what the host's role is; it cannot ask the host who it is talking to, because
 * there is no such answer to give.
 */

import type { SessionBoundaryDescriptor } from '../ipc-contracts/index.js';

/**
 * What the host contributes to the session path.
 *
 * Every entry is transport or configuration. None is a decision.
 */
export const HOST_SESSION_RESPONSIBILITIES: readonly string[] = Object.freeze([
  'Serve the renderer bundle from the application origin',
  'Report the configured gateway, realtime and authority origins',
  'Permit navigation to the authority origin so interactive sign-in can complete',
  'Constrain the renderer with a CSP the renderer cannot weaken',
]);

/**
 * What the host must never do on the session path.
 *
 * Present as data so `tests/no-policy.spec.ts` can assert the list is non-empty and that no
 * function in this module implements any of it. A prose comment would not survive a refactor.
 */
export const HOST_SESSION_PROHIBITIONS: readonly string[] = Object.freeze([
  'Acquire, store, refresh, inspect or forward an access token',
  'Persist session or identity state in the main process',
  'Determine whether a user is signed in',
  'Determine which tenant a user belongs to',
  'Determine whether an operation is permitted',
  'Resume suspended work, or act as a link on a consequential path',
]);

/**
 * The descriptor returned over `host:describeSessionBoundary`.
 *
 * Frozen and constant. It carries no session data because there is none: `tokenCustody` is the
 * renderer, `authorityHolder` is the platform, and `'main'` is not a value either field can take.
 */
export const SESSION_BOUNDARY: SessionBoundaryDescriptor = Object.freeze({
  tokenCustody: 'renderer',
  authorityHolder: 'platform',
  mainProcessPersistsSession: false,
  hostResponsibilities: HOST_SESSION_RESPONSIBILITIES,
});

/** Describe the boundary. A pure accessor over a constant — it reads nothing and decides nothing. */
export function describeSessionBoundary(): SessionBoundaryDescriptor {
  return SESSION_BOUNDARY;
}

/**
 * Session persistence settings for the Electron session.
 *
 * `persistSession: false` is the code-level counterpart of the descriptor above: nothing about the
 * session survives the process. The cache is disabled for the same reason — a cached authenticated
 * response on a customer-managed endpoint is session state the host was not supposed to keep.
 */
export const SESSION_PARTITION = Object.freeze({
  /** An in-memory partition. Not `persist:` — that is the prefix that writes to disk. */
  partition: 'synthia-desktop',
  persistSession: false,
  cache: false,
});
