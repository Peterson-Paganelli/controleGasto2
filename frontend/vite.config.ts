import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const target = loadEnv(mode, '.', 'API_').API_URL || 'http://localhost:8000'
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': { target, changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, '') },
        '/health': target,
      },
    },
  }
})
