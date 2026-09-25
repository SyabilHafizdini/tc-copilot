import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

// The operator app, built single-file for the same reason as the viewer: one
// committed artifact with one hash, instead of a directory of content-hashed
// assets churning in git on every rebuild.
//
// outDir is dist-app/, NOT dist/ -- `vite build` empties its outDir, so
// sharing one directory would make each build delete the other's output.
export default defineConfig({
  plugins: [react(), tailwindcss(), viteSingleFile()],
  build: { outDir: 'dist-app', rollupOptions: { input: 'app.html' } },
})
