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
      </el-menu>
      <div class="user">
        <span class="username">{{ username }}</span>
        <el-button link type="primary" @click="logout">退出</el-button>
      </div>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>
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
import { useRoute } from 'vue-router'
import { Monitor, EditPen, Odometer, User } from '@element-plus/icons-vue'
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
