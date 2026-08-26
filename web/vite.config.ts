import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 后端地址走 dev 代理:前端一律用相对路径("/api/..."),
// 于是开发环境同源、无预检、SSE 不受 CORS 影响;换后端地址只改这里。
const API_TARGET = process.env.VITE_API_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    // 5173 被占时:VITE_PORT=5273 npm run dev(或 make dev VITE_PORT=5273)
    port: Number(process.env.VITE_PORT ?? 5173),
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
      '/healthz': { target: API_TARGET, changeOrigin: true },
    },
  },
})
