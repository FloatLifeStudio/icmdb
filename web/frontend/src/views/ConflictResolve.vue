<template>
  <div class="page">
    <el-card class="list-card" v-loading="listLoading">
      <template #header>待裁决列表</template>
      <el-table
        ref="tableRef"
        :data="pendings"
        highlight-current-row
        :max-height="listMaxHeight"
        @current-change="selectPending"
      >
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="device_id" label="设备 ID" width="80" />
        <el-table-column prop="source" label="来源" width="110">
          <template #default="{ row }">{{ row.source || '-' }}</template>
        </el-table-column>
        <el-table-column label="推送时间" min-width="150">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" />
      </el-table>
    </el-card>

    <div class="detail">
      <template v-if="pending">
        <el-card class="card">
          <template #header>主机字段差异(设备 #{{ pending.device_id }})</template>
          <el-table :data="pending.diff.fields" border>
            <el-table-column label="字段" min-width="140">
              <template #default="{ row }">{{ fieldLabel(row.field) }}</template>
            </el-table-column>
            <el-table-column label="旧值(库中)" min-width="180">
              <template #default="{ row }">{{ row.old ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="新值(推送)" min-width="180">
              <template #default="{ row }">{{ row.new ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="裁决" width="220">
              <template #default="{ row }">
                <el-radio-group v-model="fieldChoices[row.field]">
                  <el-radio value="old">保留旧值</el-radio>
                  <el-radio value="new">采用新值</el-radio>
                </el-radio-group>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="card" v-for="entry in pending.diff.nics" :key="entry.name">
          <template #header>
            网卡 {{ entry.name }}
            <el-tag :type="kindTag[entry.kind]" class="kind-tag">
              {{ kindLabel[entry.kind] }}
            </el-tag>
          </template>

          <el-descriptions :column="1" border class="nic-detail">
            <el-descriptions-item v-if="entry.old" label="旧状态">
              {{ nicRepr(entry.old) }}
            </el-descriptions-item>
            <el-descriptions-item v-if="entry.new" label="新状态">
              {{ nicRepr(entry.new) }}
            </el-descriptions-item>
            <el-descriptions-item
              v-for="(change, i) in entry.changes"
              :key="i"
              :label="fieldLabel(change.field)"
            >
              {{ fmtChange(change) }}
            </el-descriptions-item>
          </el-descriptions>

          <el-radio-group v-model="nicChoices[entry.name]" class="nic-choice">
            <el-radio value="old">{{ kindOldLabel[entry.kind] }}</el-radio>
            <el-radio value="new">{{ kindNewLabel[entry.kind] }}</el-radio>
          </el-radio-group>
        </el-card>

        <el-card class="card" v-for="entry in pending.diff.memory" :key="entry.slot">
          <template #header>
            内存 {{ entry.slot }}
            <el-tag :type="kindTag[entry.kind]" class="kind-tag">
              {{ kindLabel[entry.kind] }}
            </el-tag>
          </template>

          <el-descriptions :column="1" border class="nic-detail">
            <el-descriptions-item v-if="entry.old" label="旧状态">
              {{ memoryRepr(entry.old) }}
            </el-descriptions-item>
            <el-descriptions-item v-if="entry.new" label="新状态">
              {{ memoryRepr(entry.new) }}
            </el-descriptions-item>
            <el-descriptions-item
              v-for="(change, i) in entry.changes"
              :key="i"
              :label="change.field"
            >
              {{ change.old }} -> {{ change.new }}
            </el-descriptions-item>
          </el-descriptions>

          <el-radio-group v-model="memoryChoices[entry.slot]" class="nic-choice">
            <el-radio value="old">{{ memoryOldLabel[entry.kind] }}</el-radio>
            <el-radio value="new">{{ memoryNewLabel[entry.kind] }}</el-radio>
          </el-radio-group>
        </el-card>

        <el-card class="card" v-for="entry in pending.diff.cpus" :key="entry.slot">
          <template #header>
            CPU {{ entry.slot }}
            <el-tag :type="kindTag[entry.kind]" class="kind-tag">
              {{ kindLabel[entry.kind] }}
            </el-tag>
          </template>

          <el-descriptions :column="1" border class="nic-detail">
            <el-descriptions-item v-if="entry.old" label="旧状态">
              {{ entry.old?.model ?? '-' }}
            </el-descriptions-item>
            <el-descriptions-item v-if="entry.new" label="新状态">
              {{ entry.new?.model ?? '-' }}
            </el-descriptions-item>
            <el-descriptions-item
              v-for="(change, i) in entry.changes"
              :key="i"
              :label="change.field"
            >
              {{ change.old }} -> {{ change.new }}
            </el-descriptions-item>
          </el-descriptions>

          <el-radio-group v-model="cpuChoices[entry.slot]" class="nic-choice">
            <el-radio value="old">{{ memoryOldLabel[entry.kind] }}</el-radio>
            <el-radio value="new">{{ memoryNewLabel[entry.kind] }}</el-radio>
          </el-radio-group>
        </el-card>

        <div
          class="actions"
          v-if="pending.diff.fields.length || pending.diff.nics.length || pending.diff.memory?.length || pending.diff.cpus?.length"
        >
          <el-button type="primary" :loading="resolving" @click="submit">
            提交裁决
          </el-button>
        </div>
        <el-empty
          v-else
          description="该记录无差异条目"
        />
      </template>
      <el-card v-else class="card">
        <el-empty description="从左侧选择待裁决记录" />
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, TableInstance } from 'element-plus'
import { api, NicDiff, PendingChange } from '../api'

const pendings = ref<PendingChange[]>([])
const pending = ref<PendingChange | null>(null)
const fieldChoices = ref<Record<string, string>>({})
const nicChoices = ref<Record<string, string>>({})
const memoryChoices = ref<Record<string, string>>({})
const cpuChoices = ref<Record<string, string>>({})
const listLoading = ref(false)
const resolving = ref(false)
const tableRef = ref<TableInstance>()

// 左侧列表限高内部滚动,窗口变窄时自适应
const listMaxHeight = ref(600)
function onResize() {
  listMaxHeight.value = Math.max(300, window.innerHeight - 180)
}
onMounted(() => {
  onResize()
  window.addEventListener('resize', onResize)
  load()
})
onBeforeUnmount(() => window.removeEventListener('resize', onResize))

const kindLabel: Record<string, string> = {
  added: '新增',
  removed: '候删',
  changed: '有变化',
}

// 主机字段路径 -> 人类可读名称
const fieldLabels: Record<string, string> = {
  hostname: '主机名',
  serial_number: '序列号',
  mgmt_mac: '管理 MAC',
  mgmt_ip: '管理 IP',
  mgmt_prefix_length: '子网前缀',
  mac: 'MAC',
  ips: 'IP 列表',
}
function fieldLabel(f: string): string {
  return fieldLabels[f] ?? f
}
const kindTag: Record<string, string> = {
  added: 'success',
  removed: 'danger',
  changed: 'warning',
}
const kindOldLabel: Record<string, string> = {
  added: '丢弃(不新增)',
  removed: '保留(不删除)',
  changed: '保留旧值',
}
const kindNewLabel: Record<string, string> = {
  added: '新增该网卡',
  removed: '删除该网卡',
  changed: '采用新值',
}
const memoryOldLabel: Record<string, string> = {
  added: '丢弃(不新增)',
  removed: '保留(不删除)',
  changed: '保留旧值',
}
const memoryNewLabel: Record<string, string> = {
  added: '新增该内存',
  removed: '删除该内存',
  changed: '采用新值',
}

function memoryRepr(m: Record<string, unknown>): string {
  const parts: string[] = []
  if (m.manufacturer) parts.push(String(m.manufacturer))
  if (m.part_number) parts.push(String(m.part_number))
  if (m.type) parts.push(String(m.type))
  if (m.size_gb) parts.push(`${m.size_gb}GB`)
  if (m.speed_mts) parts.push(`${m.speed_mts}MT/s`)
  if (m.serial_number) parts.push(`SN:${m.serial_number}`)
  return parts.length ? parts.join(' ') : '-'
}

function fmt(ts: string): string {
  // 后端存 naive UTC,补 Z 标记后由浏览器转换为查看者本地时区
  const utc = /[Zz]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : ts + 'Z'
  return new Date(utc).toLocaleString()
}

function nicRepr(nic: Record<string, unknown>): string {
  const mac = nic.mac ? `MAC ${nic.mac}` : '无 MAC'
  const ips = (nic.ips as { ip: string; prefix_length: number | null }[]) || []
  const ipStr = ips.map((i) => i.ip + (i.prefix_length ? '/' + i.prefix_length : ''))
  return `${nic.name}(${mac}),IP: ${ipStr.length ? ipStr.join(', ') : '无'}`
}

function fmtChange(change: { field: string; old: unknown; new: unknown }): string {
  if (change.field === 'ips') {
    const ips = (v: unknown) =>
      ((v as { ip: string }[]) || []).map((i) => i.ip).join(', ') || '无'
    return `IP: ${ips(change.old)} -> ${ips(change.new)}`
  }
  return `${change.old} -> ${change.new}`
}

async function load() {
  listLoading.value = true
  try {
    const res = await api.listPendingChanges('pending')
    pendings.value = res.items
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    listLoading.value = false
  }
}

function selectPending(row: PendingChange | null) {
  pending.value = row
  // 默认全部采用新值,用户可逐条改为保留旧值
  fieldChoices.value = {}
  nicChoices.value = {}
  memoryChoices.value = {}
  cpuChoices.value = {}
  if (row) {
    for (const f of row.diff.fields) fieldChoices.value[f.field] = 'new'
    for (const n of row.diff.nics) nicChoices.value[n.name] = 'new'
    for (const m of row.diff.memory ?? []) memoryChoices.value[m.slot] = 'new'
    for (const c of row.diff.cpus ?? []) cpuChoices.value[c.slot] = 'new'
  }
}

async function submit() {
  if (!pending.value) return
  resolving.value = true
  const resolvedId = pending.value.id
  // 记住当前项在列表中的位置,裁决后从刷新后列表的同一位置继续
  const idx = Math.max(0, pendings.value.findIndex((p) => p.id === resolvedId))
  try {
    const res = await api.resolve(resolvedId, {
      field_choices: fieldChoices.value,
      nic_choices: nicChoices.value,
      memory_choices: memoryChoices.value,
      cpu_choices: cpuChoices.value,
    })
    ElMessage.success(
      res.applied.length
        ? `裁决生效:${res.applied.join('; ')}`
        : '裁决已提交(保留现状,无实际改动)'
    )
    await load()
    // 自动切换到下一条:同一位置(即原下一条);裁决的是最后一条则回到列表开头
    const rest = pendings.value
    const next = rest.length ? rest[idx % rest.length] : null
    selectPending(next)
    tableRef.value?.setCurrentRow(next ?? undefined)
    if (!next) ElMessage.info('所有待裁决记录已处理完毕')
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    resolving.value = false
  }
}
</script>

<style scoped>
.page {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.list-card {
  width: 460px;
  flex-shrink: 0;
}
.detail {
  flex: 1;
  min-width: 0;
}
.card {
  margin-bottom: 16px;
}
.kind-tag {
  margin-left: 8px;
}
.nic-detail {
  margin-bottom: 12px;
}
.nic-choice {
  margin-bottom: 4px;
}
.actions {
  margin-top: 4px;
}
@media (max-width: 900px) {
  .page {
    flex-direction: column;
    align-items: stretch;
  }
  .list-card {
    width: 100%;
  }
}
</style>
