import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it } from 'node:test';

/**
 * Architecture test: **no presentation component makes an authorization decision.**
 *
 * Spec FR-SURF-004 — no client surface makes an authorization, tenancy or policy decision, and
 * every client-side role check is presentation only and re-decided server-side. Backend
 * authorization is authoritative; nothing in this workspace is a security boundary.
 *
 * This runs on Node rather than Karma because it reads source text. A browser test can only assert
 * what the code does at runtime, and the rule here is about what the code *is allowed to contain* —
 * which is exactly why the task places this file outside `src/`, where the Karma tsconfig does not
 * reach it. Run it with `npm run test:architecture`.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const projectsRoot = path.resolve(here, '..');
const workspaceRoot = path.resolve(projectsRoot, '..');

/** Presentation code: the three applications and the two feature libraries. */
const PRESENTATION_PROJECTS = [
  'customer-portal',
  'staff-portal',
  'desktop-renderer',
  'customer-features',
  'staff-features',
] as const;

/** The one place a role may legitimately be evaluated for presentation. */
const ROLE_VISIBILITY_MODULE = path.join(
  projectsRoot,
  'platform-core',
  'src',
  'lib',
  'auth',
  'role-visibility.ts',
);

interface SourceFile {
  readonly absolutePath: string;
  readonly relativePath: string;
  readonly text: string;
}

function collectTypeScript(root: string): readonly SourceFile[] {
  const files: SourceFile[] = [];

  const walk = (directory: string): void => {
    for (const entry of readdirSync(directory)) {
      if (entry === 'node_modules' || entry === 'dist' || entry.startsWith('.')) {
        continue;
      }
      const absolutePath = path.join(directory, entry);
      if (statSync(absolutePath).isDirectory()) {
        walk(absolutePath);
      } else if (entry.endsWith('.ts')) {
        files.push({
          absolutePath,
          relativePath: path.relative(workspaceRoot, absolutePath).replace(/\\/g, '/'),
          text: readFileSync(absolutePath, 'utf8'),
        });
      }
    }
  };

  walk(root);
  return files;
}

const presentationSources: readonly SourceFile[] = PRESENTATION_PROJECTS.flatMap((project) =>
  collectTypeScript(path.join(projectsRoot, project)),
);

/**
 * Everything under `projects/`, except this scanner.
 *
 * The scanner is excluded because it necessarily contains the very patterns it looks for — its
 * regexes name `bypassSecurityTrust`, `[innerHTML]` and the credential keys. Scanning itself would
 * make it fail on its own definition, which says nothing about the code under review.
 */
const allSources: readonly SourceFile[] = collectTypeScript(projectsRoot).filter(
  (file) => file.absolutePath !== fileURLToPath(import.meta.url),
);

/** Strip comments and string literals, so prose about a rule is never mistaken for the rule. */
function code(text: string): string {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/\/\/[^\n]*/g, ' ')
    .replace(/'(?:[^'\\\n]|\\.)*'/g, "''")
    .replace(/"(?:[^"\\\n]|\\.)*"/g, '""')
    .replace(/`(?:[^`\\]|\\.)*`/g, '``');
}

describe('no presentation component makes an authorization decision (FR-SURF-004)', () => {
  it('finds the presentation projects it is meant to be scanning', () => {
    assert.ok(
      presentationSources.length > 0,
      'scanned no presentation source — the scan would pass vacuously',
    );
  });

  it('declares no authorization API in a presentation project', () => {
    // Names that assert a decision rather than a display preference.
    const decisionNames =
      /\b(?:is|can|has|check|assert|require|enforce)(?:User)?(?:Authori[sz]ed|Authori[sz]e|Permission|Permitted|Allowed|AccessTo|Entitled)\b/i;

    const offenders = presentationSources.filter((file) => decisionNames.test(code(file.text)));

    assert.deepEqual(
      offenders.map((file) => file.relativePath),
      [],
      'A presentation project declared an authorization decision. Role checks in the client are ' +
        'presentation only and are re-decided server-side (FR-SURF-004).',
    );
  });

  it('evaluates roles only through the single presentation-only helper', () => {
    const offenders = presentationSources.filter((file) => {
      const source = code(file.text);
      // Comparing, sorting or ranking a role is a defect on every stack (contracts/staff-api.md).
      return (
        /\broles?\s*\.\s*(?:sort|indexOf|findIndex)\s*\(/.test(source) ||
        /\broles?\s*[<>]=?\s*/.test(source) ||
        /\bRoleRank\b|\broleLevel\b|\broleWeight\b/i.test(source)
      );
    });

    assert.deepEqual(
      offenders.map((file) => file.relativePath),
      [],
      'Roles are independent capabilities with no hierarchy. Any implementation that sorts, ' +
        'ranks or compares roles is a defect (contracts/staff-api.md §Role model).',
    );
  });

  it('never derives a tenant in client code', () => {
    // Tenant is never a parameter and never a client concern (contracts/README.md rule 1).
    const offenders = presentationSources.filter((file) =>
      /\b(?:setTenant|currentTenant|resolveTenant|tenantFromToken|switchTenant)\b/.test(
        code(file.text),
      ),
    );

    assert.deepEqual(
      offenders.map((file) => file.relativePath),
      [],
      'Organisation is derived at the gateway and is never a client concern (FR-SURF-005).',
    );
  });

  it('parses no token in client code', () => {
    const offenders = allSources.filter((file) =>
      /\b(?:jwtDecode|jwt_decode|decodeJwt|parseJwt)\b/.test(code(file.text)),
    );

    assert.deepEqual(
      offenders.map((file) => file.relativePath),
      [],
      'No client parses a token. A client that reads a claim is one step from deciding with it.',
    );
  });

  it('confines role evaluation to role-visibility.ts, which says what it is', () => {
    const text = readFileSync(ROLE_VISIBILITY_MODULE, 'utf8');
    assert.match(
      text,
      /backend authorization remains authoritative/i,
      'The single role-gating helper must state that the backend remains authoritative.',
    );
    assert.match(
      text,
      /not a security boundary/i,
      'The single role-gating helper must state that a route guard is not a security boundary.',
    );
  });
});

describe('no security bypass API anywhere in the workspace (FE-NG-10)', () => {
  it('calls no bypassSecurityTrust* API', () => {
    const offenders = allSources.filter((file) =>
      /bypassSecurityTrust\w*\s*\(/.test(code(file.text)),
    );

    assert.deepEqual(
      offenders.map((file) => file.relativePath),
      [],
      'bypassSecurityTrust* defeats Angular sanitization. Render the value as text, or model the ' +
        'markup as data (FE-NG-10, .claude/rules/23-angular.md).',
    );
  });

  it('binds no [innerHTML] in any template', () => {
    const templates = PRESENTATION_PROJECTS.flatMap((project) =>
      collectHtml(path.join(projectsRoot, project)),
    );
    const inline = allSources.filter((file) => /\[innerHTML\]/.test(code(file.text)));
    const offenders = [...templates.filter((file) => /\[innerHTML\]/.test(file.text)), ...inline];

    assert.deepEqual(
      offenders.map((file) => file.relativePath),
      [],
      'Agent-authored content is untrusted by construction and renders as text, never as HTML.',
    );
  });
});

describe('no secret in browser code (FE-SH-2)', () => {
  it('assigns no credential-shaped literal', () => {
    const credential =
      /\b(?:clientSecret|client_secret|apiKey|api_key|connectionString|accountKey|sasToken|privateKey)\b\s*[:=]\s*(?:'|"|`)[^'"`\n]{8,}/i;

    const offenders = allSources.filter((file) => credential.test(file.text));

    assert.deepEqual(
      offenders.map((file) => file.relativePath),
      [],
      'No credential in source code. A browser cannot keep a secret — anything shipped to the ' +
        'page is readable by whoever loads it (FE-SH-2, .claude/rules/22-web-typescript.md).',
    );
  });
});

function collectHtml(root: string): readonly SourceFile[] {
  const files: SourceFile[] = [];

  const walk = (directory: string): void => {
    for (const entry of readdirSync(directory)) {
      if (entry === 'node_modules' || entry === 'dist' || entry.startsWith('.')) {
        continue;
      }
      const absolutePath = path.join(directory, entry);
      if (statSync(absolutePath).isDirectory()) {
        walk(absolutePath);
      } else if (entry.endsWith('.html')) {
        files.push({
          absolutePath,
          relativePath: path.relative(workspaceRoot, absolutePath).replace(/\\/g, '/'),
          text: readFileSync(absolutePath, 'utf8'),
        });
      }
    }
  };

  walk(root);
  return files;
}
