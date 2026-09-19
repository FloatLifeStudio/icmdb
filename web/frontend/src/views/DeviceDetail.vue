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
          <el-button v-if="isAdmin" size="small" @click="openMetaEdit">编辑信息</el-button>
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
        <el-descriptions-item label="虚拟化">
          {{ device.os_virt || '-' }}
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
        <el-descriptions-item label="位置">
          {{ device.location || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="负责人">
          {{ device.owner || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="用途">
          {{ device.purpose || '-' }}
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
        <el-table-column resizable prop="name" label="网卡" width="120" show-overflow-tooltip/>
        <el-table-column resizable prop="mac" label="MAC" min-width="160" show-overflow-tooltip/>
        <el-table-column resizable label="IP 列表" min-width="280" show-overflow-tooltip>
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
        <el-table-column resizable prop="slot" label="槽位" :min-width="memoryWidths.slot" show-overflow-tooltip/>
        <el-table-column resizable prop="manufacturer" label="厂商" :min-width="memoryWidths.manufacturer" show-overflow-tooltip>
          <template #default="{ row }">{{ row.manufacturer || '-' }}</template>
        </el-table-column>
        <el-table-column resizable prop="part_number" label="型号" :min-width="memoryWidths.part_number" show-overflow-tooltip>
          <template #default="{ row }">{{ row.part_number || '-' }}</template>
        </el-table-column>
        <el-table-column resizable prop="type" label="代数" :min-width="memoryWidths.type" show-overflow-tooltip>
          <template #default="{ row }">{{ row.type || '-' }}</template>
        </el-table-column>
        <el-table-column resizable label="容量" :min-width="memoryWidths.size" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.size ? row.size + (row.size_unit ?? '') : '-' }}
          </template>
        </el-table-column>
        <el-table-column resizable label="频率" :min-width="memoryWidths.speed_mts" show-overflow-tooltip>
          <template #default="{ row }">{{ row.speed_mts ? row.speed_mts + 'MT/s' : '-' }}</template>
        </el-table-column>
        <el-table-column resizable prop="serial_number" label="SN" :min-width="memoryWidths.serial_number" show-overflow-tooltip>
          <template #default="{ row }">{{ row.serial_number || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="device && device.cpus.length" class="card">
      <template #header>CPU</template>
      <el-table :data="device.cpus" border>
        <el-table-column resizable prop="slot" label="槽位" :min-width="cpuWidths.slot" show-overflow-tooltip/>
        <el-table-column resizable prop="model" label="型号" :min-width="cpuWidths.model" show-overflow-tooltip/>
      </el-table>
    </el-card>

    <el-card v-if="device && device.disks.length" class="card">
      <template #header>硬盘</template>
      <el-table :data="device.disks" border>
        <el-table-column resizable prop="type" label="类型" :min-width="diskWidths.type" show-overflow-tooltip>
          <template #default="{ row }">{{ row.type || '-' }}</template>
        </el-table-column>
        <el-table-column resizable prop="manufacturer" label="品牌" :min-width="diskWidths.manufacturer" show-overflow-tooltip>
          <template #default="{ row }">{{ row.manufacturer || '-' }}</template>
        </el-table-column>
        <el-table-column resizable prop="model" label="型号" :min-width="diskWidths.model" show-overflow-tooltip>
          <template #default="{ row }">{{ row.model || '-' }}</template>
        </el-table-column>
        <el-table-column resizable label="容量" :min-width="diskWidths.size" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.size ? row.size + (row.size_unit ?? '') : '-' }}
          </template>
        </el-table-column>
        <el-table-column resizable prop="serial_number" label="SN" :min-width="diskWidths.serial_number" show-overflow-tooltip/>
      </el-table>
    </el-card>

    <el-card v-if="device && device.psus.length" class="card">
      <template #header>电源</template>
      <el-table :data="device.psus" border>
        <el-table-column resizable prop="manufacturer" label="品牌" :min-width="psuWidths.manufacturer" show-overflow-tooltip>
          <template #default="{ row }">{{ row.manufacturer || '-' }}</template>
        </el-table-column>
        <el-table-column resizable prop="model" label="型号" :min-width="psuWidths.model" show-overflow-tooltip>
          <template #default="{ row }">{{ row.model || '-' }}</template>
        </el-table-column>
        <el-table-column resizable label="最大功率" :min-width="psuWidths.max_power_w" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.max_power_w ? row.max_power_w + 'W' : '-' }}
          </template>
        </el-table-column>
        <el-table-column resizable prop="serial_number" label="SN" :min-width="psuWidths.serial_number" show-overflow-tooltip/>
      </el-table>
    </el-card>

    <el-card v-if="device && device.gpus.length" class="card">
      <template #header>GPU</template>
      <el-table :data="device.gpus" border>
        <el-table-column resizable prop="name" label="型号" :min-width="gpuWidths.name" show-overflow-tooltip>
          <template #default="{ row }">{{ row.name || '-' }}</template>
        </el-table-column>
        <el-table-column resizable label="显存" :min-width="gpuWidths.size" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.size ? row.size + (row.size_unit ?? '') : '-' }}
          </template>
        </el-table-column>
        <el-table-column resizable prop="driver_version" label="驱动" :min-width="gpuWidths.driver_version" show-overflow-tooltip>
          <template #default="{ row }">{{ row.driver_version || '-' }}</template>
        </el-table-column>
        <el-table-column resizable prop="pcie_id" label="PCIe" :min-width="gpuWidths.pcie_id" show-overflow-tooltip>
          <template #default="{ row }">{{ row.pcie_id || '-' }}</template>
        </el-table-column>
        <el-table-column resizable label="SN" :min-width="gpuWidths.serial_number" show-overflow-tooltip>
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
        <el-table-column resizable prop="created_at" label="时间" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column resizable label="变更内容" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ digest(row) }}</template>
        </el-table-column>
        <el-table-column resizable prop="source" label="来源" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.source || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="metaDialogVisible" title="编辑信息" width="420px">
      <el-form label-width="80">
        <el-form-item label="标签">
          <el-input
            v-model="tagInput"
            placeholder="多个标签用英文逗号分隔,如:生产,web"
          />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="metaInput.location" placeholder="机房/机柜位置" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="metaInput.owner" placeholder="负责人" />
        </el-form-item>
        <el-form-item label="用途">
          <el-input v-model="metaInput.purpose" placeholder="用途" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="metaDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMeta">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, TableInstance } from 'element-plus'
import { api, DeviceOut, HistoryRow } from '../api'
import DiffDetail from '../components/DiffDetail.vue'
import { fitMinWidths } from '../utils/fit'

const userRole = inject('userRole', ref('viewer'))
const isAdmin = computed(() => userRole.value === 'admin')

const route = useRoute()
const deviceId = Number(route.params.id)
const device = ref<DeviceOut | null>(null)
const history = ref<HistoryRow[]>([])
const loading = ref(false)
const historyLoading = ref(false)
const metaDialogVisible = ref(false)
const tagInput = ref('')
const metaInput = ref({ location: '', owner: '', purpose: '' })
const historyTable = ref<TableInstance>()

// 列宽自适应:按各列最长内容算 min-width,默认刚好放下、完整显示
const memoryWidths = computed(() =>
  fitMinWidths(device.value?.memory ?? [], [
    { key: 'slot', label: '槽位' },
    { key: 'manufacturer', label: '厂商' },
    { key: 'part_number', label: '型号' },
    { key: 'type', label: '代数' },
    { key: 'size', label: '容量', text: (r) => (r.size ? `${r.size}${r.size_unit ?? ''}` : '-') },
    { key: 'speed_mts', label: '频率', text: (r) => (r.speed_mts ? `${r.speed_mts}MT/s` : '-') },
    { key: 'serial_number', label: 'SN' },
  ])
)
const cpuWidths = computed(() =>
  fitMinWidths(device.value?.cpus ?? [], [
    { key: 'slot', label: '槽位' },
    { key: 'model', label: '型号' },
  ])
)
const diskWidths = computed(() =>
  fitMinWidths(device.value?.disks ?? [], [
    { key: 'type', label: '类型' },
    { key: 'manufacturer', label: '品牌' },
    { key: 'model', label: '型号' },
    { key: 'size', label: '容量', text: (r) => (r.size ? `${r.size}${r.size_unit ?? ''}` : '-') },
    { key: 'serial_number', label: 'SN' },
  ])
)
const psuWidths = computed(() =>
  fitMinWidths(device.value?.psus ?? [], [
    { key: 'manufacturer', label: '品牌' },
    { key: 'model', label: '型号' },
    { key: 'max_power_w', label: '最大功率', text: (r) => (r.max_power_w ? `${r.max_power_w}W` : '-') },
    { key: 'serial_number', label: 'SN' },
  ])
)
const gpuWidths = computed(() =>
  fitMinWidths(device.value?.gpus ?? [], [
    { key: 'name', label: '型号' },
    { key: 'size', label: '显存', text: (r) => (r.size ? `${r.size}${r.size_unit ?? ''}` : '-') },
    { key: 'driver_version', label: '驱动' },
    { key: 'pcie_id', label: 'PCIe' },
    { key: 'serial_number', label: 'SN' },
  ])
)

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

function openMetaEdit() {
  tagInput.value = device.value?.tags.join(',') || ''
  metaInput.value = {
    location: device.value?.location || '',
    owner: device.value?.owner || '',
    purpose: device.value?.purpose || '',
  }
  metaDialogVisible.value = true
}

async function saveMeta() {
  if (!device.value) return
  try {
    const tags = tagInput.value.split(',').map((t) => t.trim()).filter(Boolean)
    const res = await api.updateTags(device.value.id, tags)
    device.value.tags = res.tags
    const meta = {
      location: metaInput.value.location,
      owner: metaInput.value.owner,
      purpose: metaInput.value.purpose,
    }
    const metaRes = await api.updateMetadata(device.value.id, meta)
    device.value.location = metaRes.location
    device.value.owner = metaRes.owner
    device.value.purpose = metaRes.purpose
    metaDialogVisible.value = false
    ElMessage.success('信息已更新')
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
