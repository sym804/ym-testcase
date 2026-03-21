/// <reference types="vitest" />
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/** Vite plugin: 모든 응답에 charset=utf-8 헤더 추가 */
function charsetPlugin(): Plugin {
  return {
    name: "charset-utf8",
    configureServer(server) {
      server.middlewares.use((_req, res, next) => {
        const orig = res.setHeader.bind(res);
        res.setHeader = (name: string, value: string | number | readonly string[]) => {
          if (
            name.toLowerCase() === "content-type" &&
            typeof value === "string" &&
            !value.includes("charset")
          ) {
            value = `${value}; charset=utf-8`;
          }
          return orig(name, value);
        };
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
