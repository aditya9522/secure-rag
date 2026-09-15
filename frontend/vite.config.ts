import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev
export default defineConfig({
  // Recharts is imported by lazy-loaded admin/overview modules. Force a fresh
  // optimized dependency graph on each dev-server start so stale browser
  // requests cannot keep serving an invalidated dependency chunk.
  optimizeDeps: {
    force: true,
    include: ['recharts'],
  },
  plugins: [
    react(),
    tailwindcss(),
  ],
})
