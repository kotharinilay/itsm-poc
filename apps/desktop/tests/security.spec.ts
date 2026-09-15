/**
 * Electron security suite (T055, T056).
 *
 * Every assertion here corresponds to a control the constitution states unconditionally. Each
 * one **fails when its switch is flipped** — that is the gate. A protection without a failing
 * test does not count (plan Stage 11).
 *
 * These are pure-function assertions over exported configuration rather than a driven Electron
 * instance, deliberately: the control must be provable in CI on a machine with no display, and a
 * test that needs a real window is a test that gets skipped.
 */

import { describe, expect, it } from 'vitest';

import {
  ALLOWED_SCHEMES,
  buildContentSecurityPolicy,
  isNavigationAllowed,
  SECURE_WEB_PREFERENCES,
} from '../src/main/security.js';
import { guardInvocation, isSenderTrusted, validateInvocation } from '../src/main/ipc-guard.js';
import { IPC_CHANNELS } from '../src/ipc-contracts/index.js';

const TRUSTED = ['https://app.example'];

describe('webPreferences — the mandatory switches', () => {
  it('disables nodeIntegration in the renderer, workers and subframes', () => {
    expect(SECURE_WEB_PREFERENCES?.nodeIntegration).toBe(false);
    expect(SECURE_WEB_PREFERENCES?.nodeIntegrationInWorker).toBe(false);
    expect(SECURE_WEB_PREFERENCES?.nodeIntegrationInSubFrames).toBe(false);
  });

  it('enables contextIsolation', () => {
    expect(SECURE_WEB_PREFERENCES?.contextIsolation).toBe(true);
  });

  it('enables sandbox unconditionally — plan Stage 4 resolves "where compatible"', () => {
    expect(SECURE_WEB_PREFERENCES?.sandbox).toBe(true);
  });

  it('never disables webSecurity and never allows insecure content', () => {
    expect(SECURE_WEB_PREFERENCES?.webSecurity).toBe(true);
    expect(SECURE_WEB_PREFERENCES?.allowRunningInsecureContent).toBe(false);
  });

  it('disables the webview tag and experimental features', () => {
    expect(SECURE_WEB_PREFERENCES?.webviewTag).toBe(false);
    expect(SECURE_WEB_PREFERENCES?.experimentalFeatures).toBe(false);
  });
});

describe('navigation allow-list', () => {
  it('permits only HTTPS and WSS', () => {
    expect(ALLOWED_SCHEMES).toEqual(['https:', 'wss:']);
  });

  it.each([
    ['http://gateway.invalid', 'plain http'],
    ['file:///etc/passwd', 'file scheme'],
    ['synthia://open', 'custom scheme'],
    ['https://attacker.example', 'unlisted origin'],
    ['not-a-url', 'unparseable'],
    ['', 'empty'],
  ])('refuses %s (%s)', (url) => {
    expect(isNavigationAllowed(url)).toBe(false);
  });

  it('permits the Entra authority, because interactive sign-in needs it', () => {
    expect(isNavigationAllowed('https://login.microsoftonline.com/common/oauth2/authorize')).toBe(
      true,
    );
  });
});

describe('Content Security Policy', () => {
  const csp = buildContentSecurityPolicy();

  it("carries no 'unsafe-eval' — the build is AOT precisely so it does not need one", () => {
    expect(csp).not.toContain('unsafe-eval');
  });

  it.each([
    ["default-src 'self'", 'default denies'],
    ["frame-ancestors 'none'", 'cannot be framed'],
    ["object-src 'none'", 'no plugins'],
    ["base-uri 'none'", 'base tag cannot be hijacked'],
  ])('sets %s (%s)', (directive) => {
    expect(csp).toContain(directive);
  });
});

describe('IPC — sender and argument validation are two distinct checks', () => {
  it('refuses an untrusted sender even on a valid channel with valid arguments', () => {
    const decision = guardInvocation(
      { url: 'https://attacker.example/x' },
      TRUSTED,
      'app:getVersion',
      [],
    );
    expect(decision).toEqual({ ok: false, reason: 'untrusted-sender' });
  });

  it('refuses invalid arguments even from a trusted sender', () => {
    const decision = guardInvocation({ url: 'https://app.example/' }, TRUSTED, 'app:getVersion', [
      'unexpected',
    ]);
    expect(decision).toEqual({ ok: false, reason: 'invalid-arguments' });
  });

  it('refuses a channel that is not on the allow-list', () => {
    expect(validateInvocation('app:runScript', [])).toEqual({
      ok: false,
      reason: 'unknown-channel',
    });
  });

  it('fails closed on an unparseable sender URL', () => {
    expect(isSenderTrusted({ url: '' }, TRUSTED)).toBe(false);
  });

  it('accepts a trusted sender on a known channel with valid arguments', () => {
    expect(guardInvocation({ url: 'https://app.example/' }, TRUSTED, 'app:getVersion', [])).toEqual({
      ok: true,
      channel: 'app:getVersion',
    });
  });
});

describe('the host decides nothing (constitution Principle VII)', () => {
  it('exposes no channel that returns a permission, role, tenant or approval state', () => {
    const authorityWords = ['role', 'permission', 'approve', 'approval', 'tenant', 'authoriz'];
    for (const channel of IPC_CHANNELS) {
      for (const word of authorityWords) {
        expect(channel.toLowerCase()).not.toContain(word);
      }
    }
  });

  it('exposes no script-execution channel — the endpoint path is deferred (ADR-0004)', () => {
    for (const channel of IPC_CHANNELS) {
      expect(channel.toLowerCase()).not.toContain('script');
      expect(channel.toLowerCase()).not.toContain('exec');
    }
  });
});
