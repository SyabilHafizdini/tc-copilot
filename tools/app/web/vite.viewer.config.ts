import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

// The standalone viewer: one self-contained HTML file with every asset
// inlined. scripts/bake.mjs injects a graph into dist/viewer.html to produce
// a shareable page, and wiki_graph.py depends on that file existing.
//
// NOTE: `vite build` empties outDir, so nothing that must survive a build may
// live in dist/ — build-manifest.json sits at the workspace root for that
// reason.
export default defineConfig({
  plugins: [react(), tailwindcss(), viteSingleFile()],
  build: { outDir: 'dist' },
})
