import { defineConfig } from "@playwright/test";
const frontendPort = Number(process.env.PLAYWRIGHT_FRONTEND_PORT || 5173);
const backendPort = Number(process.env.PLAYWRIGHT_BACKEND_PORT || 8000);
const qualificationFixture =
  process.env.PLAYWRIGHT_QUALIFICATION_FIXTURE === "1";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  retries: 0,
  timeout: 30000,
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    viewport: { width: 1440, height: 1000 },
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `../backend/.venv/bin/python -m uvicorn ${qualificationFixture ? "browser_qualification:app --app-dir ../backend/tests" : "app.main:app --app-dir ../backend"} --port ${backendPort} --no-access-log`,
      url: `http://127.0.0.1:${backendPort}/api/v1/health`,
      reuseExistingServer: !process.env.CI,
      env: {
        GEMINI_API_KEY: "",
        NVIDIA_API_KEY: "",
        CORS_ORIGINS: JSON.stringify([
          `http://127.0.0.1:${frontendPort}`,
          `http://localhost:${frontendPort}`,
        ]),
      },
    },
    {
      command: `npm run dev -- --port ${frontendPort} --strictPort`,
      url: `http://127.0.0.1:${frontendPort}`,
      reuseExistingServer: !process.env.CI,
      env: { API_PROXY_TARGET: `http://127.0.0.1:${backendPort}` },
    },
  ],
});
