import { defineConfig } from '@playwright/test';

const baseURL = process.env.SPEC12_E2E_FRONTEND_BASE_URL || 'http://127.0.0.1:5173';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 180000,
  use: {
    baseURL,
    headless: true,
  },
});
