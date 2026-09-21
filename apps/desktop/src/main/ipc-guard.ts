/**
 * T052 — IPC sender validation and argument validation, as two distinct checks.
 *
 * FE-EL-5 (.claude/rules/24-electron.md) requires both: every IPC sender and every IPC
 * argument is validated.
 * They catch different things. Sender validation stops a frame we did not ship from reaching the
 * main process at all; argument validation stops a frame we *did* ship from sending a payload the
 * handler was not written for. Neither substitutes for the other, which is why they are separate
 * exported functions with separate tests.
 *
 * NOTE: everything here decides whether a **message is well formed**, never whether an
 * **operation is permitted**. No business authorization decision exists in the main process or the
 * renderer (FE-EL-1, .claude/rules/24-electron.md). If a future change makes any function in this file
 * consult a role, a tenant or an approval state, that change is a defect and
 * `tests/no-policy.spec.ts` is where it should be caught.
 */

import { areArgumentsValid, isIpcChannel, type IpcChannel } from '../ipc-contracts/index.js';
import { originOf, RENDERER_ORIGIN } from './config.js';

/**
 * The minimum shape of an IPC sender this guard needs, so tests need no real Electron frame.
 *
 * Both fields are optional because Electron's are: `senderFrame` is `null` once the frame has been
 * torn down, and a message can arrive in that window. An absent field fails closed.
 */
export interface SenderLike {
  /** The URL the sending frame was loaded from. */
  readonly url?: string | undefined;
  /** Whether the sending frame is the window's top-level frame. */
  readonly isMainFrame?: boolean | undefined;
}

/** Why a message was refused. Returned rather than thrown, so the caller decides how to report. */
export type IpcRejectionReason =
  | 'untrusted-sender'
  | 'subframe-sender'
  | 'unknown-channel'
  | 'invalid-arguments';

export type IpcDecision =
  | { readonly ok: true; readonly channel: IpcChannel }
  | { readonly ok: false; readonly reason: IpcRejectionReason };

/** The only origin the main process answers: the renderer bundle the app itself serves. */
export const TRUSTED_IPC_ORIGINS: readonly string[] = Object.freeze([RENDERER_ORIGIN]);

/**
 * Check 1 — is the sender one we will answer at all?
 *
 * Fails closed on a missing or unparseable URL, on an opaque origin, and on a subframe. The
 * subframe rule matters: `nodeIntegrationInSubFrames` is off, but an embedded frame that somehow
 * loaded our origin should still not be able to drive the host, and only the top-level frame is
 * ever the app.
 */
export function isSenderTrusted(
  sender: SenderLike,
  trustedOrigins: readonly string[] = TRUSTED_IPC_ORIGINS,
): boolean {
  if (sender.isMainFrame === false) {
    return false;
  }
  if (typeof sender.url !== 'string' || sender.url === '') {
    return false;
  }
  let url: URL;
  try {
    url = new URL(sender.url);
  } catch {
    return false;
  }
  const origin = originOf(url);
  if (origin === 'null') {
    return false;
  }
  return trustedOrigins.includes(origin);
}

/**
 * Check 2 — is this a known channel carrying arguments its handler accepts?
 *
 * Run only after {@link isSenderTrusted}. Both must pass, in that order: an untrusted sender is
 * refused before its payload is even looked at.
 */
export function validateInvocation(channel: unknown, args: readonly unknown[]): IpcDecision {
  if (!isIpcChannel(channel)) {
    return { ok: false, reason: 'unknown-channel' };
  }
  if (!areArgumentsValid(channel, args)) {
    return { ok: false, reason: 'invalid-arguments' };
  }
  return { ok: true, channel };
}

/** Both checks, in order, for a caller that wants one call. */
export function guardInvocation(
  sender: SenderLike,
  channel: unknown,
  args: readonly unknown[],
  trustedOrigins: readonly string[] = TRUSTED_IPC_ORIGINS,
): IpcDecision {
  if (!isSenderTrusted(sender, trustedOrigins)) {
    return { ok: false, reason: sender.isMainFrame === false ? 'subframe-sender' : 'untrusted-sender' };
  }
  return validateInvocation(channel, args);
}

/** Thrown back across the IPC boundary when a message is refused. */
export class IpcRefusedError extends Error {
  public override readonly name = 'IpcRefusedError';
  public constructor(
    public readonly channel: string,
    public readonly reason: IpcRejectionReason,
  ) {
    // The renderer learns that its message was refused and why it was malformed. It learns nothing
    // about the host's configuration, because there is nothing here worth leaking.
    super(`IPC refused on ${channel}: ${reason}`);
  }
}

/**
 * Wrap a handler so it runs only for a message that passed both checks.
 *
 * Every registered handler goes through this. Making it the only registration path is what stops
 * the next channel from being added with the guard forgotten — there is no way to register one
 * without it.
 */
export function guarded<T>(
  channel: IpcChannel,
  handle: () => T,
): (sender: SenderLike, args: readonly unknown[]) => T {
  return (sender, args) => {
    const decision = guardInvocation(sender, channel, args);
    if (!decision.ok) {
      throw new IpcRefusedError(channel, decision.reason);
    }
    return handle();
  };
}
