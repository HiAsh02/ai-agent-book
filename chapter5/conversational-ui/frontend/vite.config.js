import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite dev server enables HMR (Hot Module Replacement) by default.
// When the Agent modifies source code under src/, the browser can instantly see UI changes without a full page refresh.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The backend FastAPI runs on port 8000, and the frontend proxies /api requests to it to avoid CORS.
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
