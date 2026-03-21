import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  retries: 1,
  workers: 1,
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
  ],
  webServer: [
    {
      command: "cd ../backend && python -m uvicorn main:app --port 8008",
      port: 8008,
      timeout: 15000,
      reuseExistingServer: true,
    },
    {
      command: "npm run dev",
      port: 5173,
      timeout: 15000,
      reuseExistingServer: true,
    },
  ],
});
