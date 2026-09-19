<template>
  <div class="login-page">
    <el-card class="login-card">
      <div class="logo-row">
        <span class="logo-mark">C</span>
        <span class="logo-text">CMDB</span>
      </div>
      <p class="subtitle">资产配置管理系统</p>
      <el-form label-position="top" @keyup.enter="submit">
        <el-form-item label="用户名">
          <el-input v-model="username" placeholder="请输入用户名" autofocus />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-button
          type="primary"
          class="submit"
          :loading="loading"
          @click="submit"
        >
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)

async function submit() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await api.login(username.value, password.value)
    router.push('/dashboard')
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* Light Element Plus style consistent with the dashboard */
.login-page {
  width: 100%;
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: linear-gradient(180deg, #eef4fb 0%, var(--el-bg-color-page) 100%);
}

.login-card {
  width: 360px;
  border-radius: 10px;
  box-shadow: var(--el-box-shadow-light);
}

.logo-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.logo-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 8px;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 22px;
  font-weight: bold;
}
.logo-text {
  font-size: 24px;
  font-weight: bold;
  color: var(--el-text-color-primary);
  letter-spacing: 1px;
}
.subtitle {
  margin: 10px 0 8px;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.submit {
  width: 100%;
  margin-top: 6px;
}
</style>
