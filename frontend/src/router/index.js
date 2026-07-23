import { createRouter, createWebHistory } from 'vue-router'
import { auth } from '../store/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录', guest: true },
  },
  {
    path: '/',
    name: 'Chat',
    component: () => import('../views/Chat.vue'),
    meta: { title: '智能问答' },
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { title: '数据看板' },
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('../views/History.vue'),
    meta: { title: '查询历史' },
  },
  {
    path: '/team',
    name: 'Team',
    component: () => import('../views/TeamManage.vue'),
    meta: { title: '团队管理' },
  },
  {
    path: '/datasource',
    name: 'DataSource',
    component: () => import('../views/DataSource.vue'),
    meta: { title: '数据源管理', adminOnly: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard
router.beforeEach((to, from, next) => {
  // Public routes (login) — allow even if logged in
  if (to.meta.guest) {
    if (auth.isLoggedIn && to.name === 'Login') {
      return next('/')
    }
    return next()
  }

  // Protected routes — require login
  if (!auth.isLoggedIn) {
    return next('/login')
  }

  // Admin-only routes
  if (to.meta.adminOnly && auth.workspace?.role !== 'admin') {
    return next('/')
  }

  next()
})

export default router
