<template>
  <div v-loading="loading">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <el-button type="primary" size="small" @click="openCreate">新增用户</el-button>
        </div>
      </template>
      <el-table :data="users" border>
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ row.role === 'admin' ? '管理员' : '只读' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="160">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="openReset(row)">重置密码</el-button>
            <el-button
              size="small"
              :type="row.role === 'admin' ? 'warning' : 'primary'"
              @click="toggleRole(row)"
            >
              {{ row.role === 'admin' ? '降为只读' : '升为管理员' }}
            </el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p class="hint">管理员可操作(裁决 / 删除 / 标签 / 用户管理);只读用户仅可查看。</p>
    </el-card>

    <el-dialog v-model="createVisible" title="新增用户" width="400px">
      <el-form label-width="70px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="form.role">
            <el-radio value="viewer">只读</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetVisible" title="重置密码" width="400px">
      <el-input v-model="newPassword" placeholder="新密码" />
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" @click="reset">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, UserInfo } from '../api'

const users = ref<UserInfo[]>([])
const loading = ref(false)
const createVisible = ref(false)
const resetVisible = ref(false)
const resetTarget = ref<UserInfo | null>(null)
const newPassword = ref('')
const form = ref({ username: '', password: '', role: 'viewer' })

function fmt(ts: string): string {
  const utc = /[Zz]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : ts + 'Z'
  return new Date(utc).toLocaleString()
}

async function load() {
  loading.value = true
  try {
    users.value = (await api.listUsers()).items
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = { username: '', password: '', role: 'viewer' }
  createVisible.value = true
}

async function create() {
  if (!form.value.username.trim() || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  try {
    await api.createUser(form.value)
    createVisible.value = false
    ElMessage.success('用户已创建')
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

function openReset(user: UserInfo) {
  resetTarget.value = user
  newPassword.value = ''
  resetVisible.value = true
}

async function reset() {
  if (!resetTarget.value || !newPassword.value) {
    ElMessage.warning('请输入新密码')
    return
  }
  try {
    await api.updateUser(resetTarget.value.id, { password: newPassword.value })
    resetVisible.value = false
    ElMessage.success('密码已重置')
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function toggleRole(user: UserInfo) {
  const target = user.role === 'admin' ? 'viewer' : 'admin'
  try {
    await ElMessageBox.confirm(
      `确定将用户 ${user.username} ${target === 'admin' ? '升为管理员' : '降为只读'}?`,
      '确认',
    )
    await api.updateUser(user.id, { role: target })
    ElMessage.success('角色已更新')
    await load()
  } catch (e) {
    if ((e as Error).message) ElMessage.error((e as Error).message)
  }
}

async function remove(user: UserInfo) {
  try {
    await ElMessageBox.confirm(`确定删除用户 ${user.username}?`, '确认', {
      type: 'warning',
    })
    await api.deleteUser(user.id)
    ElMessage.success('用户已删除')
    await load()
  } catch (e) {
    if ((e as Error).message) ElMessage.error((e as Error).message)
  }
}

onMounted(load)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.hint {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
