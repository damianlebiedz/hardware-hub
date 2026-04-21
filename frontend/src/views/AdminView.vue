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
          Send the bundled legacy dataset through the Gemini AI sanitizer and
          bulk-insert the cleaned records into the database.
        </p>

        <div class="alert alert-info" style="margin-bottom:1rem;">
          <strong>{{ SEED_DATA.length }} records</strong> will be sent to Gemini
          for cleaning (typo correction, date normalisation, status mapping,
          duplicate ID resolution) then inserted into the hardware table.
        </div>

        <div v-if="seedError"   class="alert alert-error">{{ seedError }}</div>
        <div v-if="seedSuccess" class="alert alert-success">{{ seedSuccess }}</div>

        <button class="btn btn-primary" :disabled="seedLoading" @click="handleSeedImport">
          <span v-if="seedLoading" class="spinner"></span>
          {{ seedLoading ? 'Importing via AI…' : '⚡ Run AI Seed Import' }}
        </button>

        <!-- Preview of raw data that will be sent -->
        <details style="margin-top:1rem;">
          <summary class="text-muted" style="cursor:pointer; font-size:.8rem;">
            Show raw data preview
          </summary>
          <pre style="font-size:.72rem; overflow:auto; max-height:220px; margin-top:.5rem;
                      background:var(--bg); padding:.75rem; border-radius:var(--radius);
                      border:1px solid var(--border);">{{ JSON.stringify(SEED_DATA, null, 2) }}</pre>
        </details>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { createUser, aiSeed } from '../api/client.js'

// ── Hardcoded raw legacy dataset (sent as-is to the AI sanitizer) ──────────
const SEED_DATA = [
  { id: 1,  name: 'Apple iPhone 13 Pro Max',  brand: 'Apple',   purchaseDate: '2021-11-23', status: 'Available' },
  { id: 2,  name: 'Apple MacBook Pro 13',      brand: 'Apple',   purchaseDate: '2021-12-20', status: 'In Use' },
  { id: 3,  name: 'Razer Basilisk V2',         brand: 'Razer',   purchaseDate: '2021-06-05', status: 'Repair' },
  { id: 4,  name: 'SAMSUNG Galaxy S21',        brand: 'Samsung', purchaseDate: '2021-11-23', status: 'Available' },
  { id: 5,  name: 'Dell XPS 15 9510',          brand: 'Dell',    purchaseDate: '2022-03-15', status: 'Available', notes: 'Battery swelling, do not issue without service.' },
  { id: 6,  name: 'Logitech MX Master 3',      brand: 'Logitech',purchaseDate: '2027-10-10', status: 'Available' },
  { id: 7,  name: 'Sony WH-1000XM4',           brand: 'Sony',    purchaseDate: '2022-01-12', status: 'In Use',   assignedTo: 'j.doe@booksy.com' },
  { id: 4,  name: 'Duplicate ID Test Laptop',  brand: 'Lenovo',  purchaseDate: '2023-01-01', status: 'Repair' },
  { id: 9,  name: 'iPad Pro 12.9',             brand: 'Appel',   purchaseDate: '22-05-2023', status: 'Available' },
  { id: 10, name: 'Unknown Device',            brand: '',        purchaseDate: null,         status: 'Unknown' },
  { id: 11, name: 'MacBook Air M2',            brand: 'Apple',   purchaseDate: '2023-08-01', status: 'Available', history: 'Returned by user with liquid damage. Keyboard sticky.' },
]

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

async function handleSeedImport() {
  seedError.value = seedSuccess.value = ''
  seedLoading.value = true
  try {
    const result = await aiSeed(SEED_DATA)
    seedSuccess.value = `✓ Inserted ${result.inserted} record(s) after AI sanitization.`
  } catch (err) {
    seedError.value = err.message || 'AI seed import failed.'
  } finally {
    seedLoading.value = false
  }
}
</script>
