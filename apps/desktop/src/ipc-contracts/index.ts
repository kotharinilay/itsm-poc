/**
 * Typed IPC channel contracts (T029, T051).
 *
 * This file IS the allow-list. A channel that does not appear here cannot be invoked, and the
 * `contextBridge` surface is derived from it — so widening the bridge means editing this file,
 * which is visible in a diff (constitution Principle VII).
 *
 * Nothing here carries or implies authority. The desktop host decides nothing: every consequential
 * decision is made server-side and re-verified server-side. If a channel is ever proposed that
 * returns a permission, a role, a tenant or an approval state, that is the wrong channel — and
 * `tests/no-policy.spec.ts` fails when one appears.
 */

/**
 * Every channel the main process will answer. A string outside this union is rejected before a
 * handler is consulted.
 *
 * Read the list as a statement of what the host is for: it reports facts about itself and the
 * configuration it was started with. It answers no question whose answer is a decision.
 */
export const IPC_CHANNELS = [
  /** The running application version. Informational. */
  'host:getVersion',
  /** The host platform identifier. Informational. */
  'host:getPlatform',
  /** The origins this host was configured with, so the renderer addresses the same gateway. */
  'host:getEndpoints',
  /**
   * A description of the desktop session integration boundary — where session state lives and who
   * decides. It returns a *shape*, never a session, a token or a verdict.
   */
  'host:describeSessionBoundary',
] as const;

export type IpcChannel = (typeof IPC_CHANNELS)[number];

/** Narrow a caller-supplied value to a known channel. */
export function isIpcChannel(value: unknown): value is IpcChannel {
  return typeof value === 'string' && (IPC_CHANNELS as readonly string[]).includes(value);
}

/**
 * Argument validators, one per channel.
 *
 * Sender validation and argument validation are **two distinct obligations** (constitution
 * Principle VII). A trusted sender may still send a malformed payload, and a well-formed payload
 * from an untrusted sender is still untrusted. Neither check substitutes for the other, which is
 * why they live in separate functions with separate tests.
 *
 * Every channel currently takes no arguments, so every validator rejects a non-empty list. That is
 * a real check, not a placeholder: an argument arriving on a channel that takes none is evidence
 * the caller is not the renderer we shipped.
 */
export const ARGUMENT_VALIDATORS: Record<IpcChannel, (args: readonly unknown[]) => boolean> = {
  'host:getVersion': (args) => args.length === 0,
  'host:getPlatform': (args) => args.length === 0,
  'host:getEndpoints': (args) => args.length === 0,
  'host:describeSessionBoundary': (args) => args.length === 0,
};

/** Validate the arguments for a channel. An unknown channel fails closed. */
export function areArgumentsValid(channel: IpcChannel, args: readonly unknown[]): boolean {
  const validator = ARGUMENT_VALIDATORS[channel];
  return validator === undefined ? false : validator(args);
}

/**
 * The exact member names the preload exposes on `window.synthiaDesktop`, and the channel each one
 * reaches.
 *
 * Keeping the mapping here — rather than letting the preload invent its own names — is what makes
 * "the bridge is narrow" a testable claim instead of an assertion. `tests/bridge-surface.spec.ts`
 * asserts the preload exposes exactly these members and no others.
 */
export const BRIDGE_SURFACE = {
  getVersion: 'host:getVersion',
  getPlatform: 'host:getPlatform',
  getEndpoints: 'host:getEndpoints',
  describeSessionBoundary: 'host:describeSessionBoundary',
} as const satisfies Record<string, IpcChannel>;

export type BridgeMember = keyof typeof BRIDGE_SURFACE;

/** The global key the bridge is exposed under. One key, one object, nothing else. */
export const BRIDGE_GLOBAL_KEY = 'synthiaDesktop';

// ---------------------------------------------------------------------------------------------
// Response shapes — so the renderer is typed against a contract rather than against `any`.
// ---------------------------------------------------------------------------------------------

export interface HostVersion {
  readonly version: string;
}

export interface HostPlatform {
  readonly platform: string;
}

/**
 * The origins the host was configured with.
 *
 * This is configuration, not authority. It tells the renderer *where* to address the platform
 * (spec FR-SURF-017 — a single gateway); it says nothing about what the renderer may ask for once
 * it gets there.
 */
export interface HostEndpoints {
  /** The single platform origin. HTTPS. */
  readonly gatewayOrigin: string;
  /** The realtime origin. WSS — notification and results only. */
  readonly realtimeOrigin: string;
  /** The Entra authority used for interactive sign-in. HTTPS. */
  readonly authorityOrigin: string;
}

/** Who holds a given responsibility on the desktop session path. */
export type SessionCustodian = 'renderer' | 'platform' | 'nobody';

/**
 * A description of the desktop session integration boundary.
 *
 * Deliberately a description rather than a session. The main process holds no tokens, observes no
 * sign-in and answers no question about who the user is — and this payload is how that fact is
 * made legible to the renderer and assertable by a test.
 */
export interface SessionBoundaryDescriptor {
  /** Where the credential lives. Never `'main'` — the main process is not an option. */
  readonly tokenCustody: SessionCustodian;
  /** Who decides whether an operation is permitted. Always the platform. */
  readonly authorityHolder: SessionCustodian;
  /** Whether the main process persists any session state. Always `false`. */
  readonly mainProcessPersistsSession: boolean;
  /** What the host contributes to the session path, in order. Descriptive only. */
  readonly hostResponsibilities: readonly string[];
}
