<template>
  <div class="diff-detail">
    <template
      v-if="diff && (diff.fields.length || diff.nics.length || diff.memory?.length || diff.cpus?.length || diff.disks?.length || diff.psus?.length)"
    >
      <h4 class="section-title">主机字段</h4>
      <el-table :data="diff.fields" border size="small">
        <el-table-column prop="field" label="字段" min-width="140" />
        <el-table-column label="旧值(库中)" min-width="170">
          <template #default="{ row }">{{ row.old ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="新值(推送)" min-width="170">
          <template #default="{ row }">{{ row.new ?? '-' }}</template>
        </el-table-column>
      </el-table>

      <h4 class="section-title">网卡</h4>
      <el-table :data="diff.nics" border size="small">
        <el-table-column prop="name" label="网卡" width="110" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="kindTag[row.kind]" size="small">
              {{ kindLabel[row.kind] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="变化" min-width="280">
          <template #default="{ row }">
            <div v-for="(c, i) in row.changes" :key="i">{{ changeRepr(c) }}</div>
            <span v-if="!row.changes.length">{{ emptyHint[row.kind] }}</span>
          </template>
        </el-table-column>
      </el-table>

      <template v-if="diff.memory?.length">
        <h4 class="section-title">内存</h4>
        <el-table :data="diff.memory" border size="small">
          <el-table-column prop="slot" label="槽位" width="110" />
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">
                {{ kindLabel[row.kind] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="变化" min-width="280">
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
          <el-table-column prop="slot" label="槽位" width="110" />
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">
                {{ kindLabel[row.kind] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="变化" min-width="280">
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
          <el-table-column prop="serial_number" label="SN" width="130" />
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">
                {{ kindLabel[row.kind] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="变化" min-width="280">
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
          <el-table-column prop="serial_number" label="SN" width="130" />
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">
                {{ kindLabel[row.kind] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="变化" min-width="280">
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
import { FieldDiff } from '../api'

defineProps<{
  diff: {
    fields: FieldDiff[]
    nics: unknown[]
    memory?: unknown[]
    cpus?: unknown[]
    disks?: unknown[]
    psus?: unknown[]
  } | null
}>()

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
