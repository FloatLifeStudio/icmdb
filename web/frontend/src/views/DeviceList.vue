<template>
  <div>
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="按 hostname 搜索"
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
      <el-button type="primary" @click="load">刷新</el-button>
    </div>

    <el-table :data="items" v-loading="loading" border stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="hostname" label="Hostname" min-width="180">
        <template #default="{ row }">
          <router-link :to="`/devices/${row.id}`" class="link">
            {{ row.hostname }}
          </router-link>
        </template>
      </el-table-column>
      <el-table-column prop="serial_number" label="序列号" min-width="140" />
      <el-table-column prop="mgmt_ip" label="管理 IP" min-width="130" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'warning'">
            {{ row.status === 'active' ? '活跃' : '疑似下线' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="上次推送" min-width="170">
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
      :page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      class="pagination"
      @current-change="load"
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
const pageSize = 20
const search = ref('')
const statusFilter = ref('')
const loading = ref(false)

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
      page_size: pageSize,
      search: search.value || undefined,
      status: statusFilter.value || undefined,
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

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.search {
  width: 260px;
}
.filter {
  width: 140px;
}
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
