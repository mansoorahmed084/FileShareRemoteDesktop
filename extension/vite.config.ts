import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";
import { copyFileSync, mkdirSync, existsSync } from "fs";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "copy-manifest-and-icons",
      closeBundle() {
        copyFileSync(
          resolve(__dirname, "public/manifest.json"),
          resolve(__dirname, "dist/manifest.json")
        );
        const iconsDir = resolve(__dirname, "dist/icons");
        if (!existsSync(iconsDir)) mkdirSync(iconsDir, { recursive: true });
        for (const size of [16, 48, 128]) {
          const src = resolve(__dirname, `public/icons/icon${size}.png`);
          if (existsSync(src)) {
            copyFileSync(src, resolve(iconsDir, `icon${size}.png`));
          }
        }
      },
    },
  ],
  resolve: {
    alias: { "@": resolve(__dirname, "src") },
  },
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: resolve(__dirname, "src/popup/index.html"),
        sidepanel: resolve(__dirname, "src/sidepanel/index.html"),
        "service-worker": resolve(__dirname, "src/background/service-worker.ts"),
      },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});
