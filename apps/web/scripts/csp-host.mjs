// The hosting tier for the two browser portals — the one the container image runs (ADR-0009).
//
// The CSP baseline is a RESPONSE HEADER with a PER-RESPONSE style nonce (platform-core
// content-security-policy.ts). A static header cannot satisfy that — a fixed nonce is no nonce — so
// `ng serve` cannot deliver it, and nothing else in the repository did: the policy was built and
// unit-tested but never sent. This server is the executable statement of the hosting contract:
//
//   1. a fresh nonce per document response,
//   2. the same nonce handed to Angular through `ngCspNonce` on the root element,
//   3. the header produced by `buildCspHeader` itself — imported, never restated — so the policy
//      that is tested is the policy that is served.
//
// It also supplies the bundle's environment: an image promoted by digest cannot carry its own
// gateway origin or client id, so they are written into the document as an inert JSON block and
// read back by `readHostedConfig`. `e2e/csp-hosting.spec.ts` drives the built portals through
// this server and fails on any CSP violation.
//
// Usage:  node scripts/csp-host.mjs <customer-portal|staff-portal> <port>
// Needs Node 22.18+ (TypeScript type stripping, to import the policy source directly) and a built
// portal in dist/ (`npm run build`).

import { randomBytes } from 'node:crypto';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildCspHeader } from '../projects/platform-core/src/lib/security/content-security-policy.ts';

const PORTALS = new Set(['customer-portal', 'staff-portal']);
const [appArgument, portArgument] = process.argv.slice(2);

// Arguments locally, environment in the container — the image is built per portal and the Container
// App sets neither, so the defaults below are what production runs on.
const app = appArgument ?? process.env.SYNTHIA_PORTAL ?? '';
const port = portArgument ?? process.env.PORT ?? '8080';

if (!PORTALS.has(app)) {
  console.error('Usage: node scripts/csp-host.mjs <customer-portal|staff-portal> [port]');
  console.error('   or: SYNTHIA_PORTAL=<portal> PORT=<port> node scripts/csp-host.mjs');
  process.exit(2);
}

const here = fileURLToPath(new URL('.', import.meta.url));
const root = resolve(here, '..', 'dist', app, 'browser');

// The origins the portal may reach. Local defaults; a real host supplies its own.
const origins = {
  gatewayOrigin: process.env.SYNTHIA_GATEWAY_ORIGIN ?? 'https://api.synthia.local',
  signalROrigin: process.env.SYNTHIA_SIGNALR_ORIGIN ?? 'wss://realtime.synthia.local',
  authAuthority: process.env.SYNTHIA_AUTH_AUTHORITY ?? 'https://login.microsoftonline.com',
};

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.ico': 'image/x-icon',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.json': 'application/json',
  '.woff2': 'font/woff2',
};

/** Resolve a request path inside the build output, or null when it would leave it. */
function contained(urlPath) {
  const candidate = resolve(root, '.' + normalize(decodeURIComponent(urlPath)));
  return candidate === root || candidate.startsWith(root + sep) ? candidate : null;
}

// The configuration this deployment gives the bundle. A promoted-by-digest image cannot carry its
// own environment, so the tier writes it into the document and `readHostedConfig` reads it back.
// Absent here — a developer machine — the bundle keeps its compiled defaults.
const hostedConfig = {
  ...(process.env.SYNTHIA_GATEWAY_ORIGIN
    ? { gatewayOrigin: process.env.SYNTHIA_GATEWAY_ORIGIN }
    : {}),
  ...(process.env.SYNTHIA_AUTH_AUTHORITY
    ? { authAuthority: process.env.SYNTHIA_AUTH_AUTHORITY }
    : {}),
  ...(process.env.SYNTHIA_AUTH_CLIENT_ID
    ? { authClientId: process.env.SYNTHIA_AUTH_CLIENT_ID }
    : {}),
  ...(process.env.SYNTHIA_AUTH_SCOPES
    ? { authScopes: process.env.SYNTHIA_AUTH_SCOPES.split(',').map((scope) => scope.trim()) }
    : {}),
};

/** The config as a JSON data block. Not executable, so it needs no nonce and runs nothing. */
function configBlock() {
  if (Object.keys(hostedConfig).length === 0) {
    return '';
  }

  // `<` is escaped so no value can close the element early. The block is inert either way, but a
  // string that can end its own container is the shape every injection starts from.
  const json = JSON.stringify(hostedConfig).replaceAll('<', '\\u003c');
  return `<script type="application/json" id="synthia-platform-config">${json}</script>`;
}

async function document(response) {
  const nonce = randomBytes(16).toString('base64');
  const html = (await readFile(join(root, 'index.html'), 'utf8'))
    .replace('<app-root>', `<app-root ngCspNonce="${nonce}">`)
    .replace('</head>', `${configBlock()}</head>`);
  response.writeHead(200, {
    'Content-Type': TYPES['.html'],
    'Content-Security-Policy': buildCspHeader(origins, { styleNonce: nonce }),
    'X-Content-Type-Options': 'nosniff',
    'Cache-Control': 'no-store',
  });
  response.end(html);
}

const server = createServer(async (request, response) => {
  const path = new URL(request.url ?? '/', 'http://host').pathname;

  // Liveness: process-only, no dependency, nothing disclosed. Front Door probes it as the origin
  // health probe and the Container App as its liveness probe, so it must answer before anything
  // else is resolved — and it must never be mistaken for a client route into the bundle.
  if (path === '/health/live') {
    response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    response.end('{"status":"ok"}');
    return;
  }

  const file = contained(path);

  if (file === null) {
    response.writeHead(400).end();
    return;
  }

  // A route without an extension is a client-side route: serve the document, with a fresh nonce.
  if (path === '/' || extname(file) === '') {
    await document(response);
    return;
  }

  try {
    const body = await readFile(file);
    response.writeHead(200, {
      'Content-Type': TYPES[extname(file)] ?? 'application/octet-stream',
      'X-Content-Type-Options': 'nosniff',
      // The build gives every asset a content hash, so a given URL's bytes never change. The
      // document is the opposite and is served `no-store`: it carries a per-response nonce.
      'Cache-Control': 'public, max-age=31536000, immutable',
    });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});

// Loopback by default: run locally, this serves a development machine and has no business being
// reachable from the network. The container sets SYNTHIA_BIND=0.0.0.0, where the only thing that
// can reach it is the Container Apps ingress, which is internal-only and fronted by Front Door.
const bind = process.env.SYNTHIA_BIND ?? '127.0.0.1';

server.listen(Number(port), bind, () => {
  console.log(`${app} served with the CSP baseline on http://${bind}:${port}`);
});
