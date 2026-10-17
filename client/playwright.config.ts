import { defineConfig, devices } from "@playwright/test";

// Starts the API (scripted fake LLM, throwaway database) and the client, then runs the three
// personas at desktop and phone widths. No key and no network needed.
const SERVER_DIR = "../server";
const TMP = process.env.E2E_TMP ?? "/tmp/firststep-e2e";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:3100", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } },
    { name: "phone", use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } } },
  ],
  webServer: [
    {
      command: `rm -rf ${TMP} && mkdir -p ${TMP} && cd ${SERVER_DIR} && LLM_PROVIDER=fake DB_PATH=${TMP}/sandbox.db EVIDENCE_DIR=${TMP}/evidence .venv/bin/python -m uvicorn app.main:app --port 8100`,
      url: "http://127.0.0.1:8100/api/health",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "API_URL=http://127.0.0.1:8100 npx next dev --port 3100",
      url: "http://localhost:3100",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
