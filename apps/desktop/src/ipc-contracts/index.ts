/**
 * Typed IPC channel contracts.
 *
 * This file IS the allow-list. A channel that does not appear here cannot be invoked, and the
 * `contextBridge` surface is generated from it — so widening the bridge means editing this file,
 * which is visible in a diff (constitution Principle VII).
 *
 * Nothing here carries or implies authority. The desktop host decides nothing: every consequential
 * decision is made server-side and re-verified server-side. If a channel is ever proposed that
 * returns a permission, a role or an approval state, that is the wrong channel.
 */

/** Every channel the main process will answer. A string outside this union is rejected. */
export const IPC_CHANNELS = ['app:getVersion', 'app:getPlatform'] as const;

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
 * from an untrusted sender is still untrusted. Neither check substitutes for the other.
 */
export const ARGUMENT_VALIDATORS: Record<IpcChannel, (args: readonly unknown[]) => boolean> = {
  'app:getVersion': (args) => args.length === 0,
  'app:getPlatform': (args) => args.length === 0,
};

/** Validate the arguments for a channel. Unknown channels fail closed. */
export function areArgumentsValid(channel: IpcChannel, args: readonly unknown[]): boolean {
  const validator = ARGUMENT_VALIDATORS[channel];
  return validator === undefined ? false : validator(args);
}

/** Response shapes, so the renderer is typed against a contract rather than against `any`. */
export interface AppVersion {
  readonly version: string;
}

export interface AppPlatform {
  readonly platform: NodeJS.Platform;
}
