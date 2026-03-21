/// <reference types="vitest" />
import { type Plugin } from "vite";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/** Vite plugin: 모든 응답에 charset=utf-8 헤더 추가 (메모리 누수 방지) */
function charsetPlugin(): Plugin {
  return {
    name: "charset-utf8",
    configureServer(server) {
      server.middlewares.use((_req, res, next) => {
        // setHeader를 래핑하지 않고 writeHead를 한 번만 패치
        const origWriteHead = res.writeHead.bind(res);
        res.writeHead = function (
          statusCode: number,
          ...args: unknown[]
        ) {
          const ct = res.getHeader("content-type");
          if (typeof ct === "string" && !ct.includes("charset")) {
            res.setHeader("content-type", `${ct}; charset=utf-8`);
          }
          return origWriteHead(statusCode, ...args);
        } as typeof res.writeHead;
        next();
      });
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), charsetPlugin()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8008",
        changeOrigin: true,
      },
    },
    watch: {
      ignored: ["**/node_modules/**", "**/dist/**", "**/.git/**"],
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: false,
    exclude: ["e2e/**", "node_modules/**"],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom", "react-router-dom"],
          grid: ["ag-grid-community", "ag-grid-react"],
        },
      },
    },
  },
});
