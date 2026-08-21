/** 静态预览版的构建配置(`make demo`)。
 *
 * 与正式构建的区别:入口是 demo/,资源全部内联(assetsInlineLimit 拉到无限大),
 * 于是产物只有一个 HTML + 一个 JS + 一个 CSS,可以再拼成单文件丢到任何静态托管上。
 */

import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: './',
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    outDir: 'dist-demo',
    emptyOutDir: true,
    // 字体等资源全部转成 data URI,便于打成单文件
    assetsInlineLimit: 1024 * 1024 * 64,
    rollupOptions: { input: 'demo/index.html' },
  },
})
