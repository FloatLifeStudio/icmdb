import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// dev 时 /api 代理到后端 8080;构建产物输出到 src/cmdb/static,由 FastAPI 托管
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
    },
  },
  build: {
    outDir: '../../src/cmdb/static',
    emptyOutDir: true,
  },
})
