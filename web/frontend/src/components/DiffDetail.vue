<template>
  <div class="diff-detail">
    <template
      v-if="diff && (diff.fields.length || diff.nics.length || diff.memory?.length || diff.cpus?.length || diff.disks?.length || diff.psus?.length)"
    >
      <h4 class="section-title">主机字段</h4>
      <el-table :data="diff.fields" border size="small">
        <el-table-column resizable prop="field" label="字段" :min-width="diffWidths.fields.field" show-overflow-tooltip/>
        <el-table-column resizable label="旧值(库中)" :min-width="diffWidths.fields.old" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="old-val mono">{{ fmtValue(row.field, row.old) }}</span>
          </template>
        </el-table-column>
        <el-table-column resizable label="新值(推送)" :min-width="diffWidths.fields.new" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="new-val mono">{{ fmtValue(row.field, row.new) }}</span>
          </template>
        </el-table-column>
      </el-table>

      <h4 class="section-title">网卡</h4>
      <el-table :data="diff.nics" border size="small">
        <el-table-column resizable prop="name" label="网卡" :min-width="diffWidths.nics.name" show-overflow-tooltip/>
        <el-table-column resizable label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="kindTag[row.kind]" size="small">
              {{ kindLabel[row.kind] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column resizable label="变化" :min-width="diffWidths.nics.changes" show-overflow-tooltip>
          <template #default="{ row }">
            <div v-for="(c, i) in row.changes" :key="i" class="change-line mono">
              <span class="old-val">{{ fmtValue(c.field, c.old) }}</span>
              <span class="arrow">→</span>
              <span class="new-val">{{ fmtValue(c.field, c.new) }}</span>
            </div>
            <span v-if="!row.changes.length" :class="row.kind === 'added' ? 'hint-added' : 'hint-removed'">
              {{ emptyHint[row.kind] }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <template v-if="diff.memory?.length">
        <h4 class="section-title">内存</h4>
        <el-table :data="diff.memory" border size="small">
          <el-table-column resizable prop="slot" label="槽位" :min-width="diffWidths.memory.slot" show-overflow-tooltip/>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">
                {{ kindLabel[row.kind] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column resizable label="变化" :min-width="diffWidths.memory.changes" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="change-line mono">
                <span class="old-val">{{ fmtValue(c.field, c.old) }}</span>
                <span class="arrow">→</span>
                <span class="new-val">{{ fmtValue(c.field, c.new) }}</span>
              </div>
              <span v-if="!row.changes.length" :class="row.kind === 'added' ? 'hint-added' : 'hint-removed'">
                {{ emptyHint[row.kind] }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-if="diff.cpus?.length">
        <h4 class="section-title">CPU</h4>
        <el-table :data="diff.cpus" border size="small">
          <el-table-column resizable prop="slot" label="槽位" :min-width="diffWidths.cpus.slot" show-overflow-tooltip/>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">
                {{ kindLabel[row.kind] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column resizable label="变化" :min-width="diffWidths.cpus.changes" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="change-line mono">
                <span class="old-val">{{ fmtValue(c.field, c.old) }}</span>
                <span class="arrow">→</span>
                <span class="new-val">{{ fmtValue(c.field, c.new) }}</span>
              </div>
              <span v-if="!row.changes.length" :class="row.kind === 'added' ? 'hint-added' : 'hint-removed'">
                {{ emptyHint[row.kind] }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-if="diff.disks?.length">
        <h4 class="section-title">硬盘</h4>
        <el-table :data="diff.disks" border size="small">
          <el-table-column resizable label="SN" :min-width="diffWidths.disks.serial_number" show-overflow-tooltip>
            <template #default="{ row }">{{ ident(row, ['manufacturer', 'model', 'type'], 'serial_number', 'SN') }}</template>
          </el-table-column>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">
                {{ kindLabel[row.kind] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column resizable label="变化" :min-width="diffWidths.disks.changes" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="change-line mono">
                <span class="old-val">{{ fmtValue(c.field, c.old) }}</span>
                <span class="arrow">→</span>
                <span class="new-val">{{ fmtValue(c.field, c.new) }}</span>
              </div>
              <span v-if="!row.changes.length" :class="row.kind === 'added' ? 'hint-added' : 'hint-removed'">
                {{ emptyHint[row.kind] }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-if="diff.psus?.length">
        <h4 class="section-title">电源</h4>
        <el-table :data="diff.psus" border size="small">
          <el-table-column resizable label="SN" :min-width="diffWidths.psus.serial_number" show-overflow-tooltip>
            <template #default="{ row }">{{ ident(row, ['manufacturer', 'model'], 'serial_number', 'SN') }}</template>
          </el-table-column>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">
                {{ kindLabel[row.kind] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column resizable label="变化" :min-width="diffWidths.psus.changes" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="change-line mono">
                <span class="old-val">{{ fmtValue(c.field, c.old) }}</span>
                <span class="arrow">→</span>
                <span class="new-val">{{ fmtValue(c.field, c.new) }}</span>
              </div>
              <span v-if="!row.changes.length" :class="row.kind === 'added' ? 'hint-added' : 'hint-removed'">
                {{ emptyHint[row.kind] }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-if="diff.gpus?.length">
        <h4 class="section-title">GPU</h4>
        <el-table :data="diff.gpus" border size="small">
          <el-table-column resizable label="UUID" :min-width="diffWidths.gpus.uuid" show-overflow-tooltip>
            <template #default="{ row }">{{ ident(row, ['name'], 'uuid', 'UUID') }}</template>
          </el-table-column>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">
                {{ kindLabel[row.kind] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column resizable label="变化" :min-width="diffWidths.gpus.changes" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="change-line mono">
                <span class="old-val">{{ fmtValue(c.field, c.old) }}</span>
                <span class="arrow">→</span>
                <span class="new-val">{{ fmtValue(c.field, c.new) }}</span>
              </div>
              <span v-if="!row.changes.length" :class="row.kind === 'added' ? 'hint-added' : 'hint-removed'">
                {{ emptyHint[row.kind] }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </template>
    <el-empty v-else description="该记录无 diff 详情(历史数据)" :image-size="60" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { PendingChange } from '../api'
import { fitMinWidths, longestLine, FitCol } from '../utils/fit'
import { fieldLabel, fmtValue } from '../utils/diff'

const props = defineProps<{
  diff: PendingChange['diff'] | null
}>()

// Column width auto-fit: compute min-width from the longest content per column, fully visible by default
type DiffEntry = { kind: string; changes?: { field: string; old: unknown; new: unknown }[] }
const diffWidths = computed(() => {
  const d = props.diff
  const changeCol: FitCol<DiffEntry> = {
    key: 'changes',
    label: '变化',
    // One change per line in the change column, the column only needs to fit the longest one
    text: (r) =>
      longestLine([...(r.changes ?? []).map((c) => changeRepr(c)), emptyHint[r.kind] ?? '-']),
  }
  const kindCol: FitCol<DiffEntry> = { key: 'kind', label: '类型' }
  return {
    fields: fitMinWidths(d?.fields ?? [], [
      { key: 'field', label: '字段' },
      { key: 'old', label: '旧值(库中)' },
      { key: 'new', label: '新值(推送)' },
    ]),
    nics: fitMinWidths(d?.nics ?? [], [{ key: 'name', label: '网卡' }, kindCol, changeCol]),
    memory: fitMinWidths(d?.memory ?? [], [{ key: 'slot', label: '槽位' }, kindCol, changeCol]),
    cpus: fitMinWidths(d?.cpus ?? [], [{ key: 'slot', label: '槽位' }, kindCol, changeCol]),
    disks: fitMinWidths(d?.disks ?? [], [
      { key: 'serial_number', label: 'SN' },
      kindCol,
      changeCol,
    ]),
    psus: fitMinWidths(d?.psus ?? [], [
      { key: 'serial_number', label: 'SN' },
      kindCol,
      changeCol,
    ]),
    gpus: fitMinWidths(d?.gpus ?? [], [{ key: 'uuid', label: 'UUID' }, kindCol, changeCol]),
  }
})

const kindLabel: Record<string, string> = {
  added: '新增',
  removed: '候删',
  changed: '有变化',
}
const kindTag: Record<string, string> = {
  added: 'success',
  removed: 'danger',
  changed: 'warning',
}
const emptyHint: Record<string, string> = {
  added: '新增,无字段变化',
  removed: '库中多出,裁决 new 即删除',
  changed: '-',
}

// Readable identity summary: added takes the new object, removed/changed takes the old object
// name/manufacturer/model first, SN/UUID as annotation (UUID/SN alone does not tell which hardware)
function ident(
  row: {
    kind: string
    uuid?: string
    serial_number?: string
    old: Record<string, unknown> | null
    new: Record<string, unknown> | null
  },
  names: string[],
  key: string,
  keyLabel: string,
): string {
  const o = (row.kind === 'added' ? row.new : row.old) ?? {}
  const parts = names.filter((n) => o[n]).map((n) => String(o[n]))
  const id = (row as Record<string, unknown>)[key] ?? o[key]
  return [...parts, id ? `${keyLabel}:${id}` : ''].filter(Boolean).join(' · ') || '-'
}

function changeRepr(c: { field: string; old: unknown; new: unknown }): string {
  return `${fieldLabel(c.field)}: ${fmtValue(c.field, c.old)} -> ${fmtValue(c.field, c.new)}`
}
</script>

<style scoped>
.diff-detail {
  padding: 8px 16px;
}
.section-title {
  margin: 8px 0;
}
.change-line {
  padding: 1px 0;
  font-size: 12px;
}
.mono {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}
.old-val {
  color: var(--el-color-danger);
  background: #fef0f0;
  text-decoration: line-through;
  padding: 0 4px;
  border-radius: 3px;
}
.new-val {
  color: var(--el-color-success);
  background: #f0f9eb;
  padding: 0 4px;
  border-radius: 3px;
}
.arrow {
  color: var(--el-text-color-secondary);
  margin: 0 2px;
}
.hint-added {
  color: var(--el-color-success);
}
.hint-removed {
  color: var(--el-color-danger);
}
</style>
