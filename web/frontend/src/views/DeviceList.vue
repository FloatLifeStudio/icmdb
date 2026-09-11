<template>
  <div>
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索 hostname / 序列号 / IP(反查)"
        clearable
        class="search"
        @input="load"
      />
      <el-select
        v-model="statusFilter"
        placeholder="状态"
        clearable
        class="filter"
        @change="load"
      >
        <el-option label="活跃" value="active" />
        <el-option label="疑似下线" value="suspected_offline" />
      </el-select>
      <el-input
        v-model="tagFilter"
        placeholder="按标签筛选(如:生产)"
        clearable
        class="filter"
        @input="load"
      />
      <el-button type="primary" @click="load">刷新</el-button>
      <el-button @click="exportCsv">导出 CSV</el-button>
      <el-upload
        :show-file-list="false"
        :auto-upload="false"
        accept=".csv"
        :on-change="importCsv"
      >
        <el-button>导入 CSV</el-button>
      </el-upload>
      <el-popconfirm
        title="确认批量删除选中的设备?(连带网卡数据,历史保留)"
        @confirm="batchRemove"
      >
        <template #reference>
          <el-button type="danger" :disabled="!selected.length">批量删除</el-button>
        </template>
      </el-popconfirm>
    </div>

    <el-table
      :data="items"
      v-loading="loading"
      border
      stripe
      @sort-change="onSortChange"
      @selection-change="onSelectionChange"
    >
      <el-table-column type="selection" width="45" />
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="hostname" label="Hostname" min-width="180" sortable="custom">
        <template #default="{ row }">
          <router-link :to="`/devices/${row.id}`" class="link">
            {{ row.hostname }}
          </router-link>
        </template>
      </el-table-column>
      <el-table-column prop="serial_number" label="序列号" min-width="140" sortable="custom" />
      <el-table-column prop="mgmt_ip" label="管理 IP" min-width="130" sortable="custom" />
      <el-table-column label="标签" min-width="120">
        <template #default="{ row }">
          <el-tag v-for="t in row.tags" :key="t" size="small" class="tag">
            {{ t }}
          </el-tag>
          <span v-if="!row.tags.length">-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'warning'">
            {{ row.status === 'active' ? '活跃' : '疑似下线' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_pushed_at" label="上次推送" min-width="170" sortable="custom">
        <template #default="{ row }">{{ fmt(row.last_pushed_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-popconfirm
            title="确认删除该设备?(连带网卡数据,历史保留)"
            @confirm="remove(row.id)"
          >
            <template #reference>
              <el-button type="danger" link size="small">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :page-sizes="[10, 20, 50, 100, 500, 1000]"
      :total="total"
      layout="total, sizes, prev, pager, next"
      class="pagination"
      @current-change="load"
      @size-change="page = 1; load()"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, DeviceOut } from '../api'

const items = ref<DeviceOut[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const search = ref('')
const statusFilter = ref('')
const tagFilter = ref('')
const sortBy = ref('')
const sortOrder = ref('')
const selected = ref<DeviceOut[]>([])
const loading = ref(false)

function onSortChange({ prop, order }: { prop: string; order: string | null }) {
  if (order === null) {
    sortBy.value = ''
    sortOrder.value = ''
  } else {
    sortBy.value = prop
    sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
  }
  load()
}

function onSelectionChange(rows: DeviceOut[]) {
  selected.value = rows
}

function fmt(ts: string | null): string {
  if (!ts) return '-'
  // 后端存 naive UTC,补 Z 标记后由浏览器转换为查看者本地时区
  const utc = /[Zz]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : ts + 'Z'
  return new Date(utc).toLocaleString()
}

async function load() {
  loading.value = true
  try {
    const res = await api.listDevices({
      page: page.value,
      page_size: pageSize.value,
      search: search.value || undefined,
      status: statusFilter.value || undefined,
      tag: tagFilter.value || undefined,
      sort_by: sortBy.value || undefined,
      sort_order: sortOrder.value || undefined,
    })
    items.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

async function remove(id: number) {
  try {
    await api.deleteDevice(id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function batchRemove() {
  try {
    const res = await api.batchDelete(selected.value.map((r) => r.id))
    ElMessage.success(`已删除 ${res.deleted.length} 台设备`)
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

function exportCsv() {
  window.open(api.exportCsvUrl())
}

async function importCsv(upload: { raw: File }) {
  const fd = new FormData()
  fd.append('file', upload.raw)
  try {
    const res = await fetch(api.importCsvUrl(), { method: 'POST', body: fd })
    const body = await res.json()
    if (!res.ok) throw new Error(body.detail || res.statusText)
    ElMessage.success(
      `导入完成:新增 ${body.created},未变化 ${body.unchanged},进待裁决 ${body.diff_created}`
    )
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.search {
  width: 260px;
}
.filter {
  width: 170px;
}
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
.tag {
  margin-right: 4px;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
