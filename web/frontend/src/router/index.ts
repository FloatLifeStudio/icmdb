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
    { path: '/api-keys', component: () => import('../views/ApiKeys.vue') },
    { path: '/audit-logs', component: () => import('../views/AuditLog.vue') },
  ],
})

// Route guard: unauthenticated users go to the login page; user management/system settings are admin-only (session state is confirmed with the backend on each session's first navigation)
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
  if (to.path === '/users' || to.path === '/settings' || to.path === '/api-keys' || to.path === '/audit-logs') {
    try {
      const me = await api.me()
      if (me.role !== 'admin') return '/dashboard'
    } catch {
      return '/login'
    }
  }
  // API key management page requires the feature to be on (hidden from the sidebar when off)
  if (to.path === '/api-keys') {
    try {
      const s = await api.getSystemSettings()
      if (!s.api_key_enabled) return '/dashboard'
    } catch {
      return '/login'
    }
  }
  return true
})

export default router
