/**
 * Preload — the narrow `contextBridge` surface, and the only thing the renderer can reach.
 *
 * Raw `ipcRenderer` is NEVER exposed, and no broad Electron or Node API appears here
 * (constitution Principle VII). The surface is generated from the channel allow-list in
 * `ipc-contracts`, so widening it means editing that file and showing up in a diff.
 *
 * Nothing exposed here carries authority. The renderer cannot ask this bridge whether an
 * operation is permitted, because the bridge does not know and must never be taught.
 */

import { contextBridge, ipcRenderer } from 'electron';

import type { AppPlatform, AppVersion } from '../ipc-contracts/index.js';

const api = {
  /** The running application version. Informational only. */
  getVersion: (): Promise<AppVersion> => ipcRenderer.invoke('app:getVersion') as Promise<AppVersion>,
  /** The host platform. Informational only. */
  getPlatform: (): Promise<AppPlatform> =>
    ipcRenderer.invoke('app:getPlatform') as Promise<AppPlatform>,
} as const;

export type SynthiaDesktopApi = typeof api;

contextBridge.exposeInMainWorld('synthiaDesktop', api);
