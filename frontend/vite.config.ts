/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // With VITE_API_URL unset, /api/* goes to a local `uvicorn api.main:app`.
    proxy: { "/api": "http://localhost:8000" },
  },
  build: {
    rollupOptions: {
      output: {
        // maplibre-gl alone is ~800 kB; keep it out of the app chunk so app
        // changes don't bust its cache.
        manualChunks: { maplibre: ["maplibre-gl"], charts: ["recharts"] },
      },
    },
    chunkSizeWarningLimit: 1200,
  },
  test: {
    environment: "node",
  },
});
