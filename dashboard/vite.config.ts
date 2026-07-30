import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

const dashboardRoot = fileURLToPath(new URL(".", import.meta.url));
const backendTarget =
  process.env.MODELPORT_BACKEND_DEV_URL ?? "http://127.0.0.1:13243";

export default defineConfig({
  base: "/dashboard/",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(dashboardRoot, "src"),
    },
  },
  build: {
    outDir: "../backend/app/static/dashboard",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/admin": { target: backendTarget, changeOrigin: true, secure: false },
      "/analytics": { target: backendTarget, changeOrigin: true, secure: false },
      "/dashboard/auth": {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    restoreMocks: true,
  },
});
