import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// the Python server holds the derivations; in development the viewer reaches it through this proxy
export default defineConfig({
  plugins: [react()],
  server: { port: 5183, proxy: { "/api": "http://127.0.0.1:8765" } },
  build: { chunkSizeWarningLimit: 2000 },
});
