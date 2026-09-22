import tailwindcss from "@tailwindcss/vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import tsConfigPaths from "vite-tsconfig-paths";

// The Python calculation engine (api.py) runs as a separate process.
// Requests to /api are proxied to it so the browser sees a single origin
// and no CORS or hardcoded host is needed in the UI code.
const API_TARGET = process.env.API_URL ?? "http://127.0.0.1:8000";

const apiProxy = {
  "/api": {
    target: API_TARGET,
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [
    // Resolves the "@/..." alias from tsconfig.json.
    tsConfigPaths(),
    tailwindcss(),
    // tanstackStart must come before the React plugin.
    tanstackStart({
      // Route TanStack Start's server entry through src/server.ts,
      // which renders a readable page if SSR throws.
      server: { entry: "server" },
    }),
    viteReact(),
  ],
  server: {
    port: 5173,
    proxy: apiProxy,
  },
  preview: {
    port: 4173,
    proxy: apiProxy,
  },
});
