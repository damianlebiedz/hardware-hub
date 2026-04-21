import { createRouter, createWebHistory } from 'vue-router'
import { getStoredUser } from '../api/client.js'

import LoginView     from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import MyRentalsView from '../views/MyRentalsView.vue'
import AdminView     from '../views/AdminView.vue'

const routes = [
  { path: '/',          redirect: '/dashboard' },
  { path: '/login',     component: LoginView,     meta: { public: true } },
  { path: '/dashboard', component: DashboardView, meta: { requiresAuth: true } },
  { path: '/my-rentals',component: MyRentalsView, meta: { requiresAuth: true } },
  { path: '/admin',     component: AdminView,     meta: { requiresAuth: true, requiresAdmin: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/** Auth guard: redirect to /login when not authenticated. */
router.beforeEach((to) => {
  const user = getStoredUser()
  if (to.meta.requiresAuth && !user)     return '/login'
  if (to.meta.requiresAdmin && user?.role !== 'admin') return '/dashboard'
  if (to.path === '/login' && user)      return '/dashboard'
  return true
})

export default router
