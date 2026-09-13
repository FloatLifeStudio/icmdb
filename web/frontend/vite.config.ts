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
    // Element Plus 等第三方库拆分为独立 vendor chunk,避免主包过大
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'element-plus', '@element-plus/icons-vue'],
        },
      },
    },
  },
})
