<template>
  <div class="login-page">
    <div class="card login-card">
      <div class="login-header">
        <div class="login-logo">⚙</div>
        <h1>Hardware Hub</h1>
        <p class="text-muted mt-1">Sign in to manage company equipment</p>
      </div>

      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label for="email">Email address</label>
          <input
            id="email"
            v-model="email"
            type="email"
            class="input"
            placeholder="you@company.com"
            required
            autocomplete="email"
          />
        </div>

        <div v-if="error" class="alert alert-error mt-2">{{ error }}</div>

        <button type="submit" class="btn btn-primary w-full mt-2" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? 'Signing in…' : 'Sign in' }}
        </button>
      </form>

      <p class="text-muted mt-2" style="font-size:.75rem; text-align:center;">
        MVP mode — no password required.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../api/client.js'

const router  = useRouter()
const email   = ref('')
const loading = ref(false)
const error   = ref('')

async function handleLogin() {
  error.value   = ''
  loading.value = true
  try {
    const user = await login(email.value.trim())
    localStorage.setItem('hardware_hub_user', JSON.stringify(user))
    router.push('/dashboard')
  } catch (err) {
    error.value = err.message || 'Login failed. Check the email address.'
  } finally {
    loading.value = false
  }
}
</script>
