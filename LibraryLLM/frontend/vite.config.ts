import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const coreApiTarget =
  process.env.LUMINAR_CORE_API_TARGET ||
  'http://127.0.0.1:8002'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  server: {
    host: '127.0.0.1',
    port: 5173,

    proxy: {

      // ========================================================
      // CORE / AUTH / BOOKS / ISSUES / RESERVATIONS
      // ========================================================

      '/api': {
        target: coreApiTarget,
        changeOrigin: true,
        rewrite: (path) =>
          path.replace(/^\/api/, ''),
      },

      // ========================================================
      // SEARCH
      // ========================================================

      '/search-api': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true,
        rewrite: (path) =>
          path.replace(/^\/search-api/, ''),
      },

      // ========================================================
      // RECOMMENDATION
      // ========================================================

      '/recommendation-api': {
        target: 'http://127.0.0.1:8004',
        changeOrigin: true,
        rewrite: (path) =>
          path.replace(/^\/recommendation-api/, ''),
      },

      // ========================================================
      // RAG
      // ========================================================

      '/rag-api': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
        rewrite: (path) =>
          path.replace(/^\/rag-api/, ''),
      },
    },
  },
})
