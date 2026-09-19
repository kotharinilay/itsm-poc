import {
  HOSTED_CONFIG_ELEMENT_ID,
  type PlatformApiConfig,
  readHostedConfig,
} from './platform-api.config';

/**
 * The bundle takes its environment from the hosting tier, not from the build (ADR-0009).
 *
 * The same image is promoted between environments by digest, so a gateway origin compiled in would
 * mean a per-environment build — and the artefact reviewed in one environment would not be the one
 * running in another. The tier writes the values into the document; this reads them back.
 */
describe('readHostedConfig', () => {
  const compiled: PlatformApiConfig = {
    gatewayOrigin: 'https://localhost:7443',
    authAuthority: 'https://login.microsoftonline.com/common',
    authClientId: '00000000-0000-0000-0000-000000000000',
    authScopes: ['api://synthia-platform/.default'],
  };

  function documentWith(content: string | null): Document {
    const doc = window.document.implementation.createHTMLDocument('test');
    if (content !== null) {
      const block = doc.createElement('script');
      block.type = 'application/json';
      block.id = HOSTED_CONFIG_ELEMENT_ID;
      block.textContent = content;
      doc.head.appendChild(block);
    }
    return doc;
  }

  it('takes the values the hosting tier supplied', () => {
    const doc = documentWith(
      JSON.stringify({
        gatewayOrigin: 'https://api.synthia.example',
        authClientId: '11111111-1111-1111-1111-111111111111',
      }),
    );

    const config = readHostedConfig(doc, compiled);

    expect(config.gatewayOrigin).toBe('https://api.synthia.example');
    expect(config.authClientId).toBe('11111111-1111-1111-1111-111111111111');
    // Unsupplied values keep the compiled ones rather than becoming undefined.
    expect(config.authScopes).toEqual(compiled.authScopes);
  });

  it('falls back to the compiled configuration when the tier supplied none', () => {
    // A developer machine: `ng serve` writes no block, and the local gateway is the right answer.
    expect(readHostedConfig(documentWith(null), compiled)).toEqual(compiled);
  });

  it('fails loudly on a malformed block rather than falling back', () => {
    // Silently falling back would point a deployed portal at the developer default, which is the
    // failure this mechanism exists to prevent.
    expect(() => readHostedConfig(documentWith('{not json'), compiled)).toThrowError(/malformed/);
  });

  it('holds a supplied value to the same rules as a compiled one', () => {
    const plaintext = documentWith(JSON.stringify({ gatewayOrigin: 'http://api.example' }));

    expect(() => readHostedConfig(plaintext, compiled)).toThrowError(/https/);
  });

  it('refuses a supplied value that looks like a secret', () => {
    const withSecret = documentWith(JSON.stringify({ clientSecret: 'hunter2' }));

    expect(() => readHostedConfig(withSecret, compiled)).toThrowError(/secret/);
  });
});
