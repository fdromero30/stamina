import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  define: {
    "import.meta.env.VITE_USERS_CONFIG_API_URL": JSON.stringify("/api"),
    "import.meta.env.VITE_TRADING_CORE_URL": JSON.stringify("/trading-core"),
  },
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
    },
  },
});