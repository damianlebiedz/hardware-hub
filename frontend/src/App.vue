<template>
  <div>
    <!-- Navigation — only shown when logged in -->
    <nav v-if="user" class="navbar">
      <div class="navbar-inner">
        <RouterLink to="/dashboard" class="navbar-brand">⚙ Hardware Hub</RouterLink>
        <div class="navbar-links">
          <RouterLink to="/dashboard"  class="nav-link">Dashboard</RouterLink>
          <RouterLink to="/my-rentals" class="nav-link">My Rentals</RouterLink>
          <RouterLink v-if="user.role === 'admin'" to="/admin" class="nav-link">Admin</RouterLink>
          <span class="navbar-user">{{ user.email }}</span>
          <button class="btn btn-ghost btn-sm" @click="logout">Sign out</button>
        </div>
      </div>
    </nav>

    <RouterView />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, RouterLink, RouterView } from 'vue-router'
import { getStoredUser } from './api/client.js'

const router = useRouter()
const user = ref(getStoredUser())

// Keep user ref in sync when it changes (e.g. after login)
onMounted(() => {
  // Re-read whenever the storage event fires (cross-tab) or the route changes
  router.afterEach(() => { user.value = getStoredUser() })
})

function logout() {
  localStorage.removeItem('hardware_hub_user')
  user.value = null
  router.push('/login')
}
</script>
