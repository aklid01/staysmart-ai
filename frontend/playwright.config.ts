import { defineConfig } from '@playwright/test'

const ROOT = '..'

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: 0,
  outputDir: `${ROOT}/artifacts/e2e_ui/test-results`,
  use: {
    baseURL: 'http://localhost:5173/',
    viewport: { width: 1280, height: 720 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'uv run python scripts/e2e_backend.py',
      cwd: `${ROOT}`,
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:5173/',
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
  reporter: [['list'], ['json', { outputFile: `${ROOT}/artifacts/e2e_ui/results.json` }]],
})
