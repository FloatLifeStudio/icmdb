<template>
  <div v-loading="loading">
    <el-page-header :title="'返回列表'" @back="$router.back()">
      <template #content>
        <span class="hostname">{{ device?.hostname }}</span>
        <el-tag
          v-if="device"
          :type="device.status === 'active' ? 'success' : 'warning'"
          class="status-tag"
        >
          {{ device.status === 'active' ? '活跃' : '疑似下线' }}
        </el-tag>
      </template>
    </el-page-header>

    <el-card v-if="device" class="card">
      <template #header>基本信息</template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="Hostname">
          {{ device.hostname }}
        </el-descriptions-item>
        <el-descriptions-item label="序列号">
          {{ device.serial_number || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="管理 MAC">
          {{ device.mgmt_mac || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="管理 IP">
          {{ device.mgmt_ip || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="子网前缀">
          {{ device.mgmt_prefix_length ?? '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="上次推送">
          {{ fmt(device.last_pushed_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ fmt(device.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">
          {{ fmt(device.updated_at) }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="device" class="card">
      <template #header>网卡与 IP</template>
      <el-table :data="device.nics" border>
        <el-table-column prop="name" label="网卡" width="120" />
        <el-table-column prop="mac" label="MAC" min-width="160" />
        <el-table-column label="IP 列表" min-width="280">
          <template #default="{ row }">
            <el-tag
              v-for="ip in row.ips"
              :key="ip.id"
              class="ip-tag"
              type="info"
            >
              {{ ip.ip }}{{ ip.prefix_length ? '/' + ip.prefix_length : '' }}
            </el-tag>
            <span v-if="!row.ips.length">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="card">
      <template #header>变更历史(裁决生效的改动)</template>
      <el-table :data="history" border v-loading="historyLoading">
        <el-table-column prop="created_at" label="时间" min-width="170">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="summary" label="变更内容" min-width="300" />
        <el-table-column prop="source" label="来源" width="120">
          <template #default="{ row }">{{ row.source || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, DeviceOut } from '../api'

interface HistoryRow {
  id: number
  device_id: number
  summary: string
  source: string | null
  created_at: string
}

const route = useRoute()
const deviceId = Number(route.params.id)
const device = ref<DeviceOut | null>(null)
const history = ref<HistoryRow[]>([])
const loading = ref(false)
const historyLoading = ref(false)

function fmt(ts: string | null): string {
  return ts ? new Date(ts).toLocaleString() : '-'
}

async function load() {
  loading.value = true
  try {
    device.value = await api.getDevice(deviceId)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    // 历史按设备过滤:全量拉取后前端过滤(含已删设备的历史)
    const res = await fetch('/api/v1/change-history?device_id=' + deviceId)
    if (res.ok) {
      history.value = (await res.json()).items
    }
  } finally {
    historyLoading.value = false
  }
}

onMounted(async () => {
  await load()
  await loadHistory()
})
</script>

<style scoped>
.hostname {
  font-size: 18px;
  font-weight: bold;
  margin-right: 12px;
}
.status-tag {
  vertical-align: middle;
}
.card {
  margin-top: 16px;
}
.ip-tag {
  margin-right: 8px;
}
</style>
