// 격리 실행용: 5183(프론트)/8018(백엔드)에 붙고 서버를 띄우거나 재사용하지 않는다. 실제 DB 를 쓰는 8008/5173 과 섞이지 않게 한다
import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e", timeout: 30000, retries: 0, workers: 1,
  use: { baseURL: "http://localhost:5183", headless: true, screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
