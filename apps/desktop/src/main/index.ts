/**
 * Electron main process — the composition root for the desktop host
 * (plan §Composition roots).
 *
 * The host is thin and **decides nothing**. It renders the desktop renderer, applies the
 * security controls in `security.ts`, and answers exactly the IPC channels declared in
 * `ipc-contracts`. No business authorization decision exists here or in the renderer
 * (constitution Principle VII).
 *
 * Script execution is NOT implemented. The catalogue holds only inert reference fixtures, and
 * ADR-0004's open items (script signing, the destructive taxonomy) block the endpoint path from
 * carrying anything further. See specs/001-platform-scaffold/tasks.md §Deferred.
 */

import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { app, BrowserWindow, ipcMain, session, shell } from 'electron';

import { guardInvocation } from './ipc-guard.js';
import {
  buildContentSecurityPolicy,
  isNavigationAllowed,
  SECURE_WEB_PREFERENCES,
} from './security.js';

const here = path.dirname(fileURLToPath(import.meta.url));

/** Origins whose IPC messages the main process will answer. The app's own origin, and nothing else. */
const TRUSTED_IPC_ORIGINS: readonly string[] = ['file://'];

function registerIpcHandlers(): void {
  ipcMain.handle('app:getVersion', (event, ...args: unknown[]) => {
    const decision = guardInvocation(
      { url: event.senderFrame?.url ?? '' },
      TRUSTED_IPC_ORIGINS,
      'app:getVersion',
      args,
    );
    if (!decision.ok) {
      throw new Error(`IPC refused: ${decision.reason}`);
    }
    return { version: app.getVersion() };
  });

  ipcMain.handle('app:getPlatform', (event, ...args: unknown[]) => {
    const decision = guardInvocation(
      { url: event.senderFrame?.url ?? '' },
      TRUSTED_IPC_ORIGINS,
      'app:getPlatform',
      args,
    );
    if (!decision.ok) {
      throw new Error(`IPC refused: ${decision.reason}`);
    }
    return { platform: process.platform };
  });
}

function applyContentSecurityPolicy(): void {
  // Applied from the main process so the renderer cannot weaken it (plan Stage 4).
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [buildContentSecurityPolicy()],
      },
    });
  });
}

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    show: false,
    webPreferences: {
      ...SECURE_WEB_PREFERENCES,
      preload: path.join(here, '..', 'preload', 'bridge.js'),
    },
  });

  // Navigation is denied by default and permitted only for the allow-listed origins.
  window.webContents.on('will-navigate', (event, url) => {
    if (!isNavigationAllowed(url)) {
      event.preventDefault();
    }
  });

  // Every destination is denied without exception. An external link goes to the OS handler only
  // after the same allow-list check, so nothing reaches it that could not have been navigated to.
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (isNavigationAllowed(url)) {
      void shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  window.once('ready-to-show', () => window.show());
  return window;
}

void app.whenReady().then(() => {
  applyContentSecurityPolicy();
  registerIpcHandlers();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
