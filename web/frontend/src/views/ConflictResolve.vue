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
        <el-card class="card">
          <template #header>主机字段差异(设备 #{{ pending.device_id }})</template>
          <el-table :data="pending.diff.fields" border>
            <el-table-column resizable label="字段" :min-width="diffWidths.fields.field" show-overflow-tooltip>
              <template #default="{ row }">{{ fieldLabel(row.field) }}</template>
            </el-table-column>
            <el-table-column resizable label="旧值(库中)" :min-width="diffWidths.fields.old" show-overflow-tooltip>
              <template #default="{ row }">{{ row.old ?? '-' }}</template>
            </el-table-column>
            <el-table-column resizable label="新值(推送)" :min-width="diffWidths.fields.new" show-overflow-tooltip>
              <template #default="{ row }">{{ row.new ?? '-' }}</template>
            </el-table-column>
            <el-table-column resizable v-if="isAdmin" label="裁决" width="220">
              <template #default="{ row }">
                <el-radio-group v-model="fieldChoices[row.field]">
                  <el-radio value="old">保留旧值</el-radio>
                  <el-radio value="new">采用新值</el-radio>
                </el-radio-group>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="card" v-if="pending.diff.nics.length">
          <template #header>网卡</template>
          <el-table :data="pending.diff.nics" border>
            <el-table-column resizable label="网卡" width="110">
              <template #default="{ row }">{{ row.name }}</template>
            </el-table-column>
            <el-table-column resizable label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="kindTag[row.kind]" size="small">
                  {{ kindLabel[row.kind] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column resizable label="旧值(库中)" :min-width="diffWidths.nics.old" show-overflow-tooltip>
              <template #default="{ row }">{{ partContent(nicRepr, row, 'old') }}</template>
            </el-table-column>
            <el-table-column resizable label="新值(推送)" :min-width="diffWidths.nics.new" show-overflow-tooltip>
              <template #default="{ row }">{{ partContent(nicRepr, row, 'new') }}</template>
            </el-table-column>
            <el-table-column resizable v-if="isAdmin" label="裁决" width="220">
              <template #default="{ row }">
                <el-radio-group v-model="nicChoices[row.name]" v-if="row.name">
                  <el-radio value="old">{{ kindOldLabel[row.kind] }}</el-radio>
                  <el-radio value="new">{{ kindNewLabel[row.kind] }}</el-radio>
                </el-radio-group>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="card" v-if="pending.diff.memory?.length">
          <template #header>内存</template>
          <el-table :data="pending.diff.memory" border>
            <el-table-column resizable label="槽位" width="120">
              <template #default="{ row }">{{ row.slot }}</template>
            </el-table-column>
            <el-table-column resizable label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="kindTag[row.kind]" size="small">
                  {{ kindLabel[row.kind] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column resizable label="旧值(库中)" :min-width="diffWidths.memory.old" show-overflow-tooltip>
              <template #default="{ row }">{{ partContent(memoryRepr, row, 'old') }}</template>
            </el-table-column>
            <el-table-column resizable label="新值(推送)" :min-width="diffWidths.memory.new" show-overflow-tooltip>
              <template #default="{ row }">{{ partContent(memoryRepr, row, 'new') }}</template>
            </el-table-column>
            <el-table-column resizable v-if="isAdmin" label="裁决" width="220">
              <template #default="{ row }">
                <el-radio-group v-model="memoryChoices[row.slot!]" v-if="row.slot">
                  <el-radio value="old">{{ memoryOldLabel[row.kind] }}</el-radio>
                  <el-radio value="new">{{ memoryNewLabel[row.kind] }}</el-radio>
                </el-radio-group>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="card" v-if="pending.diff.cpus?.length">
          <template #header>CPU</template>
          <el-table :data="pending.diff.cpus" border>
            <el-table-column resizable label="槽位" width="120">
              <template #default="{ row }">{{ row.slot }}</template>
            </el-table-column>
            <el-table-column resizable label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="kindTag[row.kind]" size="small">
                  {{ kindLabel[row.kind] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column resizable label="旧值(库中)" :min-width="diffWidths.cpus.old" show-overflow-tooltip>
              <template #default="{ row }">{{ partContent(cpuRepr, row, 'old') }}</template>
            </el-table-column>
            <el-table-column resizable label="新值(推送)" :min-width="diffWidths.cpus.new" show-overflow-tooltip>
              <template #default="{ row }">{{ partContent(cpuRepr, row, 'new') }}</template>
            </el-table-column>
            <el-table-column resizable v-if="isAdmin" label="裁决" width="220">
              <template #default="{ row }">
                <el-radio-group v-model="cpuChoices[row.slot!]" v-if="row.slot">
                  <el-radio value="old">{{ cpuOldLabel[row.kind] }}</el-radio>
                  <el-radio value="new">{{ cpuNewLabel[row.kind] }}</el-radio>
                </el-radio-group>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="card" v-if="pending.diff.disks?.length">
          <template #header>硬盘</template>
          <el-table :data="pending.diff.disks" border>
            <el-table-column resizable label="SN" width="130">
              <template #default="{ row }">{{ row.serial_number }}</template>
            </el-table-column>
            <el-table-column resizable label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="kindTag[row.kind]" size="small">
                  {{ kindLabel[row.kind] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column resizable label="旧值(库中)" :min-width="diffWidths.disks.old" show-overflow-tooltip>
              <template #default="{ row }">{{ partContent(diskRepr, row, 'old') }}</template>
            </el-table-column>
            <el-table-column resizable label="新值(推送)" :min-width="diffWidths.disks.new" show-overflow-tooltip>
              <template #default="{ row }">{{ partContent(diskRepr, row, 'new') }}</template>
            </el-table-column>
            <el-table-column resizable v-if="isAdmin" label="裁决" width="220">
              <template #default="{ row }">
                <el-radio-group
                  v-model="diskChoices[row.serial_number!]"
                  v-if="row.serial_number"
                >
                  <el-radio value="old">{{ diskOldLabel[row.kind] }}</el-radio>
                  <el-radio value="new">{{ diskNewLabel[row.kind] }}</el-radio>
                </el-radio-group>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="card" v-if="pending.diff.psus?.length">
          <template #header>电源</template>
          <el-table :data="pending.diff.psus" border>
            <el-table-column resizable label="SN" width="130">
              <template #default="{ row }">{{ row.serial_number }}</template>
            </el-table-column>
            <el-table-column resizable label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="kindTag[row.kind]" size="small">
                  {{ kindLabel[row.kind] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column resizable label="旧值(库中)" :min-width="diffWidths.psus.old" show-overflow-tooltip>
              <template #default="{ row }">{{ partContent(psuRepr, row, 'old') }}</template>
            </el-table-column>
            <el-table-column resizable label="新值(推送)" :min-width="diffWidths.psus.new" show-overflow-tooltip>
              <template #default="{ row }">{{ partContent(psuRepr, row, 'new') }}</template>
            </el-table-column>
            <el-table-column resizable v-if="isAdmin" label="裁决" width="220">
              <template #default="{ row }">
                <el-radio-group
                  v-model="psuChoices[row.serial_number!]"
                  v-if="row.serial_number"
                >
                  <el-radio value="old">{{ psuOldLabel[row.kind] }}</el-radio>
                  <el-radio value="new">{{ psuNewLabel[row.kind] }}</el-radio>
                </el-radio-group>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="card" v-if="pending.diff.gpus?.length">
          <template #header>GPU</template>
          <el-table :data="pending.diff.gpus" border>
            <el-table-column resizable label="UUID" width="130">
              <template #default="{ row }">{{ row.uuid }}</template>
            </el-table-column>
            <el-table-column resizable label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="kindTag[row.kind]" size="small">
                  {{ kindLabel[row.kind] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column resizable label="旧值(库中)" :min-width="diffWidths.gpus.old" show-overflow-tooltip>
              <template #default="{ row }">{{ partContent(gpuRepr, row, 'old') }}</template>
            </el-table-column>
            <el-table-column resizable label="新值(推送)" :min-width="diffWidths.gpus.new" show-overflow-tooltip>
              <template #default="{ row }">{{ partContent(gpuRepr, row, 'new') }}</template>
            </el-table-column>
            <el-table-column resizable v-if="isAdmin" label="裁决" width="220">
              <template #default="{ row }">
                <el-radio-group v-model="gpuChoices[row.uuid!]" v-if="row.uuid">
                  <el-radio value="old">{{ gpuOldLabel[row.kind] }}</el-radio>
                  <el-radio value="new">{{ gpuNewLabel[row.kind] }}</el-radio>
                </el-radio-group>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <div
          class="actions"
          v-if="isAdmin && hasEntries"
        >
          <el-button type="primary" :loading="resolving" @click="submit">
            提交裁决
          </el-button>
          <el-button @click="keepAllOld">全部保留旧值</el-button>
        </div>
        <p class="readonly-hint" v-else-if="hasEntries">
          当前账号为只读权限,仅可查看差异;如需裁决请联系管理员。
        </p>
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
import { computed, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, TableInstance } from 'element-plus'
import { api, PendingChange } from '../api'
import { fitMinWidths, FitCol } from '../utils/fit'

// 裁决提交成功后通知侧边栏气泡立即刷新
const refreshPendingCount = inject<() => void>('refreshPendingCount', () => {})
const userRole = inject('userRole', ref('viewer'))
const isAdmin = computed(() => userRole.value === 'admin')
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
const cpuOldLabel: Record<string, string> = {
  added: '丢弃(不新增)',
  removed: '保留(不删除)',
  changed: '保留旧值',
}
const cpuNewLabel: Record<string, string> = {
  added: '新增该 CPU',
  removed: '删除该 CPU',
  changed: '采用新值',
}
const diskOldLabel: Record<string, string> = {
  added: '丢弃(不新增)',
  removed: '保留(不删除)',
  changed: '保留旧值',
}
const diskNewLabel: Record<string, string> = {
  added: '新增该硬盘',
  removed: '删除该硬盘',
  changed: '采用新值',
}
const psuOldLabel: Record<string, string> = {
  added: '丢弃(不新增)',
  removed: '保留(不删除)',
  changed: '保留旧值',
}
const psuNewLabel: Record<string, string> = {
  added: '新增该电源',
  removed: '删除该电源',
  changed: '采用新值',
}
const gpuOldLabel: Record<string, string> = {
  added: '丢弃(不新增)',
  removed: '保留(不删除)',
  changed: '保留旧值',
}
const gpuNewLabel: Record<string, string> = {
  added: '新增该 GPU',
  removed: '删除该 GPU',
  changed: '采用新值',
}

// 列宽自适应:旧值/新值列按最长内容算 min-width,默认刚好放下、完整显示
type DiffEntry = {
  kind: string
  old: unknown
  new: unknown
  changes?: { field: string; old: unknown; new: unknown }[]
}
const diffWidths = computed(() => {
  const d = pending.value?.diff
  const valueCols = (reprFn: (o: Record<string, unknown>) => string): FitCol<DiffEntry>[] => [
    { key: 'old', label: '旧值(库中)', text: (r) => partContent(reprFn, r, 'old') },
    { key: 'new', label: '新值(推送)', text: (r) => partContent(reprFn, r, 'new') },
  ]
  return {
    fields: fitMinWidths(d?.fields ?? [], [
      { key: 'field', label: '字段' },
      { key: 'old', label: '旧值(库中)' },
      { key: 'new', label: '新值(推送)' },
    ]),
    nics: fitMinWidths(d?.nics ?? [], valueCols(nicRepr)),
    memory: fitMinWidths(d?.memory ?? [], valueCols(memoryRepr)),
    cpus: fitMinWidths(d?.cpus ?? [], valueCols(cpuRepr)),
    disks: fitMinWidths(d?.disks ?? [], valueCols(diskRepr)),
    psus: fitMinWidths(d?.psus ?? [], valueCols(psuRepr)),
    gpus: fitMinWidths(d?.gpus ?? [], valueCols(gpuRepr)),
  }
})

function memoryRepr(m: Record<string, unknown>): string {
  const parts: string[] = []
  if (m.manufacturer) parts.push(String(m.manufacturer))
  if (m.part_number) parts.push(String(m.part_number))
  if (m.type) parts.push(String(m.type))
  if (m.size) parts.push(`${m.size}${m.size_unit ?? ''}`)
  if (m.speed_mts) parts.push(`${m.speed_mts}MT/s`)
  if (m.serial_number) parts.push(`SN:${m.serial_number}`)
  return parts.length ? parts.join(' ') : '-'
}

function gpuRepr(g: Record<string, unknown>): string {
  const parts: string[] = []
  if (g.name) parts.push(String(g.name))
  if (g.size) parts.push(`${g.size}${g.size_unit ?? ''}`)
  if (g.driver_version) parts.push(`driver:${g.driver_version}`)
  if (g.pcie_id) parts.push(`${g.pcie_id}`)
  if (g.serial_number) parts.push(`SN:${g.serial_number}`)
  return parts.length ? parts.join(' ') : '-'
}

function diskRepr(d: Record<string, unknown>): string {
  const parts: string[] = []
  if (d.type) parts.push(String(d.type))
  if (d.manufacturer) parts.push(String(d.manufacturer))
  if (d.model) parts.push(String(d.model))
  if (d.size) parts.push(`${d.size}${d.size_unit ?? ''}`)
  if (d.serial_number) parts.push(`SN:${d.serial_number}`)
  return parts.length ? parts.join(' ') : '-'
}

function psuRepr(p: Record<string, unknown>): string {
  const parts: string[] = []
  if (p.manufacturer) parts.push(String(p.manufacturer))
  if (p.model) parts.push(String(p.model))
  if (p.max_power_w) parts.push(`${p.max_power_w}W`)
  if (p.serial_number) parts.push(`SN:${p.serial_number}`)
  return parts.length ? parts.join(' ') : '-'
}

function cpuRepr(c: Record<string, unknown>): string {
  return String(c.model ?? '-')
}

// 旧值/新值两列对比:added 的旧值与 removed 的新值不存在,显示 -
function partContent(
  reprFn: (o: Record<string, unknown>) => string,
  entry: {
    kind: string
    old: unknown
    new: unknown
    changes?: { field: string; old: unknown; new: unknown }[]
  },
  which: 'old' | 'new',
): string {
  if (which === 'old' && entry.kind === 'added') return '-'
  if (which === 'new' && entry.kind === 'removed') return '-'
  const obj = (which === 'old' ? entry.old : entry.new) as Record<string, unknown> | null
  if (obj) return reprFn(obj)
  // 已存 diff 的 changed 条目没有整体 old/new,从逐字段 changes 回溯
  const built: Record<string, unknown> = {}
  for (const c of entry.changes ?? []) built[c.field] = which === 'old' ? c.old : c.new
  return reprFn(built)
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
  diskChoices.value = {}
  psuChoices.value = {}
  gpuChoices.value = {}
  if (row) {
    for (const f of row.diff.fields) fieldChoices.value[f.field] = 'new'
    for (const n of row.diff.nics) nicChoices.value[n.name] = 'new'
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

// 一键全部保留旧值(不采用任何新数据,提交后仅标记 applied)
function keepAllOld() {
  if (!pending.value) return
  for (const f of pending.value.diff.fields) fieldChoices.value[f.field] = 'old'
  for (const n of pending.value.diff.nics) nicChoices.value[n.name] = 'old'
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
  // 记住当前项在列表中的位置,裁决后从刷新后列表的同一位置继续
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
    ElMessage.success(
      res.applied.length
        ? `裁决生效:${res.applied.join('; ')}`
        : '裁决已提交(保留现状,无实际改动)'
    )
    await load()
    refreshPendingCount()
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
.actions {
  margin-top: 4px;
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
