// @ts-check
const eslint = require('@eslint/js');
const tseslint = require('typescript-eslint');
const angular = require('angular-eslint');

/**
 * Library boundaries (plan §Dependency direction):
 *
 *   apps → customer-features | staff-features → platform-core → design-system
 *
 * Anything not drawn there is prohibited. These rules are how that survives contact with a
 * deadline — a violating import is a lint error, not a review comment someone might miss.
 */
const WORKSPACE_LIBS = ['customer-features', 'staff-features', 'platform-core', 'design-system'];
const APPS = ['customer-portal', 'staff-portal', 'desktop-renderer'];

/** Build a no-restricted-imports rule from a list of forbidden package names. */
const forbid = (names, why) => [
  'error',
  {
    patterns: names.map((name) => ({
      group: [name, `${name}/*`],
      message: why,
    })),
  },
];

module.exports = tseslint.config(
  {
    ignores: ['dist/**', 'node_modules/**', '.angular/**', 'coverage/**'],
  },

  // ---------------------------------------------------------------- TypeScript
  {
    files: ['**/*.ts'],
    extends: [
      eslint.configs.recommended,
      ...tseslint.configs.recommended,
      ...tseslint.configs.stylistic,
      ...angular.configs.tsRecommended,
    ],
    processor: angular.processInlineTemplates,
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/explicit-module-boundary-types': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'no-console': ['error', { allow: ['warn', 'error'] }],
      eqeqeq: ['error', 'always'],

      // Constitution Principle VII: no secret in browser code, and sanitization is not optional.
      'no-restricted-properties': [
        'error',
        {
          object: 'DomSanitizer',
          message:
            'bypassSecurityTrust* defeats Angular sanitization. Requires specific justification, ' +
            'review and constraint (constitution Principle VII).',
        },
      ],
    },
  },

  // ---------------------------------------------------------------- Templates
  {
    files: ['**/*.html'],
    extends: [...angular.configs.templateRecommended, ...angular.configs.templateAccessibility],
    rules: {
      // Accessibility is mandatory on all three surfaces — WCAG 2.2 AA, no best-effort surface
      // (spec FR-SURF-010). Template a11y findings are errors, not warnings.
      '@angular-eslint/template/elements-content': 'error',
      '@angular-eslint/template/label-has-associated-control': 'error',
      '@angular-eslint/template/no-autofocus': 'error',
    },
  },

  // ------------------------------------------------- design-system: the floor
  {
    files: ['projects/design-system/**/*.ts'],
    rules: {
      'no-restricted-imports': forbid(
        [...WORKSPACE_LIBS.filter((l) => l !== 'design-system'), ...APPS],
        'design-system is the dependency floor: accessible primitives only, no business logic ' +
          'and no dependency on any other workspace project (plan §Dependency direction).',
      ),
    },
  },

  // --------------------------------- platform-core: may reach design-system only
  {
    files: ['projects/platform-core/**/*.ts'],
    rules: {
      'no-restricted-imports': forbid(
        ['customer-features', 'staff-features', ...APPS],
        'platform-core holds shared infrastructure (auth, API clients, realtime, correlation). ' +
          'It may depend on design-system and nothing else in the workspace.',
      ),
    },
  },

  // ------------------- customer-features: never staff-features, never an app
  {
    files: ['projects/customer-features/**/*.ts'],
    rules: {
      'no-restricted-imports': forbid(
        ['staff-features', ...APPS],
        'customer-features is shared by the customer portal AND the desktop renderer. Importing ' +
          'staff-features would ship staff code to a customer client, and importing an ' +
          'application would invert the dependency direction.',
      ),
    },
  },

  // ------------------- staff-features: never customer-features, never an app
  {
    files: ['projects/staff-features/**/*.ts'],
    rules: {
      'no-restricted-imports': forbid(
        ['customer-features', ...APPS],
        'staff-features must not depend on customer-features or on any application ' +
          '(plan §Dependency direction).',
      ),
    },
  },

  // ---------------------------------- applications: never each other
  ...APPS.map((app) => ({
    files: [`projects/${app}/**/*.ts`],
    rules: {
      'no-restricted-imports': forbid(
        APPS.filter((other) => other !== app),
        'An application must not import another application. Share through a library instead.',
      ),
    },
  })),

  // -------------- staff-portal may not import customer chat features
  {
    files: ['projects/staff-portal/**/*.ts'],
    rules: {
      'no-restricted-imports': forbid(
        ['customer-features', ...APPS.filter((a) => a !== 'staff-portal')],
        'The staff portal MUST NOT provide any facility to start a chat session (spec ' +
          'FR-SURF-006). Importing customer-features is how that rule gets broken by accident.',
      ),
    },
  },
);
