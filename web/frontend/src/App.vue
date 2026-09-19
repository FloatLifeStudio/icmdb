<template>
  <el-container v-if="$route.path === '/login'" class="bare">
    <router-view />
  </el-container>
  <el-container v-else class="layout">
    <el-aside width="200px" class="aside">
      <div class="logo" title="回到首页" @click="$router.push('/dashboard')">CMDB</div>
      <el-menu router :default-active="$route.path" class="menu">
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>仪表盘
        </el-menu-item>
        <el-menu-item index="/devices">
          <el-icon><Monitor /></el-icon>资产列表
        </el-menu-item>
        <el-menu-item index="/conflicts">
          <el-icon><EditPen /></el-icon>
          <span>冲突裁决</span>
          <span v-if="pendingCount" class="pending-count">
            {{ pendingCount > 99 ? '99+' : pendingCount }}
          </span>
        </el-menu-item>
        <el-menu-item v-if="role === 'admin'" index="/users">
          <el-icon><User /></el-icon>用户管理
        </el-menu-item>
        <el-menu-item v-if="role === 'admin'" index="/settings">
          <el-icon><Setting /></el-icon>系统设置
        </el-menu-item>
      </el-menu>
      <div class="user">
        <span class="username">{{ username }}</span>
        <el-button link type="primary" @click="openChangePassword">修改密码</el-button>
        <el-button link type="primary" @click="logout">退出</el-button>
      </div>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>

    <el-dialog v-model="pwdVisible" title="修改密码" width="400px">
      <el-form label-width="80px">
        <el-form-item label="原密码">
          <el-input v-model="pwdForm.old" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwdForm.new" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="pwdForm.confirm" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" @click="changePassword">确认修改</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<style>
/* 全局重置:去掉浏览器默认 8px 外边距(登录页渐变贴边,主布局撑满) */
body {
  margin: 0;
}
</style>

<script setup lang="ts">
import { provide, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import { Monitor, EditPen, Odometer, Setting, User } from '@element-plus/icons-vue'
import { api } from './api'

const route = useRoute()
const pendingCount = ref(0)
const username = ref('')
const role = ref('viewer')

// 待裁决数量气泡:进入应用、切换页面时刷新(裁决提交后由 ConflictResolve 调 loadPendingCount)
async function loadPendingCount() {
  try {
    const res = await api.dashboard()
    pendingCount.value = res.pending_changes
  } catch {
    // 静默失败,不影响页面使用
  }
}

// 当前登录用户与角色;未登录静默
async function loadUsername() {
  try {
    const res = await api.me()
    username.value = res.username
    role.value = res.role
  } catch {
    // 静默失败
  }
}

async function logout() {
  try {
    await api.logout()
  } finally {
    window.location.href = '/login'
  }
}

// 修改自己的密码(所有角色可用)
const pwdVisible = ref(false)
const pwdForm = ref({ old: '', new: '', confirm: '' })

function openChangePassword() {
  pwdForm.value = { old: '', new: '', confirm: '' }
  pwdVisible.value = true
}

async function changePassword() {
  if (!pwdForm.value.old || !pwdForm.value.new) {
    ElMessage.warning('请填写原密码和新密码')
    return
  }
  if (pwdForm.value.new !== pwdForm.value.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  try {
    await api.changePassword(pwdForm.value.old, pwdForm.value.new)
    pwdVisible.value = false
    ElMessage.success('密码已修改')
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

watch(() => route.path, loadPendingCount)
loadPendingCount()
loadUsername()
provide('refreshPendingCount', loadPendingCount)
provide('userRole', role)
</script>

<style scoped>
.layout {
  min-height: 100vh;
}
.aside {
  position: relative;
  border-right: 1px solid var(--el-border-color-light);
}
.logo {
  font-size: 20px;
  font-weight: bold;
  padding: 20px 16px;
  cursor: pointer;
}
.menu {
  border-right: none;
}
.menu-item-label {
  flex: 1;
}
.pending-count {
  margin-left: 6px;
  background: var(--el-color-danger);
  color: #fff;
  border-radius: 9px;
  padding: 0 6px;
  font-size: 12px;
  line-height: 18px;
  height: 18px;
  flex-shrink: 0;
}
.main {
  background: var(--el-bg-color-page);
}
.bare {
  min-height: 100vh;
  display: block;
}
.user {
  position: absolute;
  bottom: 16px;
  left: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.username {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
