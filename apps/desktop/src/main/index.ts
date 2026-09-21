/**
 * Electron main process — the composition root for the desktop host (plan §Composition roots).
 *
 * This file does Electron wiring and nothing else. Every decision it applies is defined and tested
 * in a sibling module: `window.ts` (switches), `navigation.ts` (allow-list), `csp.ts` (policy),
 * `ipc-guard.ts` (sender and argument validation), `app-shell.ts` (handler table and process
 * hardening), `renderer-protocol.ts` (serving the bundle). Keeping the wiring separate from the
 * rules is what lets the rules be proven in CI on a machine with no display.
 *
 * The host is thin and **decides nothing**. No business authorization decision exists here or in
 * the renderer (FE-EL-1, .claude/rules/24-electron.md).
 *
 * Script execution is NOT implemented — see `endpoint-execution-boundary.ts`, which refuses
 * unconditionally and is reachable from no IPC channel.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { app, BrowserWindow, ipcMain, net, protocol, session, shell } from 'electron';
import type { Session } from 'electron';

import { assertNoForbiddenSwitches, buildHandlers, decidePermission, shouldTrustCertificateError } from './app-shell.js';
import { loadHostConfig, RENDERER_SCHEME } from './config.js';
import { applyContentSecurityPolicy, buildContentSecurityPolicy, CSP_HEADER } from './csp.js';
import { applyNavigationPolicy, isExternalOpenAllowed } from './navigation.js';
import {
  chooseRendererResponse,
  createNonce,
  injectNonce,
  RENDERER_ENTRY_URL,
  RENDERER_SCHEME_PRIVILEGES,
} from './renderer-protocol.js';
import { SESSION_PARTITION } from './session-boundary.js';
import { createMainWindow } from './window.js';

const here = path.dirname(fileURLToPath(import.meta.url));

/** The built Angular bundle, copied into the desktop package at build time. */
const BUNDLE_ROOT = path.resolve(here, '..', 'renderer');
const PRELOAD_PATH = path.join(here, '..', 'preload', 'bridge.js');

// Refuse to start under a switch that would disable a control asserted elsewhere. Done before any
// Electron API call, so there is no window in which the process runs weakened.
assertNoForbiddenSwitches(process.argv);

const config = loadHostConfig();

// The scheme must be registered before `app.whenReady()`, or it is not standard or secure.
protocol.registerSchemesAsPrivileged([RENDERER_SCHEME_PRIVILEGES]);

// Sandbox every renderer at the process level, not only per-window. A window created without our
// `webPreferences` still lands in a sandbox.
app.enableSandbox();

/** One instance. A second launch focuses the existing window rather than opening a second host. */
if (!app.requestSingleInstanceLock()) {
  app.quit();
}

/**
 * The one session every window uses.
 *
 * Created once and memoised, because the protocol handler, the CSP interceptor and the permission
 * handlers must all be registered on the **same** session the window renders in. Registering on
 * `session.defaultSession` while the window runs in a partition means the window gets none of
 * them — and the failure mode is a blank window, not an error.
 */
let hostSession: Session | undefined;

function getHostSession(): Session {
  hostSession ??= session.fromPartition(SESSION_PARTITION.partition, {
    cache: SESSION_PARTITION.cache,
  });
  return hostSession;
}

function registerRendererProtocol(target: Session): void {
  target.protocol.handle(RENDERER_SCHEME.replace(':', ''), async (request) => {
    try {
      const { filePath, isEntryDocument } = chooseRendererResponse(
        BUNDLE_ROOT,
        request.url,
        (candidate) => fs.existsSync(candidate),
      );

      // The entry document is rewritten with a fresh nonce and served with the policy that names
      // it. Both happen here, on one path, so the document can never be served without the header
      // or with a header naming a different nonce.
      if (isEntryDocument) {
        const nonce = createNonce();
        const html = injectNonce(await fs.promises.readFile(filePath, 'utf8'), nonce);
        return new Response(html, {
          status: 200,
          headers: {
            'content-type': 'text/html; charset=utf-8',
            [CSP_HEADER]: buildContentSecurityPolicy(config, nonce),
          },
        });
      }

      // `pathToFileURL` rather than string concatenation: it encodes a drive letter, a UNC path
      // and any character that would otherwise need escaping. Concatenation gets Windows wrong.
      return await net.fetch(pathToFileURL(filePath).toString());
    } catch {
      // A refused path is a 404, not a detailed error. The renderer has no use for the reason and
      // an attacker probing traversal should learn nothing from the difference.
      return new Response('Not found', { status: 404, headers: { 'content-type': 'text/plain' } });
    }
  });
}

function registerIpcHandlers(): void {
  const handlers = buildHandlers(
    { version: app.getVersion(), platform: process.platform },
    config,
  );

  // Only the channels in the contract are registered at all, so an unregistered channel is
  // rejected by Electron before any code here runs — and a registered one still has to pass both
  // guard checks inside `handle`.
  for (const [channel, handle] of Object.entries(handlers)) {
    ipcMain.handle(channel, (event, ...args: unknown[]) => {
      const frame = event.senderFrame;
      return handle(
        frame === null || frame === undefined
          ? {}
          : { url: frame.url, isMainFrame: frame.parent === null },
        args,
      );
    });
  }
}

function createWindow(): BrowserWindow {
  const target = getHostSession();

  const window = createMainWindow(
    (options) =>
      new BrowserWindow({
        ...options,
        webPreferences: { ...options.webPreferences, session: target },
      }),
    PRELOAD_PATH,
  );

  applyNavigationPolicy(window.webContents, config, (url) => {
    // Double-checked: `decideWindowOpen` already applied the allow-list, and this re-applies it at
    // the one call site that hands a string to the operating system. `shell.openExternal` MUST
    // NEVER receive an untrusted URL (FE-EL-8, .claude/rules/24-electron.md), so it is checked twice.
    if (isExternalOpenAllowed(url, config)) {
      void shell.openExternal(url);
    }
  });

  void window.loadURL(RENDERER_ENTRY_URL);
  return window;
}

void app.whenReady().then(() => {
  const target = getHostSession();

  // Applied to the host session AND the default one. The host session is what the window uses;
  // the default is what anything created outside `createWindow` would fall back to, and a control
  // that only covers the expected path is not a control.
  for (const scope of [target, session.defaultSession]) {
    scope.setPermissionRequestHandler((_contents, permission, callback) => {
      callback(decidePermission(permission));
    });
    scope.setPermissionCheckHandler((_contents, permission) => decidePermission(permission));
    applyContentSecurityPolicy(scope, config);
  }

  registerRendererProtocol(target);
  registerIpcHandlers();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('second-instance', () => {
  const [existing] = BrowserWindow.getAllWindows();
  if (existing) {
    if (existing.isMinimized()) {
      existing.restore();
    }
    existing.focus();
  }
});

// A certificate error is never trusted. See `shouldTrustCertificateError` for why there is no
// development escape hatch.
app.on('certificate-error', (event, _contents, _url, _error, _certificate, callback) => {
  event.preventDefault();
  callback(shouldTrustCertificateError());
});

// Applies to every `WebContents`, including any created outside `createWindow`.
app.on('web-contents-created', (_event, contents) => {
  applyNavigationPolicy(contents, config, (url) => {
    if (isExternalOpenAllowed(url, config)) {
      void shell.openExternal(url);
    }
  });
  // A `<webview>` is disabled in `webPreferences`; this refuses one that is attached anyway.
  contents.on('will-attach-webview', (event) => event.preventDefault());
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
