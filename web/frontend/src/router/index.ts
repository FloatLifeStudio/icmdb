import { createRouter, createWebHistory } from 'vue-router'
import { api } from '../api'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', component: () => import('../views/Login.vue') },
    { path: '/dashboard', component: () => import('../views/Dashboard.vue') },
    { path: '/devices', component: () => import('../views/DeviceList.vue') },
    { path: '/devices/:id', component: () => import('../views/DeviceDetail.vue') },
    { path: '/conflicts', component: () => import('../views/ConflictResolve.vue') },
    { path: '/users', component: () => import('../views/Users.vue') },
    { path: '/settings', component: () => import('../views/SystemSettings.vue') },
  ],
})

// 路由守卫:未登录跳登录页;用户管理/系统设置仅 admin(会话状态每次会话首次导航时向后端确认)
let sessionChecked = false
router.beforeEach(async (to) => {
  if (to.path === '/login') return true
  if (!sessionChecked) {
    try {
      await api.me()
      sessionChecked = true
    } catch {
      return '/login'
    }
  }
  if (to.path === '/users' || to.path === '/settings') {
    try {
      const me = await api.me()
      if (me.role !== 'admin') return '/dashboard'
    } catch {
      return '/login'
    }
  }
  return true
})

export default router
