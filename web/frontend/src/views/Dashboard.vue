<template>
  <div v-loading="loading">
    <el-row :gutter="16">
      <el-col :span="6" v-for="card in statCards" :key="card.label">
        <el-card class="stat">
          <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="card">
      <template #header>
        <div class="card-header">
          <span>最近变更(裁决生效)</span>
          <el-button type="primary" link @click="$router.push('/devices')">
            查看全部资产
          </el-button>
        </div>
      </template>
      <el-table
        ref="tableRef"
        :data="stats?.recent_changes || []"
        border
        @row-click="toggleExpand"
      >
        <el-table-column type="expand" width="40">
          <template #default="{ row }">
            <DiffDetail :diff="row.diff" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" min-width="170">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="设备" width="100">
          <template #default="{ row }">
            <router-link :to="`/devices/${row.device_id}`" class="link">
              #{{ row.device_id }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column label="变更内容" min-width="200">
          <template #default="{ row }">{{ digest(row) }}</template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="120">
          <template #default="{ row }">{{ row.source || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, TableInstance } from 'element-plus'
import { api, DashboardOut, HistoryRow } from '../api'
import DiffDetail from '../components/DiffDetail.vue'

const stats = ref<DashboardOut | null>(null)
const loading = ref(false)
const tableRef = ref<TableInstance>()

// 点击行任意位置展开/收起明细(设备列的链接点击除外)
function toggleExpand(row: HistoryRow, _column: unknown, event: Event) {
  if ((event.target as HTMLElement).closest('a')) return
  tableRef.value?.toggleRowExpansion(row)
}

// 变更内容紧凑概览:改了哪些字段/网卡,完整明细在展开行
function digest(row: HistoryRow): string {
  const diff = row.diff as
    | { fields?: unknown[]; nics?: { name: string }[] }
    | null
  if (!diff) return '-'
  const parts: string[] = []
  const nf = diff.fields?.length ?? 0
  const nics = diff.nics ?? []
  if (nf) parts.push(`修改 ${nf} 个字段`)
  if (nics.length)
    parts.push(`改动网卡 ${nics.map((n) => n.name).join('、')}`)
  return parts.length ? parts.join(', ') : '-'
}

const statCards = computed(() => [
  { label: '资产总数', value: stats.value?.total_devices ?? '-', color: '#409eff' },
  { label: '活跃', value: stats.value?.active ?? '-', color: '#67c23a' },
  {
    label: '疑似下线',
    value: stats.value?.suspected_offline ?? '-',
    color: '#e6a23c',
  },
  { label: '待裁决', value: stats.value?.pending_changes ?? '-', color: '#f56c6c' },
])

function fmt(ts: string | null): string {
  if (!ts) return '-'
  const utc = /[Zz]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : ts + 'Z'
  return new Date(utc).toLocaleString()
}

onMounted(async () => {
  loading.value = true
  try {
    stats.value = await api.dashboard()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.stat {
  text-align: center;
}
.stat-value {
  font-size: 32px;
  font-weight: bold;
}
.stat-label {
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
.card {
  margin-top: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
:deep(.el-table__row) {
  cursor: pointer;
}
</style>
