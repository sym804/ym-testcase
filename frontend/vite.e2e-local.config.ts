// 격리 실행용: /api 를 임시 DB 백엔드(8018)로 보낸다. playwright.e2e-local.config.ts 와 짝
import base from "./vite.config";
const cfg = { ...base, server: { ...base.server, proxy: { "/api": { target: "http://localhost:8018", changeOrigin: true } } } };
export default cfg;
