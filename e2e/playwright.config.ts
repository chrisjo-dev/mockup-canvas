import { defineConfig, devices } from '@playwright/test';

// Every test starts its own canvas server on a free port from the fixtures in tests/fixtures.ts,
// so there is no global webServer here.
export default defineConfig({
  testDir: '.',
  testMatch: ['tests/**/*.spec.ts', 'seed.spec.ts'],
  timeout: 60_000,
  expect: { timeout: 8_000 },
  fullyParallel: true,
  workers: process.env.CI ? 2 : 4,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    viewport: { width: 1280, height: 720 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 720 } }, grepInvert: /@mobile/ },
    { name: 'firefox', use: { ...devices['Desktop Firefox'], viewport: { width: 1280, height: 720 } }, grepInvert: /@mobile/ },
    { name: 'webkit', use: { ...devices['Desktop Safari'], viewport: { width: 1280, height: 720 } }, grepInvert: /@mobile/ },
    { name: 'mobile-webkit', use: { ...devices['iPhone 13'] }, grep: /@mobile/ },
  ],
});
