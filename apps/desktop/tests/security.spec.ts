/**
 * T055 — the Electron security suite.
 *
 * Every assertion here corresponds to a control the constitution states unconditionally, and each
 * one **fails when its switch is flipped** — that is the Stage 4 gate. A protection without a
 * failing test does not count (plan Stage 11). `build/scripts/verify-desktop-security-guard.sh`
 * proves that claim by flipping each switch in a scratch copy and asserting this suite goes red.
 *
 * These are assertions over exported configuration and pure functions rather than a driven
 * Electron instance, deliberately: the control must be provable in CI on a machine with no
 * display, and a test that needs a real window is a test that gets skipped.
 */

import path from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  ALLOWED_REMOTE_SCHEMES,
  CONFIG_ENV_KEYS,
  DEFAULT_CONFIG,
  EXTERNAL_SCHEME,
  HostConfigurationError,
  loadHostConfig,
  parseOrigin,
  RENDERER_ORIGIN,
  type HostConfig,
} from '../src/main/config.js';
import { SECURE_WEB_PREFERENCES, buildWindowOptions } from '../src/main/window.js';
import {
  allowedRemoteOrigins,
  decideWindowOpen,
  isAllowedRemote,
  isExternalOpenAllowed,
  isNavigationAllowed,
  isRendererOrigin,
} from '../src/main/navigation.js';
import {
  CSP_HEADER,
  buildContentSecurityPolicy,
  isPolicySetAtSource,
  withContentSecurityPolicy,
} from '../src/main/csp.js';
import {
  IpcRefusedError,
  guarded,
  guardInvocation,
  isSenderTrusted,
  validateInvocation,
} from '../src/main/ipc-guard.js';
import {
  FORBIDDEN_SWITCHES,
  GRANTED_PERMISSIONS,
  ForbiddenSwitchError,
  assertNoForbiddenSwitches,
  decidePermission,
  findForbiddenSwitches,
  shouldTrustCertificateError,
  TRUST_CERTIFICATE_ERRORS,
} from '../src/main/app-shell.js';
import {
  RENDERER_SCHEME_PRIVILEGES,
  RendererPathError,
  createNonce,
  injectNonce,
  resolveBundlePath,
} from '../src/main/renderer-protocol.js';
import { SESSION_PARTITION } from '../src/main/session-boundary.js';

const CONFIG: HostConfig = Object.freeze({
  gatewayOrigin: 'https://gateway.example',
  realtimeOrigin: 'wss://realtime.example',
  authorityOrigin: 'https://login.microsoftonline.com',
});

// ------------------------------------------------------------------ webPreferences

describe('webPreferences — the mandatory switches', () => {
  it('disables nodeIntegration in the renderer, in workers and in subframes', () => {
    expect(SECURE_WEB_PREFERENCES.nodeIntegration).toBe(false);
    expect(SECURE_WEB_PREFERENCES.nodeIntegrationInWorker).toBe(false);
    expect(SECURE_WEB_PREFERENCES.nodeIntegrationInSubFrames).toBe(false);
  });

  it('enables contextIsolation', () => {
    expect(SECURE_WEB_PREFERENCES.contextIsolation).toBe(true);
  });

  it('enables sandbox unconditionally — plan Stage 4 resolves "where compatible"', () => {
    expect(SECURE_WEB_PREFERENCES.sandbox).toBe(true);
  });

  it('never disables webSecurity and never allows insecure content', () => {
    expect(SECURE_WEB_PREFERENCES.webSecurity).toBe(true);
    expect(SECURE_WEB_PREFERENCES.allowRunningInsecureContent).toBe(false);
  });

  it('disables the webview tag, experimental features and spellcheck', () => {
    expect(SECURE_WEB_PREFERENCES.webviewTag).toBe(false);
    expect(SECURE_WEB_PREFERENCES.experimentalFeatures).toBe(false);
    expect(SECURE_WEB_PREFERENCES.spellcheck).toBe(false);
  });

  it('is frozen, so a switch cannot be flipped at runtime', () => {
    expect(Object.isFrozen(SECURE_WEB_PREFERENCES)).toBe(true);
  });

  it('applies the security switches after the preload path, so no caller can override one', () => {
    const options = buildWindowOptions('/tmp/preload.js');
    expect(options.webPreferences?.preload).toBe('/tmp/preload.js');
    expect(options.webPreferences?.sandbox).toBe(true);
    expect(options.webPreferences?.contextIsolation).toBe(true);
    expect(options.webPreferences?.nodeIntegration).toBe(false);
  });
});

// ------------------------------------------------------------------ configuration

describe('configuration — origins are validated, not trusted', () => {
  it('requires HTTPS for the gateway and the authority, and WSS for realtime', () => {
    expect(() => loadHostConfig({ [CONFIG_ENV_KEYS.gatewayOrigin]: 'http://gateway.example' })).toThrow(
      HostConfigurationError,
    );
    expect(() =>
      loadHostConfig({ [CONFIG_ENV_KEYS.realtimeOrigin]: 'ws://realtime.example' }),
    ).toThrow(HostConfigurationError);
    expect(() =>
      loadHostConfig({ [CONFIG_ENV_KEYS.authorityOrigin]: 'http://login.example' }),
    ).toThrow(HostConfigurationError);
  });

  it.each([
    ['https://user:pass@gateway.example', 'credentials'],
    ['https://gateway.example/path', 'a path'],
    ['https://gateway.example/?q=1', 'a query'],
    ['https://gateway.example/#frag', 'a fragment'],
    ['not-a-url', 'an unparseable value'],
    ['', 'an empty value'],
  ])('refuses %s (%s)', (raw) => {
    expect(() => parseOrigin(raw, ['https:'], 'test')).toThrow(HostConfigurationError);
  });

  it('defaults to an unresolvable reserved domain, so an unconfigured build reaches nothing', () => {
    expect(DEFAULT_CONFIG.gatewayOrigin).toContain('.invalid');
    expect(DEFAULT_CONFIG.realtimeOrigin).toContain('.invalid');
  });

  it('freezes the loaded configuration', () => {
    expect(Object.isFrozen(loadHostConfig({}))).toBe(true);
  });
});

// ------------------------------------------------------------------ navigation

describe('navigation allow-list', () => {
  it('permits only HTTPS and WSS for a remote destination', () => {
    expect(ALLOWED_REMOTE_SCHEMES).toEqual(['https:', 'wss:']);
  });

  it('permits exactly the three configured origins and no more', () => {
    expect(allowedRemoteOrigins(CONFIG)).toEqual([
      CONFIG.gatewayOrigin,
      CONFIG.authorityOrigin,
      CONFIG.realtimeOrigin,
    ]);
  });

  it.each([
    ['http://gateway.example', 'plain http'],
    ['file:///etc/passwd', 'the file scheme'],
    ['synthia://open', 'an unrelated custom scheme'],
    ['javascript:alert(1)', 'the javascript scheme'],
    ['data:text/html,<script>1</script>', 'a data URL'],
    ['https://attacker.example', 'an unlisted origin'],
    ['https://gateway.example.attacker.example', 'a suffix-extended host'],
    ['https://gateway.example:8443', 'the right host on the wrong port'],
    ['not-a-url', 'an unparseable value'],
    ['', 'an empty value'],
  ])('refuses navigation to %s (%s)', (url) => {
    expect(isNavigationAllowed(url, CONFIG)).toBe(false);
  });

  it.each([
    ['https://gateway.example/api/customer/v1/views/sessions', 'the gateway'],
    ['https://login.microsoftonline.com/common/oauth2/authorize', 'the Entra authority'],
    ['wss://realtime.example/hubs/notifications', 'the realtime origin'],
  ])('permits navigation to %s (%s)', (url) => {
    expect(isNavigationAllowed(url, CONFIG)).toBe(true);
  });

  it('treats the renderer origin as the app itself, not as a remote destination', () => {
    const entry = `${RENDERER_ORIGIN}/index.html`;
    expect(isRendererOrigin(entry)).toBe(true);
    expect(isNavigationAllowed(entry, CONFIG)).toBe(true);
    expect(isAllowedRemote(entry, CONFIG)).toBe(false);
  });

  it.each([null, undefined, 42, {}, []])('fails closed on the non-string %p', (value) => {
    expect(isNavigationAllowed(value, CONFIG)).toBe(false);
    expect(isExternalOpenAllowed(value, CONFIG)).toBe(false);
  });
});

describe('shell.openExternal is stricter than navigation', () => {
  it('accepts only HTTPS', () => {
    expect(EXTERNAL_SCHEME).toBe('https:');
    expect(isExternalOpenAllowed('wss://realtime.example/hubs', CONFIG)).toBe(false);
  });

  it('never hands the renderer origin to the operating system', () => {
    expect(isExternalOpenAllowed(`${RENDERER_ORIGIN}/index.html`, CONFIG)).toBe(false);
  });

  it.each([
    'file:///C:/Windows/System32/cmd.exe',
    'ms-msdt:/id',
    'search-ms:query=x',
    'vbscript:msgbox(1)',
    'https://attacker.example/payload',
  ])('refuses %s', (url) => {
    expect(isExternalOpenAllowed(url, CONFIG)).toBe(false);
  });
});

describe('setWindowOpenHandler denies every destination without exception', () => {
  it('denies an allow-listed destination, and opens it in the OS browser instead', () => {
    const opened: string[] = [];
    const decision = decideWindowOpen('https://gateway.example/docs', CONFIG, (u) => opened.push(u));
    expect(decision.action).toBe('deny');
    expect(decision.openedExternally).toBe(true);
    expect(opened).toEqual(['https://gateway.example/docs']);
  });

  it('denies a destination outside the allow-list, and opens nothing', () => {
    const opened: string[] = [];
    const decision = decideWindowOpen('https://attacker.example', CONFIG, (u) => opened.push(u));
    expect(decision.action).toBe('deny');
    expect(decision.openedExternally).toBe(false);
    expect(opened).toEqual([]);
  });

  it('never returns an action other than deny, for any input', () => {
    for (const url of [
      `${RENDERER_ORIGIN}/x`,
      'https://gateway.example',
      'https://attacker.example',
      'javascript:alert(1)',
      '',
    ]) {
      expect(decideWindowOpen(url, CONFIG, () => undefined).action).toBe('deny');
    }
  });
});

// ------------------------------------------------------------------ CSP

describe('Content Security Policy', () => {
  const csp = buildContentSecurityPolicy(CONFIG);

  it("carries no 'unsafe-eval' — the Angular build is AOT precisely so it does not need one", () => {
    expect(csp).not.toContain('unsafe-eval');
  });

  it("carries no 'unsafe-inline' in ANY directive, including style-src", () => {
    expect(csp).not.toContain('unsafe-inline');
  });

  it('keeps script-src to self, with no nonce and no host', () => {
    const scriptSrc = csp.split('; ').find((d) => d.startsWith('script-src'));
    expect(scriptSrc).toBe("script-src 'self'");
  });

  it('keeps style-src strict when no nonce is minted', () => {
    const styleSrc = csp.split('; ').find((d) => d.startsWith('style-src'));
    expect(styleSrc).toBe("style-src 'self'");
  });

  it('names the nonce in style-src, and only there, when one is minted', () => {
    const withNonce = buildContentSecurityPolicy(CONFIG, 'abc123');
    expect(withNonce).toContain("style-src 'self' 'nonce-abc123'");
    expect(withNonce.split('; ').find((d) => d.startsWith('script-src'))).toBe("script-src 'self'");
    expect(withNonce).not.toContain('unsafe-inline');
  });

  it.each([
    ["default-src 'self'", 'the default denies'],
    ["frame-ancestors 'none'", 'the host cannot be framed'],
    ["object-src 'none'", 'no plugins'],
    ["base-uri 'self'", 'a base tag cannot point at another origin'],
    ["form-action 'self'", 'a form cannot post off-origin'],
    ['upgrade-insecure-requests', 'no downgrade'],
  ])('sets %s (%s)', (directive) => {
    expect(csp).toContain(directive);
  });

  it('narrows connect-src to exactly the configured origins', () => {
    const connectSrc = csp.split('; ').find((d) => d.startsWith('connect-src'));
    expect(connectSrc).toBe(
      `connect-src 'self' ${CONFIG.gatewayOrigin} ${CONFIG.realtimeOrigin} ${CONFIG.authorityOrigin}`,
    );
    expect(connectSrc).not.toContain('*');
  });

  it('names no origin the navigation allow-list would refuse', () => {
    const origins = csp.match(/https?:\/\/[^\s;]+|wss:\/\/[^\s;]+/g) ?? [];
    for (const origin of origins) {
      expect(isNavigationAllowed(origin, CONFIG)).toBe(true);
    }
  });

  it('replaces a server-supplied policy rather than merging with it', () => {
    const headers = withContentSecurityPolicy(
      { 'content-security-policy': ["default-src *"], 'x-other': ['keep'] },
      CONFIG,
    );
    expect(headers[CSP_HEADER]).toEqual([csp]);
    expect(headers['content-security-policy']).toBeUndefined();
    expect(headers['x-other']).toEqual(['keep']);
  });

  it('attaches the policy even when the response carried no headers at all', () => {
    expect(withContentSecurityPolicy(undefined, CONFIG)[CSP_HEADER]).toEqual([csp]);
  });

  it('enforces rather than reports', () => {
    expect(CSP_HEADER).toBe('Content-Security-Policy');
    expect(CSP_HEADER).not.toContain('Report-Only');
  });

  it('leaves the renderer document alone, because its policy is set at the source', () => {
    expect(isPolicySetAtSource(`${RENDERER_ORIGIN}/index.html`)).toBe(true);
  });

  it.each([
    ['https://gateway.example/api', 'a remote response'],
    ['file:///C:/x.html', 'a file URL'],
    ['', 'an unparseable URL'],
  ])('applies the interceptor policy to %s (%s)', (url) => {
    expect(isPolicySetAtSource(url)).toBe(false);
  });
});

describe('CSP nonce', () => {
  it('is unpredictable and freshly minted each time', () => {
    const nonces = new Set(Array.from({ length: 64 }, () => createNonce()));
    expect(nonces.size).toBe(64);
  });

  it('carries at least 128 bits of entropy', () => {
    expect(Buffer.from(createNonce(), 'base64').length).toBeGreaterThanOrEqual(16);
  });

  it('hands the nonce to Angular through ngCspNonce on the root element', () => {
    const html = injectNonce('<body><app-root></app-root></body>', 'N1');
    expect(html).toContain('<app-root ngCspNonce="N1">');
  });

  it('nonces an inline style element the builder may have inlined', () => {
    const html = injectNonce('<head><style>a{}</style></head>', 'N1');
    expect(html).toContain('<style nonce="N1">');
  });

  it('never nonces a script — an inline script must stay blocked', () => {
    const html = injectNonce('<script>alert(1)</script><script src="a.js"></script>', 'N1');
    expect(html).not.toContain('nonce');
  });

  it('leaves a document with neither element untouched', () => {
    expect(injectNonce('<p>nothing here</p>', 'N1')).toBe('<p>nothing here</p>');
  });
});

// ------------------------------------------------------------------ IPC

describe('IPC — sender validation and argument validation are two distinct checks', () => {
  const senderUrl = `${RENDERER_ORIGIN}/index.html`;

  it('refuses an untrusted sender even on a valid channel with valid arguments', () => {
    expect(
      guardInvocation({ url: 'https://attacker.example/x', isMainFrame: true }, 'host:getVersion', []),
    ).toEqual({ ok: false, reason: 'untrusted-sender' });
  });

  it('refuses invalid arguments even from a trusted sender', () => {
    expect(
      guardInvocation({ url: senderUrl, isMainFrame: true }, 'host:getVersion', ['unexpected']),
    ).toEqual({ ok: false, reason: 'invalid-arguments' });
  });

  it('refuses a channel that is not on the allow-list', () => {
    expect(validateInvocation('host:runScript', [])).toEqual({
      ok: false,
      reason: 'unknown-channel',
    });
  });

  it('refuses a subframe sender on the app origin', () => {
    expect(guardInvocation({ url: senderUrl, isMainFrame: false }, 'host:getVersion', [])).toEqual({
      ok: false,
      reason: 'subframe-sender',
    });
  });

  it.each([
    [{}, 'no URL at all'],
    [{ url: '' }, 'an empty URL'],
    [{ url: 'not-a-url' }, 'an unparseable URL'],
    [{ url: 'file:///C:/app/index.html' }, 'an opaque file origin'],
    [{ url: 'data:text/html,x' }, 'a data URL'],
  ])('fails closed on a sender with %p (%s)', (sender) => {
    expect(isSenderTrusted(sender)).toBe(false);
  });

  it('accepts a trusted main-frame sender on a known channel with valid arguments', () => {
    expect(guardInvocation({ url: senderUrl, isMainFrame: true }, 'host:getVersion', [])).toEqual({
      ok: true,
      channel: 'host:getVersion',
    });
  });

  it('makes the guard the only way to reach a handler', () => {
    let ran = false;
    const handler = guarded('host:getVersion', () => {
      ran = true;
      return { version: '1.0.0' };
    });

    expect(() => handler({ url: 'https://attacker.example/' }, [])).toThrow(IpcRefusedError);
    expect(ran).toBe(false);

    expect(handler({ url: senderUrl, isMainFrame: true }, [])).toEqual({ version: '1.0.0' });
    expect(ran).toBe(true);
  });

  it('leaks no host configuration in a refusal message', () => {
    const error = new IpcRefusedError('host:getVersion', 'untrusted-sender');
    expect(error.message).toBe('IPC refused on host:getVersion: untrusted-sender');
    expect(error.message).not.toContain('gateway');
  });
});

// ------------------------------------------------------------------ renderer protocol

describe('renderer protocol — the bundle is contained', () => {
  const root = '/srv/bundle';

  it('is registered as a standard, secure, CORS-enabled scheme', () => {
    const { privileges } = RENDERER_SCHEME_PRIVILEGES;
    expect(privileges.standard).toBe(true);
    expect(privileges.secure).toBe(true);
    expect(privileges.corsEnabled).toBe(true);
    expect(privileges.allowServiceWorkers).toBe(false);
  });

  it('resolves the entry document for the root path', () => {
    expect(resolveBundlePath(root, `${RENDERER_ORIGIN}/`)).toContain('index.html');
  });

  it.each([
    ['/%2e%2e%2f%2e%2e%2fetc/passwd', 'encoded traversal'],
    ['/..%2f..%2fsecret', 'mixed traversal'],
    ['/assets/%00.js', 'a NUL byte'],
  ])('refuses %s (%s)', (suffix) => {
    expect(() => resolveBundlePath(root, `${RENDERER_ORIGIN}${suffix}`)).toThrow(RendererPathError);
  });

  it('collapses a literal parent traversal during URL parsing, and stays contained', () => {
    // `app://renderer/../../../etc/passwd` normalises to `/etc/passwd` in the URL parser before
    // this function sees it, so there is nothing left to refuse — the check that matters is that
    // the result is still inside the bundle. The encoded forms above are the ones the parser does
    // NOT collapse, and those throw.
    const resolved = resolveBundlePath(root, `${RENDERER_ORIGIN}/../../../etc/passwd`);
    expect(resolved.startsWith(path.resolve(root))).toBe(true);
  });

  it('refuses a request for a different origin on the same scheme', () => {
    expect(() => resolveBundlePath(root, 'app://elsewhere/index.html')).toThrow(RendererPathError);
  });

  it('refuses a request on a different scheme entirely', () => {
    expect(() => resolveBundlePath(root, 'https://gateway.example/index.html')).toThrow(
      RendererPathError,
    );
  });
});

// ------------------------------------------------------------------ process hardening

describe('process hardening', () => {
  it('grants no permission to the renderer', () => {
    expect(GRANTED_PERMISSIONS).toEqual([]);
    for (const permission of ['media', 'geolocation', 'notifications', 'clipboard-read', 'midi']) {
      expect(decidePermission(permission)).toBe(false);
    }
  });

  it('never trusts a certificate error, in any environment', () => {
    expect(TRUST_CERTIFICATE_ERRORS).toBe(false);
    expect(shouldTrustCertificateError()).toBe(false);
  });

  it.each([
    '--disable-web-security',
    '--ignore-certificate-errors',
    '--allow-running-insecure-content',
    '--remote-debugging-port=9222',
    '--no-sandbox',
    '--JS-Flags=--allow-natives-syntax',
  ])('refuses to start under %s', (argument) => {
    expect(() => assertNoForbiddenSwitches(['electron', '.', argument])).toThrow(
      ForbiddenSwitchError,
    );
  });

  it('starts cleanly with ordinary arguments', () => {
    expect(() => assertNoForbiddenSwitches(['electron', '.', '--enable-logging'])).not.toThrow();
    expect(findForbiddenSwitches(['electron', '.'])).toEqual([]);
  });

  it('lists every switch that would disable a control asserted elsewhere', () => {
    expect(FORBIDDEN_SWITCHES).toContain('disable-web-security');
    expect(FORBIDDEN_SWITCHES).toContain('ignore-certificate-errors');
    expect(FORBIDDEN_SWITCHES).toContain('no-sandbox');
  });

  it('keeps no session and no cache on disk', () => {
    expect(SESSION_PARTITION.persistSession).toBe(false);
    expect(SESSION_PARTITION.cache).toBe(false);
    expect(SESSION_PARTITION.partition.startsWith('persist:')).toBe(false);
  });
});
