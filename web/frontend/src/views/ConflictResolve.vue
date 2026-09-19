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
        <el-table-column resizable prop="id" label="ID" width="60" />
        <el-table-column resizable prop="device_id" label="设备 ID" width="80" />
        <el-table-column resizable prop="source" label="来源" width="110">
          <template #default="{ row }">{{ row.source || '-' }}</template>
        </el-table-column>
        <el-table-column resizable label="推送时间" min-width="150">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column resizable prop="status" label="状态" width="90" />
      </el-table>
    </el-card>

    <div class="detail">
      <template v-if="pending">
        <!-- Summary bar: change size overview + submit button pinned to the top, not pushed away by content -->
        <el-card v-if="hasEntries" class="card summary-card">
          <div class="summary-bar">
            <div class="summary-info">
              <span class="dev">设备 #{{ pending.device_id }}</span>
              <router-link :to="`/devices/${pending.device_id}`" class="dev-link">
                查看设备
              </router-link>
              <span class="counts">
                <el-tag type="success" size="small">新增 {{ counts.added }}</el-tag>
                <el-tag type="danger" size="small">候删 {{ counts.removed }}</el-tag>
                <el-tag type="warning" size="small">变化 {{ counts.changed }}</el-tag>
              </span>
              <span class="hint">默认采用新值,可逐条改为保留旧值</span>
            </div>
            <div v-if="isAdmin" class="summary-actions">
              <el-button size="small" @click="keepAllOld">全部保留旧值</el-button>
              <el-button type="primary" size="small" :loading="resolving" @click="submit">
                提交裁决
              </el-button>
            </div>
          </div>
        </el-card>

        <el-collapse v-if="hasEntries" v-model="openSections" class="sections">
          <el-collapse-item v-if="pending.diff.fields.length" name="fields">
            <template #title>
              <span class="sec-title">主机字段 ({{ pending.diff.fields.length }})</span>
            </template>
            <div v-for="f in pending.diff.fields" :key="f.field" class="field-row">
              <span class="fname">{{ fieldLabel(f.field) }}</span>
              <span class="old-val mono">{{ fmtValue(f.field, f.old) }}</span>
              <span class="arrow">→</span>
              <span class="new-val mono">{{ fmtValue(f.field, f.new) }}</span>
              <span v-if="isAdmin" class="choice">
                <el-radio-group v-model="fieldChoices[f.field]" size="small">
                  <el-radio-button value="old">保留旧值</el-radio-button>
                  <el-radio-button value="new">采用新值</el-radio-button>
                </el-radio-group>
              </span>
            </div>
          </el-collapse-item>

          <el-collapse-item v-if="pending.diff.nics.length" name="nics">
            <template #title>
              <span class="sec-title">网卡 ({{ pending.diff.nics.length }})</span>
            </template>
            <DiffEntry
              v-for="n in pending.diff.nics"
              :key="n.name"
              :entry="n"
              :identity="n.name || '(未命名)'"
              noun="网卡"
              v-model="nicChoices[n.name]"
              :is-admin="isAdmin"
            />
          </el-collapse-item>

          <el-collapse-item v-if="pending.diff.memory?.length" name="memory">
            <template #title>
              <span class="sec-title">内存 ({{ pending.diff.memory.length }})</span>
            </template>
            <DiffEntry
              v-for="m in pending.diff.memory"
              :key="m.slot"
              :entry="m"
              :identity="m.slot || '(未采集)'"
              noun="内存"
              :model-value="m.slot ? memoryChoices[m.slot] : undefined"
              @update:model-value="m.slot && (memoryChoices[m.slot] = $event)"
              :is-admin="isAdmin"
            />
          </el-collapse-item>

          <el-collapse-item v-if="pending.diff.cpus?.length" name="cpus">
            <template #title>
              <span class="sec-title">CPU ({{ pending.diff.cpus.length }})</span>
            </template>
            <DiffEntry
              v-for="c in pending.diff.cpus"
              :key="c.slot"
              :entry="c"
              :identity="c.slot || '(未采集)'"
              noun="CPU"
              :model-value="c.slot ? cpuChoices[c.slot] : undefined"
              @update:model-value="c.slot && (cpuChoices[c.slot] = $event)"
              :is-admin="isAdmin"
            />
          </el-collapse-item>

          <el-collapse-item v-if="pending.diff.disks?.length" name="disks">
            <template #title>
              <span class="sec-title">硬盘 ({{ pending.diff.disks.length }})</span>
            </template>
            <DiffEntry
              v-for="d in pending.diff.disks"
              :key="d.serial_number"
              :entry="d"
              :identity="hwSummary(d, ['manufacturer', 'model', 'type'], 'serial_number', 'SN')"
              noun="硬盘"
              :model-value="d.serial_number ? diskChoices[d.serial_number] : undefined"
              @update:model-value="d.serial_number && (diskChoices[d.serial_number] = $event)"
              :is-admin="isAdmin"
            />
          </el-collapse-item>

          <el-collapse-item v-if="pending.diff.psus?.length" name="psus">
            <template #title>
              <span class="sec-title">电源 ({{ pending.diff.psus.length }})</span>
            </template>
            <DiffEntry
              v-for="p in pending.diff.psus"
              :key="p.serial_number"
              :entry="p"
              :identity="hwSummary(p, ['manufacturer', 'model'], 'serial_number', 'SN')"
              noun="电源"
              :model-value="p.serial_number ? psuChoices[p.serial_number] : undefined"
              @update:model-value="p.serial_number && (psuChoices[p.serial_number] = $event)"
              :is-admin="isAdmin"
            />
          </el-collapse-item>

          <el-collapse-item v-if="pending.diff.gpus?.length" name="gpus">
            <template #title>
              <span class="sec-title">GPU ({{ pending.diff.gpus.length }})</span>
            </template>
            <DiffEntry
              v-for="g in pending.diff.gpus"
              :key="g.uuid"
              :entry="g"
              :identity="hwSummary(g, ['name'], 'uuid', 'UUID')"
              noun="GPU"
              :model-value="g.uuid ? gpuChoices[g.uuid] : undefined"
              @update:model-value="g.uuid && (gpuChoices[g.uuid] = $event)"
              :is-admin="isAdmin"
            />
          </el-collapse-item>
        </el-collapse>

        <p class="readonly-hint" v-if="isAdmin && !hasEntries">该记录无差异条目</p>
        <p class="readonly-hint" v-else-if="!isAdmin && hasEntries">
          当前账号为只读权限,仅可查看差异;如需裁决请联系管理员。
        </p>
      </template>
      <el-card v-else class="card">
        <el-empty description="从左侧选择待裁决记录" />
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, TableInstance } from 'element-plus'
import { api, PendingChange } from '../api'
import { fieldLabel, fmtValue } from '../utils/diff'
import DiffEntry from '../components/DiffEntry.vue'

// After a resolve is submitted, notify the sidebar badge to refresh immediately
const refreshPendingCount = inject<() => void>('refreshPendingCount', () => {})
const userRole = inject('userRole', ref('viewer'))
const isAdmin = computed(() => userRole.value === 'admin')

const pendings = ref<PendingChange[]>([])
const pending = ref<PendingChange | null>(null)
const fieldChoices = ref<Record<string, string>>({})
const nicChoices = ref<Record<string, string>>({})
const memoryChoices = ref<Record<string, string>>({})
const cpuChoices = ref<Record<string, string>>({})
const diskChoices = ref<Record<string, string>>({})
const psuChoices = ref<Record<string, string>>({})
const gpuChoices = ref<Record<string, string>>({})
const listLoading = ref(false)
const resolving = ref(false)
const tableRef = ref<TableInstance>()

// Left list capped with internal scrolling, adapts when the window narrows
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

// Section collapse state: all expanded by default
const openSections = ref<string[]>(['fields', 'nics', 'memory', 'cpus', 'disks', 'psus', 'gpus'])

// Change size overview: counts across all categories
const counts = computed(() => {
  const d = pending.value?.diff
  const list = [
    ...(d?.fields ?? []).map(() => 'changed'),
    ...(d?.nics ?? []).map((n) => n.kind),
    ...(d?.memory ?? []).map((m) => m.kind),
    ...(d?.cpus ?? []).map((c) => c.kind),
    ...(d?.disks ?? []).map((k) => k.kind),
    ...(d?.psus ?? []).map((k) => k.kind),
    ...(d?.gpus ?? []).map((k) => k.kind),
  ]
  return {
    added: list.filter((k) => k === 'added').length,
    removed: list.filter((k) => k === 'removed').length,
    changed: list.filter((k) => k === 'changed').length,
  }
})

const hasEntries = computed(() => {
  const d = pending.value?.diff
  return Boolean(
    d &&
      (d.fields.length ||
        d.nics.length ||
        d.memory?.length ||
        d.cpus?.length ||
        d.disks?.length ||
        d.psus?.length ||
        d.gpus?.length),
  )
})

// Readable identity summary: added takes the new object, removed/changed takes the old object
// builds a human-readable entry name from name/manufacturer/model, SN/UUID as annotation (UUID/SN alone does not tell which hardware)
function hwSummary(
  entry: {
    kind: string
    old: Record<string, unknown> | null
    new: Record<string, unknown> | null
  },
  names: string[],
  key: string,
  keyLabel: string,
): string {
  const o = (entry.kind === 'added' ? entry.new : entry.old) ?? {}
  const parts = names.filter((n) => o[n]).map((n) => String(o[n]))
  const id = o[key]
  return [...parts, id ? `${keyLabel}:${id}` : ''].filter(Boolean).join(' · ') || '(未采集)'
}

function fmt(ts: string): string {
  // Backend stores naive UTC, append a Z marker and let the browser convert to the viewer's local timezone
  const utc = /[Zz]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : ts + 'Z'
  return new Date(utc).toLocaleString()
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
  // Default to adopting all new values, the user can switch individual ones to keep the old value
  fieldChoices.value = {}
  nicChoices.value = {}
  memoryChoices.value = {}
  cpuChoices.value = {}
  diskChoices.value = {}
  psuChoices.value = {}
  gpuChoices.value = {}
  if (row) {
    for (const f of row.diff.fields) fieldChoices.value[f.field] = 'new'
    for (const n of row.diff.nics) if (n.name) nicChoices.value[n.name] = 'new'
    for (const m of row.diff.memory ?? [])
      if (m.slot) memoryChoices.value[m.slot] = 'new'
    for (const c of row.diff.cpus ?? []) if (c.slot) cpuChoices.value[c.slot] = 'new'
    for (const d of row.diff.disks ?? [])
      if (d.serial_number) diskChoices.value[d.serial_number] = 'new'
    for (const p of row.diff.psus ?? [])
      if (p.serial_number) psuChoices.value[p.serial_number] = 'new'
    for (const g of row.diff.gpus ?? [])
      if (g.uuid) gpuChoices.value[g.uuid] = 'new'
  }
}

// Keep all old values in one click (adopts no new data, only marked applied after submit)
function keepAllOld() {
  if (!pending.value) return
  for (const f of pending.value.diff.fields) fieldChoices.value[f.field] = 'old'
  for (const n of pending.value.diff.nics) if (n.name) nicChoices.value[n.name] = 'old'
  for (const m of pending.value.diff.memory ?? [])
    if (m.slot) memoryChoices.value[m.slot] = 'old'
  for (const c of pending.value.diff.cpus ?? []) if (c.slot) cpuChoices.value[c.slot] = 'old'
  for (const d of pending.value.diff.disks ?? [])
    if (d.serial_number) diskChoices.value[d.serial_number] = 'old'
  for (const p of pending.value.diff.psus ?? [])
    if (p.serial_number) psuChoices.value[p.serial_number] = 'old'
  for (const g of pending.value.diff.gpus ?? [])
    if (g.uuid) gpuChoices.value[g.uuid] = 'old'
  ElMessage.info('已全部选择保留旧值,可直接提交')
}

async function submit() {
  if (!pending.value) return
  resolving.value = true
  const resolvedId = pending.value.id
  // Remember the current item's position in the list, resume at the same position of the refreshed list after the resolve
  const idx = Math.max(0, pendings.value.findIndex((p) => p.id === resolvedId))
  try {
    const res = await api.resolve(resolvedId, {
      field_choices: fieldChoices.value,
      nic_choices: nicChoices.value,
      memory_choices: memoryChoices.value,
      cpu_choices: cpuChoices.value,
      disk_choices: diskChoices.value,
      psu_choices: psuChoices.value,
      gpu_choices: gpuChoices.value,
    })
    ElMessage.success('裁决生效')
    if (res.applied.length) {
      console.info('applied:', res.applied.join('; '))
    }
    await load()
    refreshPendingCount()
    // Auto-advance to the next entry: same position (i.e. the original next one); if the last entry was resolved, back to the top of the list
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
.summary-card :deep(.el-card__body) {
  padding: 12px 16px;
}
.summary-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.summary-info {
  display: flex;
  align-items: center;
  gap: 10px;
}
.dev {
  font-weight: bold;
  font-size: 15px;
}
.dev-link {
  font-size: 13px;
}
.hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.counts {
  display: inline-flex;
  gap: 6px;
}
.summary-actions {
  display: flex;
  gap: 8px;
}
.sections :deep(.el-collapse-item__header) {
  font-weight: bold;
}
.field-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 6px 8px;
  font-size: 13px;
}
.fname {
  flex-shrink: 0;
  width: 96px;
  color: var(--el-text-color-secondary);
  text-align: right;
}
.mono {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}
.old-val {
  color: var(--el-color-danger);
  background: #fef0f0;
  text-decoration: line-through;
  padding: 1px 6px;
  border-radius: 3px;
}
.new-val {
  color: var(--el-color-success);
  background: #f0f9eb;
  padding: 1px 6px;
  border-radius: 3px;
}
.arrow {
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}
.choice {
  margin-left: auto;
}
.readonly-hint {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
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
