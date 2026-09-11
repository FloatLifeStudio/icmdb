import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/devices' },
    { path: '/devices', component: () => import('../views/DeviceList.vue') },
    { path: '/devices/:id', component: () => import('../views/DeviceDetail.vue') },
    { path: '/conflicts', component: () => import('../views/ConflictResolve.vue') },
  ],
})

export default router
