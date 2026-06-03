import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// During `npm run dev`, API calls are proxied to the FastAPI backend so the
// Vue dev server (5173) and the API (8000) work together without CORS hassle.
// `npm run build` emits to web/dist, which the backend serves at "/".
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
