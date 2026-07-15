import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // SPEC-PF: stable vendor chunks — long-term caching + parallel
        // fetch. recharts ships inside the lazy instruments chunk, so it
        // stays off the initial path entirely.
        manualChunks: {
          'vendor-react': ['react', 'react-dom'],
          'vendor-net': ['axios'],
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // يوجه طلبات الـ API للخادم الخلفي
        changeOrigin: true,
      }
    }
  }
})
