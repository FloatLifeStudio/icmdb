<template>
  <el-container class="layout">
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
          <el-icon><EditPen /></el-icon>冲突裁决
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { Monitor, EditPen, Odometer } from '@element-plus/icons-vue'
</script>

<style scoped>
.layout {
  min-height: 100vh;
}
.aside {
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
.main {
  background: var(--el-bg-color-page);
}
</style>
