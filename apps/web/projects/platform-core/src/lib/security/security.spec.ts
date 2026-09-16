import {
  FORBIDDEN_CSP_TOKENS,
  REQUIRED_CSP_DIRECTIVES,
  assertNoCspMetaTag,
  buildCspHeader,
  type CspOrigins,
} from './content-security-policy';
import { SANITIZATION_POLICY } from './sanitization-policy';

describe('CSP baseline', () => {
  const origins: CspOrigins = {
    gatewayOrigin: 'https://api.synthia.example',
    signalROrigin: 'wss://realtime.synthia.example',
    authAuthority: 'https://login.microsoftonline.com',
  };

  const header = (): string => buildCspHeader(origins, { styleNonce: 'r4nd0m' });

  it('emits every directive the plan Stage 3 baseline requires', () => {
    const policy = header();
    for (const directive of REQUIRED_CSP_DIRECTIVES) {
      expect(policy).withContext(`missing ${directive}`).toContain(directive);
    }
  });

  it('never emits unsafe-inline or unsafe-eval in script-src', () => {
    const scriptSrc = header()
      .split('; ')
      .find((directive) => directive.startsWith('script-src'));
    expect(scriptSrc).toBe(`script-src 'self'`);
  });

  it('never emits a forbidden token anywhere', () => {
    const policy = header();
    for (const token of FORBIDDEN_CSP_TOKENS) {
      expect(policy).withContext(`policy contains ${token}`).not.toContain(token);
    }
  });

  // connect-src is the load-bearing directive (plan Stage 3).
  it('narrows connect-src to exactly self, the gateway, SignalR and Entra', () => {
    const connectSrc = header()
      .split('; ')
      .find((directive) => directive.startsWith('connect-src'));
    expect(connectSrc).toBe(
      `connect-src 'self' https://api.synthia.example wss://realtime.synthia.example ` +
        `https://login.microsoftonline.com`,
    );
  });

  it('configures exactly one platform origin (FR-SURF-017)', () => {
    const connectSrc =
      header()
        .split('; ')
        .find((directive) => directive.startsWith('connect-src')) ?? '';
    const httpsOrigins = connectSrc.match(/https:\/\/[^\s]+/g) ?? [];
    // The gateway and the Entra authority. There is no second platform origin.
    expect(httpsOrigins).toEqual([origins.gatewayOrigin, origins.authAuthority]);
  });

  it('denies framing and locks the base URI', () => {
    const policy = header();
    expect(policy).toContain(`frame-ancestors 'none'`);
    expect(policy).toContain(`base-uri 'none'`);
    expect(policy).toContain(`object-src 'none'`);
  });

  it('carries a per-response nonce for Angular injected styles', () => {
    expect(header()).toContain(`style-src 'self' 'nonce-r4nd0m'`);
  });

  it('refuses to build a policy without a style nonce', () => {
    expect(() => buildCspHeader(origins, { styleNonce: '   ' })).toThrowError(
      /style nonce is required/i,
    );
  });
});

describe('CSP delivery', () => {
  const withMeta = (doc: Document, content: string): HTMLMetaElement => {
    const meta = doc.createElement('meta');
    meta.setAttribute('http-equiv', content);
    meta.setAttribute('content', `default-src 'self'`);
    doc.head.appendChild(meta);
    return meta;
  };

  it('accepts a document with no CSP meta tag', () => {
    expect(() => assertNoCspMetaTag(document)).not.toThrow();
  });

  // A policy in a <meta> tag can be stripped by injected markup, and frame-ancestors is ignored
  // there entirely. The baseline is a response header (plan Stage 3).
  it('rejects a CSP delivered as a meta tag', () => {
    const meta = withMeta(document, 'Content-Security-Policy');
    try {
      expect(() => assertNoCspMetaTag(document)).toThrowError(
        /response header, never a <meta> tag/,
      );
    } finally {
      meta.remove();
    }
  });

  it('rejects a CSP meta tag regardless of attribute casing', () => {
    const meta = withMeta(document, 'content-security-policy');
    try {
      expect(() => assertNoCspMetaTag(document)).toThrow();
    } finally {
      meta.remove();
    }
  });
});

describe('sanitization policy', () => {
  it('permits no security bypass API', () => {
    expect(SANITIZATION_POLICY.bypassApisPermitted).toBeFalse();
  });

  it('renders agent-authored content as text, never as HTML', () => {
    expect(SANITIZATION_POLICY.agentContentRendersAs).toBe('text');
  });

  it('delivers the policy as a response header', () => {
    expect(SANITIZATION_POLICY.cspDeliveredAs).toBe('response-header');
  });
});
