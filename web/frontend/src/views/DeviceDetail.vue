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
        <el-table-column label="详情" width="80">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="showDiff(row)">
              查看
            </el-button>
          </template>
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

    <el-dialog v-model="diffDialogVisible" title="变更详情" width="700px">
      <template v-if="diffRow">
        <el-descriptions :column="2" border class="diff-desc">
          <el-descriptions-item label="时间">{{ fmt(diffRow.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ diffRow.source || '-' }}</el-descriptions-item>
        </el-descriptions>
        <template v-if="diffRow.diff">
          <h4>主机字段</h4>
          <el-table :data="diffRow.diff.fields" border size="small">
            <el-table-column prop="field" label="字段" min-width="120" />
            <el-table-column label="旧值" min-width="140">
              <template #default="{ row }">{{ row.old ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="新值" min-width="140">
              <template #default="{ row }">{{ row.new ?? '-' }}</template>
            </el-table-column>
          </el-table>
          <h4>网卡</h4>
          <el-table :data="diffRow.diff.nics" border size="small">
            <el-table-column prop="name" label="网卡" width="100" />
            <el-table-column label="类型" width="100">
              <template #default="{ row }">{{ kindLabel[row.kind] || row.kind }}</template>
            </el-table-column>
            <el-table-column label="变化" min-width="260">
              <template #default="{ row }">
                <div v-for="(c, i) in row.changes" :key="i">
                  {{ c.field }}: {{ fmtChange(c) }}
                </div>
                <span v-if="!row.changes.length">-</span>
              </template>
            </el-table-column>
          </el-table>
        </template>
        <el-empty v-else description="该记录无 diff 详情(历史数据)" />
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, DeviceOut, HistoryRow, NicDiff, FieldDiff } from '../api'

const route = useRoute()
const deviceId = Number(route.params.id)
const device = ref<DeviceOut | null>(null)
const history = ref<HistoryRow[]>([])
const loading = ref(false)
const historyLoading = ref(false)
const tagDialogVisible = ref(false)
const tagInput = ref('')
const diffDialogVisible = ref(false)
const diffRow = ref<HistoryRow | null>(null)

const kindLabel: Record<string, string> = {
  added: '新增',
  removed: '候删',
  changed: '有变化',
}

function fmt(ts: string | null): string {
  if (!ts) return '-'
  // 后端存 naive UTC,补 Z 标记后由浏览器转换为查看者本地时区
  const utc = /[Zz]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : ts + 'Z'
  return new Date(utc).toLocaleString()
}

function fmtChange(change: FieldDiff): string {
  if (change.field === 'ips') {
    const ips = (v: unknown) =>
      ((v as { ip: string }[]) || []).map((i) => i.ip).join(', ') || '无'
    return `${ips(change.old)} -> ${ips(change.new)}`
  }
  return `${change.old} -> ${change.new}`
}

function nicDiffKind(n: NicDiff): string {
  return n.kind
}

function showDiff(row: HistoryRow) {
  diffRow.value = row
  diffDialogVisible.value = true
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
.diff-desc {
  margin-bottom: 12px;
}
</style>
