<template>
  <div class="login-page">
    <div class="wrapper">
      <div class="circle circle1"></div>
      <div class="circle circle2"></div>
      <div class="circle circle3"></div>
      <div class="form">
        <h1>CMDB</h1>
        <p class="subtitle">资产配置管理系统</p>
        <form @submit.prevent="submit">
          <input
            type="text"
            v-model="username"
            placeholder="用户名"
            autocomplete="username"
          />
          <input
            type="password"
            v-model="password"
            placeholder="密码"
            autocomplete="current-password"
          />
          <button type="submit" :disabled="loading">
            {{ loading ? '登录中…' : '登录' }}
          </button>
        </form>
      </div>
    </div>
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
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: linear-gradient(to right, #12c2e9, #c471ed, #f64f59);
  overflow: hidden;
}

.wrapper {
  position: relative;
  padding: 60px;
}

/* 装饰圆:毛玻璃卡片后方呼应背景渐变 */
.circle {
  position: absolute;
  border-radius: 50%;
  filter: blur(2px);
}
.circle1 {
  height: 160px;
  width: 160px;
  background: #12c2e9;
  right: 0;
  top: 0;
  opacity: 0.9;
  animation: float1 8s ease-in-out alternate infinite;
}
.circle2 {
  height: 140px;
  width: 140px;
  background: #f64f59;
  left: 0;
  bottom: 0;
  opacity: 0.9;
  animation: float2 10s ease-in-out alternate infinite;
}
.circle3 {
  height: 56px;
  width: 56px;
  background: rgba(255, 255, 255, 0.35);
  left: 30%;
  top: -20px;
  animation: float1 6s ease-in-out alternate infinite;
}
@keyframes float1 {
  100% {
    transform: translateY(28px);
  }
}
@keyframes float2 {
  100% {
    transform: translateY(-32px);
  }
}

/* 毛玻璃卡片 */
.form {
  position: relative;
  width: 360px;
  box-sizing: border-box;
  padding: 44px 40px 40px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: 16px;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 26px 42px rgba(0, 0, 0, 0.12);
  color: #fff;
}
h1 {
  margin: 0;
  font-size: 34px;
  font-weight: 900;
  letter-spacing: 3px;
  text-align: center;
}
.subtitle {
  margin: 6px 0 28px;
  text-align: center;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.75);
  letter-spacing: 1px;
}

input,
button {
  font-size: 15px;
  display: block;
  box-sizing: border-box;
  width: 100%;
  margin: 18px auto;
  padding: 12px 18px;
  border: none;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow: 0 10px 18px rgba(0, 0, 0, 0.05);
  color: #fff;
}
input {
  transition: background 0.3s;
}
input:focus {
  outline: none;
  background: rgba(255, 255, 255, 0.2);
}
input::placeholder {
  color: rgba(255, 255, 255, 0.65);
}

button {
  cursor: pointer;
  margin-top: 26px;
  background: #f64f59;
  color: #fff;
  letter-spacing: 2px;
  transition: background 0.4s;
}
button:hover {
  background: #12c2e9;
}
button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
</style>
