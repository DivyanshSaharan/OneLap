import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  outputDir: '../test-results',
  workers: 1,
  timeout: 30000,
  use: {
    baseURL: 'http://127.0.0.1:4175',
    headless: true,
    serviceWorkers: 'allow',
    screenshot: 'only-on-failure',
    viewport: { width: 390, height: 844 },
    ...(process.env.ONELAP_TEST_BROWSER === 'msedge'
      ? { channel: 'msedge' }
      : {}),
  },
  webServer: {
    command: 'npm run preview -- --port 4175',
    cwd: '..',
    url: 'http://127.0.0.1:4175',
    reuseExistingServer: false,
    timeout: 30000,
  },
})
