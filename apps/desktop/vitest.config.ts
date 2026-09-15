import { defineConfig } from 'vitest/config';

// The security suite asserts exported configuration, so it runs in plain Node with no display.
// A security control that can only be proven with a real window is a control CI will skip.
export default defineConfig({
  test: {
    include: ['tests/**/*.spec.ts'],
    environment: 'node',
  },
});
