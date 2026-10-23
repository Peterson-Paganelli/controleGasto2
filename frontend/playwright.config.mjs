import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:55173',
    browserName: 'chromium',
    channel: process.env.E2E_BROWSER_CHANNEL || undefined,
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'celular', use: { viewport: { width: 360, height: 800 } } },
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
  ],
})
