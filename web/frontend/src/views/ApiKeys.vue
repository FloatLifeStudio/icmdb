<template>
  <div>
    <el-card class="card" v-loading="loading">
      <template #header>
        <div class="header">
          <span>API 密钥</span>
          <el-button type="primary" size="small" @click="openCreate">新建密钥</el-button>
        </div>
      </template>
      <el-table :data="keys" border>
        <el-table-column resizable prop="name" label="名称" min-width="140" show-overflow-tooltip/>
        <el-table-column resizable prop="key" label="密钥" min-width="320">
          <template #default="{ row }">
            <span class="mono">{{ row.key }}</span>
            <el-button link type="primary" size="small" @click="copyKey(row)">复制</el-button>
          </template>
        </el-table-column>
        <el-table-column resizable prop="created_at" label="创建时间" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column resizable prop="last_used_at" label="最后使用" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.last_used_at ? fmt(row.last_used_at) : '从未使用' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="danger" size="small" @click="revoke(row)">吊销</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="desc">
        密钥用于采集器推送与只读 API 访问(请求头 X-API-Key),在系统设置中开启"API 密钥"后生效;吊销后使用该密钥的请求立即返回 401
      </div>
    </el-card>

    <el-dialog v-model="createVisible" title="新建密钥" width="400px">
      <el-input
        v-model="newName"
        placeholder="密钥名称,如 iagent-prod"
        maxlength="64"
        @keyup.enter="create"
      />
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, ApiKey } from '../api'

const keys = ref<ApiKey[]>([])
const loading = ref(false)
const createVisible = ref(false)
const newName = ref('')

function fmt(ts: string): string {
  const utc = /[Zz]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : ts + 'Z'
  return new Date(utc).toLocaleString()
}

async function fetchKeys() {
  loading.value = true
  try {
    const res = await api.listApiKeys()
    keys.value = res.items
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  newName.value = ''
  createVisible.value = true
}

async function create() {
  const name = newName.value.trim()
  if (!name) {
    ElMessage.warning('请填写密钥名称')
    return
  }
  try {
    await api.createApiKey(name)
    createVisible.value = false
    ElMessage.success('密钥已创建')
    await fetchKeys()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function copyKey(row: ApiKey) {
  const ok = await copyText(row.key)
  if (ok) {
    ElMessage.success('已复制')
  } else {
    ElMessage.error('复制失败')
  }
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // HTTP (non-localhost) blocks the clipboard API, fall back to execCommand
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    try {
      return document.execCommand('copy')
    } catch {
      return false
    } finally {
      document.body.removeChild(ta)
    }
  }
}

async function revoke(row: ApiKey) {
  try {
    await ElMessageBox.confirm(`确定吊销密钥"${row.name}"?吊销后立即失效`, '吊销密钥', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await api.deleteApiKey(row.id)
    ElMessage.success('密钥已吊销')
    await fetchKeys()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

onMounted(fetchKeys)
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
.mono {
  font-family: monospace;
  font-size: 13px;
  margin-right: 8px;
}
.desc {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin-top: 12px;
}
</style>
