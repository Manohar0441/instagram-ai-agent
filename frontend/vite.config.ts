import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // The backend's CORS_ALLOWED_ORIGINS defaults to http://localhost:3000,
    // and allow_credentials=True means "*" is never usable there. strictPort
    // makes a port collision fail loudly instead of silently moving to 3001,
    // where every request would fail CORS in a way that reads like an auth bug.
    port: 3000,
    strictPort: true,
  },
});
