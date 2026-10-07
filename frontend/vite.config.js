import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react()],
    server: {
      host: true,
      port: 3000,
      watch: {
        usePolling: true,
      },
      proxy: {
        '/api': {
          target: env.VITE_BACKEND_URL || 'http://backend:8000',
          changeOrigin: true,
        },
      },
    },
  }
})