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
      <template #header>
        <div class="card-header">
          <span>基本信息</span>
          <el-button size="small" @click="openTagEdit">编辑标签</el-button>
        </div>
      </template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="Hostname">
          {{ device.hostname }}
        </el-descriptions-item>
        <el-descriptions-item label="序列号">
          {{ device.serial_number || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="OS 类型">
          {{ device.os_type || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="OS 版本">
          {{ device.os_version || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="内核">
          {{ device.kernel || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="采集器版本">
          {{ device.agent_version || '-' }}
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
        <el-descriptions-item label="标签">
          <el-tag v-for="t in device.tags" :key="t" size="small" class="tag">
            {{ t }}
          </el-tag>
          <span v-if="!device.tags.length">-</span>
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
              class="tag"
              type="info"
            >
              {{ ip.ip }}{{ ip.prefix_length ? '/' + ip.prefix_length : '' }}
            </el-tag>
            <span v-if="!row.ips.length">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="device && device.memory.length" class="card">
      <template #header>内存</template>
      <el-table :data="device.memory" border>
        <el-table-column prop="slot" label="槽位" width="110" />
        <el-table-column prop="manufacturer" label="厂商" min-width="110">
          <template #default="{ row }">{{ row.manufacturer || '-' }}</template>
        </el-table-column>
        <el-table-column prop="part_number" label="型号" min-width="190">
          <template #default="{ row }">{{ row.part_number || '-' }}</template>
        </el-table-column>
        <el-table-column prop="type" label="代数" width="90">
          <template #default="{ row }">{{ row.type || '-' }}</template>
        </el-table-column>
        <el-table-column label="容量" width="100">
          <template #default="{ row }">
            {{ row.size ? row.size + (row.size_unit ?? '') : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="频率" width="110">
          <template #default="{ row }">{{ row.speed_mts ? row.speed_mts + 'MT/s' : '-' }}</template>
        </el-table-column>
        <el-table-column prop="serial_number" label="SN" min-width="130">
          <template #default="{ row }">{{ row.serial_number || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="device && device.cpus.length" class="card">
      <template #header>CPU</template>
      <el-table :data="device.cpus" border>
        <el-table-column prop="slot" label="槽位" width="110" />
        <el-table-column prop="model" label="型号" min-width="300" />
      </el-table>
    </el-card>

    <el-card v-if="device && device.disks.length" class="card">
      <template #header>硬盘</template>
      <el-table :data="device.disks" border>
        <el-table-column prop="type" label="类型" width="90">
          <template #default="{ row }">{{ row.type || '-' }}</template>
        </el-table-column>
        <el-table-column prop="manufacturer" label="品牌" min-width="110">
          <template #default="{ row }">{{ row.manufacturer || '-' }}</template>
        </el-table-column>
        <el-table-column prop="model" label="型号" min-width="190">
          <template #default="{ row }">{{ row.model || '-' }}</template>
        </el-table-column>
        <el-table-column label="容量" width="110">
          <template #default="{ row }">
            {{ row.size ? row.size + (row.size_unit ?? '') : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="serial_number" label="SN" min-width="130" />
      </el-table>
    </el-card>

    <el-card v-if="device && device.psus.length" class="card">
      <template #header>电源</template>
      <el-table :data="device.psus" border>
        <el-table-column prop="manufacturer" label="品牌" min-width="110">
          <template #default="{ row }">{{ row.manufacturer || '-' }}</template>
        </el-table-column>
        <el-table-column prop="model" label="型号" min-width="190">
          <template #default="{ row }">{{ row.model || '-' }}</template>
        </el-table-column>
        <el-table-column label="最大功率" width="130">
          <template #default="{ row }">
            {{ row.max_power_w ? row.max_power_w + 'W' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="serial_number" label="SN" min-width="130" />
      </el-table>
    </el-card>

    <el-card v-if="device && device.gpus.length" class="card">
      <template #header>GPU</template>
      <el-table :data="device.gpus" border>
        <el-table-column prop="name" label="型号" min-width="200">
          <template #default="{ row }">{{ row.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="显存" width="100">
          <template #default="{ row }">
            {{ row.size ? row.size + (row.size_unit ?? '') : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="driver_version" label="驱动" width="130">
          <template #default="{ row }">{{ row.driver_version || '-' }}</template>
        </el-table-column>
        <el-table-column prop="pcie_id" label="PCIe" width="130">
          <template #default="{ row }">{{ row.pcie_id || '-' }}</template>
        </el-table-column>
        <el-table-column label="SN" min-width="130">
          <template #default="{ row }">{{ row.serial_number || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="card history-card">
      <template #header>变更历史(裁决生效的改动)</template>
      <el-table
        ref="historyTable"
        :data="history"
        border
        v-loading="historyLoading"
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
        <el-table-column label="变更内容" min-width="200">
          <template #default="{ row }">{{ digest(row) }}</template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="120">
          <template #default="{ row }">{{ row.source || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="tagDialogVisible" title="编辑标签" width="400px">
      <el-input
        v-model="tagInput"
        placeholder="多个标签用英文逗号分隔,如:生产,web"
        @keyup.enter="saveTags"
      />
      <template #footer>
        <el-button @click="tagDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTags">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, TableInstance } from 'element-plus'
import { api, DeviceOut, HistoryRow } from '../api'
import DiffDetail from '../components/DiffDetail.vue'

const route = useRoute()
const deviceId = Number(route.params.id)
const device = ref<DeviceOut | null>(null)
const history = ref<HistoryRow[]>([])
const loading = ref(false)
const historyLoading = ref(false)
const tagDialogVisible = ref(false)
const tagInput = ref('')
const historyTable = ref<TableInstance>()

// 点击行任意位置展开/收起明细
function toggleExpand(row: HistoryRow) {
  historyTable.value?.toggleRowExpansion(row)
}

// 变更内容概览:只写大类(如 内存,CPU),完整明细在展开行
function digest(row: HistoryRow): string {
  const diff = row.diff as
    | {
        fields?: unknown[]
        nics?: unknown[]
        memory?: unknown[]
        cpus?: unknown[]
        disks?: unknown[]
        psus?: unknown[]
        gpus?: unknown[]
      }
    | null
  if (!diff) return '-'
  const parts: string[] = []
  if (diff.fields?.length) parts.push('主机字段')
  if (diff.nics?.length) parts.push('网卡')
  if (diff.memory?.length) parts.push('内存')
  if (diff.cpus?.length) parts.push('CPU')
  if (diff.disks?.length) parts.push('硬盘')
  if (diff.psus?.length) parts.push('电源')
  if (diff.gpus?.length) parts.push('GPU')
  return parts.length ? parts.join(',') : '-'
}

function fmt(ts: string | null): string {
  if (!ts) return '-'
  // 后端存 naive UTC,补 Z 标记后由浏览器转换为查看者本地时区
  const utc = /[Zz]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : ts + 'Z'
  return new Date(utc).toLocaleString()
}

function openTagEdit() {
  tagInput.value = device.value?.tags.join(',') || ''
  tagDialogVisible.value = true
}

async function saveTags() {
  if (!device.value) return
  try {
    const tags = tagInput.value.split(',').map((t) => t.trim()).filter(Boolean)
    const res = await api.updateTags(device.value.id, tags)
    device.value.tags = res.tags
    tagDialogVisible.value = false
    ElMessage.success('标签已更新')
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
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
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tag {
  margin-right: 4px;
}
.history-card :deep(.el-table__row) {
  cursor: pointer;
}
</style>
