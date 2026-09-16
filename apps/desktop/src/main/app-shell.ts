/**
 * The application shell — process-wide hardening and the IPC handler table.
 *
 * Split from `index.ts` so that everything except the Electron wiring is testable. The functions
 * here take their Electron collaborators as parameters rather than importing them, which is what
 * lets `tests/` exercise the shell's decisions in plain Node with no display.
 *
 * The shell **decides nothing about business operations**. It decides which window to open, which
 * headers to attach and which messages are well formed. Every question about what a user may do is
 * the platform's, answered server-side and re-verified server-side (constitution Principle VII).
 */

import {
  BRIDGE_SURFACE,
  IPC_CHANNELS,
  type HostEndpoints,
  type HostPlatform,
  type HostVersion,
  type IpcChannel,
  type SessionBoundaryDescriptor,
} from '../ipc-contracts/index.js';
import type { HostConfig } from './config.js';
import { guarded, type SenderLike } from './ipc-guard.js';
import { describeSessionBoundary } from './session-boundary.js';

/** Facts about the running process the host is willing to report. */
export interface HostFacts {
  readonly version: string;
  readonly platform: string;
}

/** A registered handler: already wrapped by the guard, so it cannot be invoked unvalidated. */
export type GuardedHandler = (sender: SenderLike, args: readonly unknown[]) => unknown;

/**
 * Build the complete handler table.
 *
 * Every entry goes through `guarded`, and the table's keys are asserted against `IPC_CHANNELS` —
 * so a channel declared in the contract with no handler, or a handler for a channel not in the
 * contract, is a test failure rather than a runtime surprise.
 *
 * Each handler returns a fact or a shape. None consults a role, a tenant or an approval state,
 * because none has access to one.
 */
export function buildHandlers(
  facts: HostFacts,
  config: HostConfig,
): Readonly<Record<IpcChannel, GuardedHandler>> {
  const handlers: Record<IpcChannel, GuardedHandler> = {
    'host:getVersion': guarded(
      'host:getVersion',
      (): HostVersion => ({ version: facts.version }),
    ),
    'host:getPlatform': guarded(
      'host:getPlatform',
      (): HostPlatform => ({ platform: facts.platform }),
    ),
    'host:getEndpoints': guarded(
      'host:getEndpoints',
      (): HostEndpoints => ({
        gatewayOrigin: config.gatewayOrigin,
        realtimeOrigin: config.realtimeOrigin,
        authorityOrigin: config.authorityOrigin,
      }),
    ),
    'host:describeSessionBoundary': guarded(
      'host:describeSessionBoundary',
      (): SessionBoundaryDescriptor => describeSessionBoundary(),
    ),
  };
  return Object.freeze(handlers);
}

/** The channel set the handler table covers. Used by the suite to prove the two agree. */
export function handledChannels(
  handlers: Readonly<Record<string, GuardedHandler>>,
): readonly string[] {
  return Object.keys(handlers).sort();
}

/** The channel set the contract declares. */
export function contractChannels(): readonly string[] {
  return [...IPC_CHANNELS].sort();
}

/** The bridge members the contract declares. */
export function contractBridgeMembers(): readonly string[] {
  return Object.keys(BRIDGE_SURFACE).sort();
}

// ---------------------------------------------------------------------------------------------
// Process-wide hardening
// ---------------------------------------------------------------------------------------------

/**
 * Permissions the renderer may be granted.
 *
 * Empty. The desktop scaffold needs no camera, microphone, geolocation, notification, clipboard or
 * MIDI access, and a permission granted "for later" is a permission available now. Adding one is a
 * deliberate edit here, visible in a diff, and `tests/security.spec.ts` asserts the list is empty.
 */
export const GRANTED_PERMISSIONS: readonly string[] = Object.freeze([]);

/**
 * Decide a permission request.
 *
 * Denies everything not on `GRANTED_PERMISSIONS` — which, today, is everything.
 */
export function decidePermission(permission: string): boolean {
  return GRANTED_PERMISSIONS.includes(permission);
}

/**
 * Whether a TLS certificate error is ever trusted.
 *
 * A named constant rather than a bare `return false`, for the same reason the `webPreferences`
 * switches are exported as data: it gives the control a single assertable value, and it gives
 * `verify-desktop-security-guard.sh` something to flip when proving the suite catches it.
 */
export const TRUST_CERTIFICATE_ERRORS = false;

/**
 * Decide what to do with a TLS certificate error.
 *
 * Always refuse. There is no development escape hatch and no environment variable that opens one:
 * an endpoint sits inside a customer network, which is exactly where a transparent proxy presenting
 * its own certificate lives. Accepting one "only in development" means shipping the branch that
 * accepts one.
 */
export function shouldTrustCertificateError(): boolean {
  return TRUST_CERTIFICATE_ERRORS;
}

/**
 * Command-line switches that must never be present.
 *
 * Each of these disables a control asserted elsewhere in this scaffold, and each can be supplied
 * by whoever launches the process — which, on a customer-managed endpoint, is not necessarily us.
 * The shell refuses to start rather than running with one.
 */
export const FORBIDDEN_SWITCHES: readonly string[] = Object.freeze([
  'disable-web-security',
  'ignore-certificate-errors',
  'allow-running-insecure-content',
  'remote-debugging-port',
  'remote-debugging-pipe',
  'inspect',
  'inspect-brk',
  'js-flags',
  'disable-site-isolation-trials',
  'host-rules',
  'auth-server-whitelist',
  'no-sandbox',
]);

export class ForbiddenSwitchError extends Error {
  public override readonly name = 'ForbiddenSwitchError';
  public constructor(public readonly switches: readonly string[]) {
    super(`Refusing to start: forbidden command-line switch(es): ${switches.join(', ')}`);
  }
}

/**
 * Find forbidden switches in an argv list.
 *
 * Matches `--switch`, `--switch=value` and `--switch value`, and is case-insensitive, because all
 * four forms reach Chromium identically.
 */
export function findForbiddenSwitches(argv: readonly string[]): readonly string[] {
  const found = new Set<string>();
  for (const raw of argv) {
    if (!raw.startsWith('--')) {
      continue;
    }
    const name = raw.slice(2).split('=', 1)[0]?.toLowerCase() ?? '';
    if (FORBIDDEN_SWITCHES.includes(name)) {
      found.add(name);
    }
  }
  return [...found].sort();
}

/** Throw if the process was launched with any forbidden switch. */
export function assertNoForbiddenSwitches(argv: readonly string[]): void {
  const found = findForbiddenSwitches(argv);
  if (found.length > 0) {
    throw new ForbiddenSwitchError(found);
  }
}
