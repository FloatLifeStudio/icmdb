<template>
  <div class="diff-detail">
    <template
      v-if="diff && (diff.fields.length || diff.nics.length || diff.memory?.length || diff.cpus?.length || diff.disks?.length || diff.psus?.length)"
    >
      <h4 class="section-title">主机字段</h4>
      <el-table :data="diff.fields" border size="small">
        <el-table-column resizable prop="field" label="字段" :min-width="diffWidths.fields.field" show-overflow-tooltip/>
        <el-table-column resizable label="旧值(库中)" :min-width="diffWidths.fields.old" show-overflow-tooltip>
          <template #default="{ row }">{{ row.old ?? '-' }}</template>
        </el-table-column>
        <el-table-column resizable label="新值(推送)" :min-width="diffWidths.fields.new" show-overflow-tooltip>
          <template #default="{ row }">{{ row.new ?? '-' }}</template>
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
            <div v-for="(c, i) in row.changes" :key="i">{{ changeRepr(c) }}</div>
            <span v-if="!row.changes.length">{{ emptyHint[row.kind] }}</span>
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
              <div v-for="(c, i) in row.changes" :key="i">{{ changeRepr(c) }}</div>
              <span v-if="!row.changes.length">{{ emptyHint[row.kind] }}</span>
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
              <div v-for="(c, i) in row.changes" :key="i">{{ changeRepr(c) }}</div>
              <span v-if="!row.changes.length">{{ emptyHint[row.kind] }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-if="diff.disks?.length">
        <h4 class="section-title">硬盘</h4>
        <el-table :data="diff.disks" border size="small">
          <el-table-column resizable prop="serial_number" label="SN" :min-width="diffWidths.disks.serial_number" show-overflow-tooltip/>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">
                {{ kindLabel[row.kind] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column resizable label="变化" :min-width="diffWidths.disks.changes" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i">{{ changeRepr(c) }}</div>
              <span v-if="!row.changes.length">{{ emptyHint[row.kind] }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-if="diff.psus?.length">
        <h4 class="section-title">电源</h4>
        <el-table :data="diff.psus" border size="small">
          <el-table-column resizable prop="serial_number" label="SN" :min-width="diffWidths.psus.serial_number" show-overflow-tooltip/>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">
                {{ kindLabel[row.kind] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column resizable label="变化" :min-width="diffWidths.psus.changes" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i">{{ changeRepr(c) }}</div>
              <span v-if="!row.changes.length">{{ emptyHint[row.kind] }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-if="diff.gpus?.length">
        <h4 class="section-title">GPU</h4>
        <el-table :data="diff.gpus" border size="small">
          <el-table-column resizable prop="uuid" label="UUID" :min-width="diffWidths.gpus.uuid" show-overflow-tooltip/>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">
                {{ kindLabel[row.kind] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column resizable label="变化" :min-width="diffWidths.gpus.changes" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i">{{ changeRepr(c) }}</div>
              <span v-if="!row.changes.length">{{ emptyHint[row.kind] }}</span>
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

const props = defineProps<{
  diff: PendingChange['diff'] | null
}>()

// 列宽自适应:按各列最长内容算 min-width,默认刚好放下、完整显示
type DiffEntry = { kind: string; changes?: { field: string; old: unknown; new: unknown }[] }
const diffWidths = computed(() => {
  const d = props.diff
  const changeCol: FitCol<DiffEntry> = {
    key: 'changes',
    label: '变化',
    // 变化列一行一条,列宽只需放下最长的一条
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

function changeRepr(c: { field: string; old: unknown; new: unknown }): string {
  if (c.field === 'ips') {
    const ips = (v: unknown) =>
      ((v as { ip: string }[]) || []).map((i) => i.ip).join(', ') || '无'
    return `${c.field}: ${ips(c.old)} -> ${ips(c.new)}`
  }
  return `${c.field}: ${c.old ?? '-'} -> ${c.new ?? '-'}`
}
</script>

<style scoped>
.diff-detail {
  padding: 8px 16px;
}
.section-title {
  margin: 8px 0;
}
</style>
