<template>
  <div class="diff-entry" :class="`is-${entry.kind}`">
    <div class="entry-head">
      <el-tag :type="kindTag[entry.kind]" size="small">{{ kindLabel[entry.kind] }}</el-tag>
      <span class="identity mono">{{ headText }}</span>
      <el-radio-group
        v-if="isAdmin && modelValue"
        size="small"
        :model-value="modelValue"
        @update:model-value="emit('update:modelValue', $event as string)"
      >
        <el-radio-button value="old">{{ oldLabel }}</el-radio-button>
        <el-radio-button value="new">{{ newLabel }}</el-radio-button>
      </el-radio-group>
    </div>
    <div class="entry-body">
      <!-- changed: red/green diff of the changed fields; identity + unchanged fields are in the head line -->
      <template v-if="entry.kind === 'changed'">
        <div v-for="c in entry.changes ?? []" :key="c.field" class="change-row">
          <span class="fname">{{ fieldLabel(c.field) }}</span>
          <span class="old-val mono">{{ fmtValue(c.field, c.old) }}</span>
          <span class="arrow">→</span>
          <span class="new-val mono">{{ fmtValue(c.field, c.new) }}</span>
        </div>
        <div v-if="!(entry.changes ?? []).length" class="change-row">
          <span class="empty">-</span>
        </div>
      </template>
      <!-- added/removed: full key-value display -->
      <template v-else>
        <div v-for="(row, i) in rows" :key="i" class="change-row">
          <span class="fname">{{ row.label }}</span>
          <span class="mono" :class="entry.kind === 'added' ? 'new-val' : 'old-val'">{{ row.value }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { fieldLabel, fmtValue, fullRows } from '../utils/diff'

type Entry = {
  kind: string
  old: unknown
  new: unknown
  changes?: { field: string; old: unknown; new: unknown }[]
}

const props = defineProps<{
  entry: Entry
  // Entry identity (NIC name/slot/SN/UUID), shown in the entry header
  identity: string
  // Category noun (NIC/memory/CPU...), used in keep/adopt wording
  noun: string
  // Resolution choice old/new (v-model); hidden when undefined (entries without identity)
  modelValue?: string
  isAdmin?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

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

const oldLabel = computed(() => {
  if (props.entry.kind === 'added') return '丢弃(不新增)'
  if (props.entry.kind === 'removed') return '保留(不删除)'
  return '保留旧值'
})
const newLabel = computed(() => {
  if (props.entry.kind === 'added') return `新增该${props.noun}`
  if (props.entry.kind === 'removed') return `删除该${props.noun}`
  return '采用新值'
})

const rows = computed(() =>
  fullRows((props.entry.kind === 'added' ? props.entry.new : props.entry.old) as Record<string, unknown> | null)
)

// Identity context of a changed entry: unchanged fields from the old object (SN/manufacturer/model etc)
// shown in the head line after the kind tag, used to confirm "a change to the same hardware"
const contextRows = computed(() => {
  if (props.entry.kind !== 'changed') return []
  const changedFields = new Set((props.entry.changes ?? []).map((c) => c.field))
  return fullRows(props.entry.old as Record<string, unknown> | null).filter(
    (r) => !changedFields.has(r.key),
  )
})

// Head line text: identity + unchanged context in one line for changed entries, bare identity otherwise
const headText = computed(() => {
  const rows = contextRows.value
  return rows.length ? rows.map((r) => r.value).join(' · ') : props.identity
})
</script>

<style scoped>
.diff-entry {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  margin-bottom: 10px;
  overflow: hidden;
}
.entry-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--el-fill-color-light);
}
.identity {
  font-weight: bold;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.entry-body {
  padding: 10px 16px 12px;
}
.is-added .entry-body {
  background: #f0f9eb;
}
.is-removed .entry-body {
  background: #fef0f0;
}
.change-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 3px 4px;
  font-size: 13px;
}
.fname {
  flex-shrink: 0;
  width: 72px;
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
.empty {
  color: var(--el-text-color-secondary);
}
</style>
