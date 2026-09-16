/**
 * T051 — the preload, and the narrow `contextBridge` surface.
 *
 * This is the **only** thing the renderer can reach. Raw `ipcRenderer` is never exposed, and no
 * broad Electron or Node API appears on the bridge (constitution Principle VII). `ipcRenderer` is
 * imported here and captured in a closure; nothing that leaves this module can reach it.
 *
 * The surface is derived from `BRIDGE_SURFACE` in `ipc-contracts`, so widening it means editing
 * the contract — which shows up in a diff, and which `tests/bridge-surface.spec.ts` asserts
 * against. A bridge that can grow quietly is a bridge that will.
 *
 * Nothing exposed here carries authority. The renderer cannot ask this bridge whether an operation
 * is permitted, because the bridge does not know and must never be taught.
 */

import { contextBridge, ipcRenderer } from 'electron';

import {
  BRIDGE_GLOBAL_KEY,
  BRIDGE_SURFACE,
  type HostEndpoints,
  type HostPlatform,
  type HostVersion,
  type SessionBoundaryDescriptor,
} from '../ipc-contracts/index.js';

/**
 * Invoke a contract channel.
 *
 * Takes an `IpcChannel`, never a caller-supplied string, so there is no path by which the renderer
 * can name its own channel. This function is not exposed — only the closures below are.
 */
function invoke<T>(channel: (typeof BRIDGE_SURFACE)[keyof typeof BRIDGE_SURFACE]): Promise<T> {
  return ipcRenderer.invoke(channel) as Promise<T>;
}

/**
 * The exposed API.
 *
 * Every member is a zero-argument reader. There is no `send`, no `on`, no channel parameter and no
 * way to pass a value through to the main process — which is why the argument validators in the
 * contract reject every non-empty argument list: under normal operation, nothing can produce one.
 */
const api = {
  /** The running application version. Informational. */
  getVersion: (): Promise<HostVersion> => invoke<HostVersion>(BRIDGE_SURFACE.getVersion),
  /** The host platform identifier. Informational. */
  getPlatform: (): Promise<HostPlatform> => invoke<HostPlatform>(BRIDGE_SURFACE.getPlatform),
  /** The origins this host was configured with, so the renderer addresses the same gateway. */
  getEndpoints: (): Promise<HostEndpoints> => invoke<HostEndpoints>(BRIDGE_SURFACE.getEndpoints),
  /** A description of the session boundary — a shape, never a session, a token or a verdict. */
  describeSessionBoundary: (): Promise<SessionBoundaryDescriptor> =>
    invoke<SessionBoundaryDescriptor>(BRIDGE_SURFACE.describeSessionBoundary),
} as const;

/** The renderer types itself against this. Exported as a type only — no value crosses. */
export type SynthiaDesktopApi = typeof api;

contextBridge.exposeInMainWorld(BRIDGE_GLOBAL_KEY, api);
