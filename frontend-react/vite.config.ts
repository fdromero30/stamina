import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
        secure: false,
        headers: {
          Origin: "http://localhost:8080",
          Referer: "http://localhost:8080/"
        },
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/trading-core": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/trading-core/, ""),
      },
    },
  },
  test: {
    globals: true,
    environment: "node",
  },
});