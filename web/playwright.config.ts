import { defineConfig } from "@playwright/test";

// Backend: fixture API on :8000 (INVENTED text, test only). Frontend: production build on :3100.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:3100",
    launchOptions: { executablePath: process.env.CHROMIUM_PATH },
  },
  webServer: [
    {
      command: "../.venv/bin/python ../scripts/serve_fixture.py 8000",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: false,
    },
    {
      command: "npm run start -- -p 3100",
      url: "http://127.0.0.1:3100",
      reuseExistingServer: false,
      env: { API_URL: "http://127.0.0.1:8000" },
    },
  ],
});
