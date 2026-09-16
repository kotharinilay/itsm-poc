/**
 * T050 — secure `BrowserWindow` configuration.
 *
 * The switches are exported as **data** rather than applied inline, so `tests/security.spec.ts`
 * can assert each one and fail when it is flipped. A protection without a failing test does not
 * count (plan Stage 11), and a protection buried in a constructor call is a protection the next
 * change silently drops.
 *
 * The endpoint runs inside a customer network and is outside platform control. Anything it decides
 * is a decision an attacker can make instead — so it decides nothing (constitution Principle VII).
 */

import type { BrowserWindow, BrowserWindowConstructorOptions } from 'electron';

/**
 * `webPreferences` for **every** window.
 *
 * `sandbox` is unconditional here. The constitution says "where compatible"; plan Stage 4 resolves
 * that discretion, because the one thing that breaks the sandbox — a preload needing Node built-ins
 * — does not apply to a preload that exposes a narrow typed bridge and nothing else. Turning it off
 * requires an ADR, not a code comment.
 */
export const SECURE_WEB_PREFERENCES: Readonly<
  NonNullable<BrowserWindowConstructorOptions['webPreferences']>
> = Object.freeze({
  /** No Node in the renderer, in a worker, or in a subframe. All three, because all three exist. */
  nodeIntegration: false,
  nodeIntegrationInWorker: false,
  nodeIntegrationInSubFrames: false,
  /** The preload runs in its own context; the page cannot reach the preload's scope. */
  contextIsolation: true,
  /** Unconditional — see above. */
  sandbox: true,
  /** Same-origin policy stays on. There is no configuration under which this becomes false. */
  webSecurity: true,
  /** No mixed content, ever. */
  allowRunningInsecureContent: false,
  /** No experimental web platform features in a host that renders customer-facing content. */
  experimentalFeatures: false,
  /** `<webview>` is a second, weaker embedding surface. It is not used and must not be available. */
  webviewTag: false,
  /** No spellcheck round-trip: it sends typed text, including chat content, to a remote service. */
  spellcheck: false,
});

/** Window geometry. Separated from the security switches so a layout change cannot touch them. */
export const WINDOW_OPTIONS: Readonly<Omit<BrowserWindowConstructorOptions, 'webPreferences'>> =
  Object.freeze({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 600,
    /** Shown on `ready-to-show` so the user never sees an unpainted frame. */
    show: false,
    title: 'Synthia',
    backgroundColor: '#ffffff',
  });

/**
 * Compose the full constructor options.
 *
 * The spread order matters and is asserted: `SECURE_WEB_PREFERENCES` is spread **last** within
 * `webPreferences`, so no caller-supplied preference can override a security switch.
 */
export function buildWindowOptions(preloadPath: string): BrowserWindowConstructorOptions {
  return {
    ...WINDOW_OPTIONS,
    webPreferences: {
      preload: preloadPath,
      ...SECURE_WEB_PREFERENCES,
    },
  };
}

/**
 * The minimum surface of a window this module needs, so the shell can be exercised without a real
 * Electron instance.
 */
export interface WindowFactory {
  (options: BrowserWindowConstructorOptions): BrowserWindow;
}

/**
 * Create the main window.
 *
 * Deliberately does no navigation policy and no CSP work of its own — `navigation.ts` and `csp.ts`
 * own those, and the shell wires all three together. Keeping them apart is what lets each be
 * tested in isolation and what stops a window-creation change from quietly weakening a policy.
 */
export function createMainWindow(factory: WindowFactory, preloadPath: string): BrowserWindow {
  const window = factory(buildWindowOptions(preloadPath));
  window.once('ready-to-show', () => window.show());
  return window;
}
