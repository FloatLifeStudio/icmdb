<template>
  <div class="diff-entry" :class="`is-${entry.kind}`">
    <div class="entry-head">
      <el-tag :type="kindTag[entry.kind]" size="small">{{ kindLabel[entry.kind] }}</el-tag>
      <span class="identity mono">{{ identity }}</span>
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
      <!-- changed:只展示变化的字段,旧值浅红删除线 -> 新值浅绿 -->
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
      <!-- added/removed:整条键值对展示 -->
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
  // 条目身份(网卡名/槽位/SN/UUID),条目头展示
  identity: string
  // 类别名(网卡/内存/CPU...),用于采用/保留文案
  noun: string
  // 裁决选择 old/new(v-model);undefined 时隐藏(无身份条目)
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
  padding: 8px 12px;
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
  padding: 6px 12px;
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
