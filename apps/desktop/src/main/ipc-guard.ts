/**
 * IPC guard — sender validation and argument validation as two distinct checks.
 *
 * The constitution requires both: "Every IPC sender and every IPC argument MUST be validated."
 * They catch different attacks. Sender validation stops a compromised or injected frame from
 * reaching the main process at all; argument validation stops a legitimate frame from sending a
 * payload the handler was not written for. Neither substitutes for the other, which is why they
 * are separate exported functions with separate tests.
 */

import { areArgumentsValid, isIpcChannel, type IpcChannel } from '../ipc-contracts/index.js';

/** The minimum shape of an IPC sender this guard needs, so tests need no real Electron frame. */
export interface SenderLike {
  /** The URL the sending frame was loaded from. */
  readonly url: string;
}

/** Why a message was refused. Returned rather than thrown so the caller decides how to report. */
export type IpcRejection =
  | { readonly ok: false; readonly reason: 'untrusted-sender' }
  | { readonly ok: false; readonly reason: 'unknown-channel' }
  | { readonly ok: false; readonly reason: 'invalid-arguments' };

export type IpcDecision = { readonly ok: true; readonly channel: IpcChannel } | IpcRejection;

/**
 * Check 1 — is the sender one we will answer at all?
 *
 * Fails closed on an unparseable URL. The renderer bundle is loaded from the app itself, so the
 * only trusted sender is the application's own origin.
 */
export function isSenderTrusted(sender: SenderLike, trustedOrigins: readonly string[]): boolean {
  let url: URL;
  try {
    url = new URL(sender.url);
  } catch {
    return false;
  }
  return trustedOrigins.includes(url.origin);
}

/**
 * Check 2 — is this a known channel carrying arguments its handler accepts?
 *
 * Run only after {@link isSenderTrusted}. Both must pass.
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

/**
 * Both checks, in order, for a caller that wants one call.
 *
 * NOTE: this decides whether a *message is well formed*, never whether an *operation is
 * permitted*. No business authorization decision exists in the main process or the renderer
 * (constitution Principle VII). If a future change makes this function consult a role, a tenant
 * or an approval state, that change is a defect.
 */
export function guardInvocation(
  sender: SenderLike,
  trustedOrigins: readonly string[],
  channel: unknown,
  args: readonly unknown[],
): IpcDecision {
  if (!isSenderTrusted(sender, trustedOrigins)) {
    return { ok: false, reason: 'untrusted-sender' };
  }
  return validateInvocation(channel, args);
}
