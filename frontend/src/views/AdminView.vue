<template>
  <div class="page">
    <h1>Admin Panel</h1>
    <p class="text-muted mt-1">Manage users and import legacy hardware data.</p>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:1.5rem; margin-top:1.5rem;">

      <!-- ── Add User ────────────────────────────────────────────────────── -->
      <div class="card">
        <h2>Add User</h2>
        <p class="text-muted mt-1" style="margin-bottom:1rem;">
          Create a new account with a password. Passwords are hashed server-side.
        </p>

        <form @submit.prevent="handleCreateUser">
          <div class="form-group">
            <label for="new-email">Email address</label>
            <input id="new-email" v-model="newEmail" type="email" class="input"
                   placeholder="user@company.com" required />
          </div>
          <div class="form-group mt-1">
            <label for="new-role">Role</label>
            <select id="new-role" v-model="newRole">
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div class="form-group mt-1">
            <label for="new-password">Temporary password</label>
            <input id="new-password" v-model="newPassword" type="password" class="input"
                   placeholder="At least 8 characters" required minlength="8" />
          </div>

          <div v-if="userError"   class="alert alert-error mt-2">{{ userError }}</div>
          <div v-if="userSuccess" class="alert alert-success mt-2">{{ userSuccess }}</div>

          <button type="submit" class="btn btn-primary mt-2" :disabled="userLoading">
            <span v-if="userLoading" class="spinner"></span>
            {{ userLoading ? 'Creating…' : 'Create user' }}
          </button>
        </form>
      </div>

      <!-- ── AI Seed Import ──────────────────────────────────────────────── -->
      <div class="card">
        <h2>AI Seed Import</h2>
        <p class="text-muted mt-1" style="margin-bottom:1rem;">
          Upload a legacy JSON file, then send it through the Gemini AI sanitizer
          to bulk-insert cleaned records into the database.
        </p>

        <div class="form-group" style="margin-bottom:1rem;">
          <label for="seed-file">Seed JSON file</label>
          <input
            id="seed-file"
            type="file"
            class="input"
            accept=".json,application/json"
            :disabled="seedLoading"
            @change="handleSeedFileChange"
          />
        </div>

        <div v-if="seedRecordCount > 0" class="alert alert-info" style="margin-bottom:1rem;">
          <strong>{{ seedRecordCount }} records</strong> from
          <strong>{{ seedFileName }}</strong> are ready to be sent to Gemini
          for cleaning (typo correction, date normalization, status mapping,
          duplicate ID resolution) then inserted into the hardware table.
        </div>

        <div v-if="seedError"   class="alert alert-error">{{ seedError }}</div>
        <div v-if="seedSuccess" class="alert alert-success">{{ seedSuccess }}</div>

        <button class="btn btn-primary" :disabled="seedLoading || seedRecordCount === 0" @click="handleSeedImport">
          <span v-if="seedLoading" class="spinner"></span>
          {{ seedLoading ? 'Importing via AI…' : '⚡ Run AI Seed Import' }}
        </button>

        <!-- Preview of raw data that will be sent -->
        <details v-if="seedRecordCount > 0" style="margin-top:1rem;">
          <summary class="text-muted" style="cursor:pointer; font-size:.8rem;">
            Show raw data preview
          </summary>
          <pre style="font-size:.72rem; overflow:auto; max-height:220px; margin-top:.5rem;
                      background:var(--bg); padding:.75rem; border-radius:var(--radius);
                      border:1px solid var(--border);">{{ JSON.stringify(seedPayload, null, 2) }}</pre>
        </details>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { createUser, aiSeed } from '../api/client.js'

// ── Add user state ──────────────────────────────────────────────────────────
const newEmail    = ref('')
const newRole     = ref('user')
const newPassword = ref('')
const userLoading = ref(false)
const userError   = ref('')
const userSuccess = ref('')

async function handleCreateUser() {
  userError.value = userSuccess.value = ''
  userLoading.value = true
  try {
    const user = await createUser(newEmail.value.trim(), newRole.value, newPassword.value)
    userSuccess.value = `User "${user.email}" created with role "${user.role}".`
    newEmail.value = ''
    newRole.value  = 'user'
    newPassword.value = ''
  } catch (err) {
    userError.value = err.message || 'Failed to create user.'
  } finally {
    userLoading.value = false
  }
}

// ── AI Seed Import state ────────────────────────────────────────────────────
const seedLoading = ref(false)
const seedError   = ref('')
const seedSuccess = ref('')
const seedPayload = ref([])
const seedFileName = ref('')
const seedRecordCount = ref(0)

async function handleSeedFileChange(event) {
  seedError.value = seedSuccess.value = ''
  seedPayload.value = []
  seedRecordCount.value = 0
  seedFileName.value = ''

  const file = event.target.files?.[0]
  if (!file) return

  try {
    const rawText = await file.text()
    const parsed = JSON.parse(rawText)
    if (!Array.isArray(parsed)) {
      throw new Error('Seed file must contain a JSON array.')
    }
    seedPayload.value = parsed
    seedRecordCount.value = parsed.length
    seedFileName.value = file.name
  } catch (err) {
    seedError.value = err.message || 'Failed to parse JSON file.'
  }
}

async function handleSeedImport() {
  seedError.value = seedSuccess.value = ''
  if (seedRecordCount.value === 0) {
    seedError.value = 'Upload a JSON file with at least one record first.'
    return
  }
  seedLoading.value = true
  try {
    const result = await aiSeed(seedPayload.value)
    seedSuccess.value = `✓ Inserted ${result.inserted} record(s) after AI sanitization.`
  } catch (err) {
    seedError.value = err.message || 'AI seed import failed.'
  } finally {
    seedLoading.value = false
  }
}
</script>
