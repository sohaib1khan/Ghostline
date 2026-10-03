import fs from "node:fs";
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Inside Compose, VITE_API_PROXY points at the backend service.
// A local `npm run dev` falls back to the backend on this machine.
const apiProxy = process.env.VITE_API_PROXY || "http://127.0.0.1:8000";

const PYODIDE_FILES = [
  "pyodide.mjs",
  "pyodide.asm.mjs",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide-lock.json",
];

const THEME = "#1b1f23";

// DECISION: only these GETs are kept for offline reading. A live response wins.
// Answer checks, sign-in, and admin writes are never stored. An inline service
// worker registration would violate script-src 'self', so the app registers it.
const READ_CACHE = {
  handler: "NetworkFirst",
  options: {
    cacheName: "ghostline-read",
    networkTimeoutSeconds: 4,
    expiration: { maxEntries: 80, maxAgeSeconds: 60 * 60 * 24 * 14 },
    cacheableResponse: { statuses: [200] },
  },
};

function readCache(urlPattern) {
  return { urlPattern, ...READ_CACHE };
}

function contentType(name) {
  if (name.endsWith(".wasm")) {
    return "application/wasm";
  }
  if (name.endsWith(".json")) {
    return "application/json";
  }
  if (name.endsWith(".zip")) {
    return "application/zip";
  }
  return "text/javascript";
}

function pyodideStatic() {
  const root = path.resolve("node_modules/pyodide");
  return {
    name: "pyodide-static",
    configureServer(server) {
      server.middlewares.use("/pyodide", (request, response, next) => {
        const name = decodeURIComponent((request.url || "/").split("?")[0].replace(/^\//, ""));
        if (!PYODIDE_FILES.includes(name)) {
          next();
          return;
        }
        response.setHeader("Content-Type", contentType(name));
        response.setHeader("Access-Control-Allow-Origin", "*");
        fs.createReadStream(path.join(root, name)).pipe(response);
      });
    },
    closeBundle() {
      const dest = path.resolve("dist/pyodide");
      fs.mkdirSync(dest, { recursive: true });
      for (const name of PYODIDE_FILES) {
        fs.copyFileSync(path.join(root, name), path.join(dest, name));
      }
    },
  };
}

export default defineConfig({
  plugins: [
    react(),
    pyodideStatic(),
    VitePWA({
      injectRegister: false,
      registerType: "autoUpdate",
      // Generate the worker after Pyodide has been copied into dist.
      integration: { closeBundleOrder: "post" },
      manifest: {
        name: "Ghostline",
        short_name: "Ghostline",
        description: "A calm, typing-first way to learn Bash, Python, Go, JavaScript, SQL, C#, and Java.",
        theme_color: THEME,
        background_color: THEME,
        display: "standalone",
        start_url: "/",
        scope: "/",
        lang: "en",
        icons: [
          {
            src: "icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        skipWaiting: true,
        clientsClaim: true,
        cleanupOutdatedCaches: true,
        navigateFallback: "index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/pyodide\//, /^\/sandbox\//],
        globPatterns: ["**/*.{js,css,html,svg,png,woff2,wav,webmanifest,wasm,mjs,zip,json}"],
        maximumFileSizeToCacheInBytes: 12 * 1024 * 1024,
        runtimeCaching: [
          readCache(/\/api\/setup\/status$/),
          readCache(/\/api\/me$/),
          readCache(/\/api\/learn\/dashboard$/),
          readCache(/\/api\/learn\/tracks$/),
          readCache(/\/api\/demo\/tracks$/),
          readCache(/\/api\/learn\/tracks\/[^/]+\/outline$/),
          readCache(/\/api\/(?:learn|demo)\/lessons\/[^/]+$/),
          {
            urlPattern: /\/pyodide\/[^/?]+$/,
            handler: "CacheFirst",
            options: {
              cacheName: "ghostline-pyodide",
              expiration: { maxEntries: 8, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            urlPattern: /\/sounds\/[^/?]+$/,
            handler: "CacheFirst",
            options: {
              cacheName: "ghostline-sounds",
              expiration: { maxEntries: 8, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [200] },
            },
          },
        ],
      },
    }),
  ],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": apiProxy,
    },
  },
});
