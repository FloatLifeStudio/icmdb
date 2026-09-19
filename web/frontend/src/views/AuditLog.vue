<template>
  <div>
    <el-card class="card" v-loading="loading">
      <template #header>
        <div class="header">
          <span>操作日志</span>
          <el-input
            v-model="usernameFilter"
            placeholder="按操作人过滤"
            clearable
            style="width: 200px"
            @input="load"
          />
        </div>
      </template>
      <el-table :data="logs" border>
        <el-table-column resizable prop="created_at" label="时间" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column resizable prop="username" label="操作人" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.username || '-' }}</template>
        </el-table-column>
        <el-table-column resizable prop="action" label="操作" min-width="120" show-overflow-tooltip/>
        <el-table-column resizable prop="detail" label="详情" min-width="300" show-overflow-tooltip>
          <template #default="{ row }">{{ row.detail || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, AuditLogRow } from '../api'

const logs = ref<AuditLogRow[]>([])
const loading = ref(false)
const usernameFilter = ref('')

let timer: ReturnType<typeof setTimeout> | undefined
function load() {
  // 输入防抖,避免每敲一个字符发一次请求
  clearTimeout(timer)
  timer = setTimeout(fetchLogs, 300)
}

function fmt(ts: string): string {
  const utc = /[Zz]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : ts + 'Z'
  return new Date(utc).toLocaleString()
}

async function fetchLogs() {
  loading.value = true
  try {
    const res = await api.listAuditLogs(usernameFilter.value.trim())
    logs.value = res.items
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(fetchLogs)
</script>

<style scoped>
.card {
  margin-top: 16px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
