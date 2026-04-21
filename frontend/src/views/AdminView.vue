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

        <div v-if="seedRecordCount > 0 && !seedChanges.length" class="alert alert-info" style="margin-bottom:1rem;">
          <strong>{{ seedRecordCount }} records</strong> from
          <strong>{{ seedFileName }}</strong> are ready to be sent to Gemini
          for cleaning (typo correction, date normalization, status mapping,
          duplicate ID resolution) then inserted into the hardware table.
        </div>

        <div v-if="seedError" class="alert alert-error">{{ seedError }}</div>

        <button class="btn btn-primary" :disabled="seedLoading || seedRecordCount === 0" @click="handleSeedImport">
          <span v-if="seedLoading" class="spinner"></span>
          {{ seedLoading ? 'Importing via AI…' : '⚡ Run AI Seed Import' }}
        </button>

        <!-- Preview of raw data that will be sent -->
        <details v-if="seedRecordCount > 0 && !seedChanges.length" style="margin-top:1rem;">
          <summary class="text-muted" style="cursor:pointer; font-size:.8rem;">
            Show raw data preview
          </summary>
          <pre style="font-size:.72rem; overflow:auto; max-height:220px; margin-top:.5rem;
                      background:var(--bg); padding:.75rem; border-radius:var(--radius);
                      border:1px solid var(--border);">{{ JSON.stringify(seedPayload, null, 2) }}</pre>
        </details>

        <!-- ── AI corrections diff panel ──────────────────────────────── -->
        <div v-if="seedChanges.length" class="diff-panel">
          <div class="diff-panel-title">
            ✏️ AI corrected {{ seedChanges.length }} record{{ seedChanges.length > 1 ? 's' : '' }}
          </div>

          <div v-for="rec in seedChanges" :key="rec.index" class="diff-record">
            <div class="diff-record-header" @click="toggleDiff(rec.index)">
              <span class="diff-record-name">{{ rec.name }}</span>
              <span class="diff-badge">
                ⚠ {{ rec.changes.length }} fix{{ rec.changes.length > 1 ? 'es' : '' }}
              </span>
              <span class="diff-chevron" :class="{ open: expandedDiffs.has(rec.index) }">▼</span>
            </div>

            <div v-if="expandedDiffs.has(rec.index)" class="diff-rows">
              <div v-for="ch in rec.changes" :key="ch.field" class="diff-row">
                <span class="diff-field">{{ fieldLabel(ch.field) }}</span>
                <span class="diff-before">{{ ch.before ?? '—' }}</span>
                <span class="diff-arrow">→</span>
                <span class="diff-after">{{ ch.after ?? '—' }}</span>
              </div>
            </div>
          </div>
        </div>

      </div>

    </div>
  </div>

  <!-- ── Toast notification ─────────────────────────────────────────────── -->
  <Transition name="toast">
    <div v-if="showToast" class="toast" role="alert">
      <div class="toast-header">
        <span class="toast-title">✓ Import successful</span>
        <button class="toast-close" @click="dismissToast" aria-label="Close">×</button>
      </div>
      <div class="toast-body">{{ toastMessage }}</div>
      <div class="toast-actions">
        <button class="btn btn-primary btn-sm" @click="goToDashboard">View in Dashboard →</button>
        <button class="btn btn-ghost btn-sm" @click="dismissToast">Dismiss</button>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { createUser, aiSeed } from '../api/client.js'

const router = useRouter()

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
const seedLoading     = ref(false)
const seedError       = ref('')
const seedPayload     = ref([])
const seedFileName    = ref('')
const seedRecordCount = ref(0)
const seedChanges     = ref([])  // SeedRecordChange[] from backend

// Diff expand/collapse state
const expandedDiffs = reactive(new Set())

function toggleDiff(index) {
  if (expandedDiffs.has(index)) {
    expandedDiffs.delete(index)
  } else {
    expandedDiffs.add(index)
  }
}

const FIELD_LABELS = {
  name:          'Name',
  brand:         'Brand',
  purchase_date: 'Date',
  status:        'Status',
  notes:         'Notes',
}
function fieldLabel(field) {
  return FIELD_LABELS[field] ?? field
}

// ── Toast state ─────────────────────────────────────────────────────────────
const showToast    = ref(false)
const toastMessage = ref('')
let toastTimer     = null

function showImportToast(message) {
  toastMessage.value = message
  showToast.value = true
  clearTimeout(toastTimer)
  toastTimer = setTimeout(dismissToast, 7000)
}

function dismissToast() {
  showToast.value = false
  clearTimeout(toastTimer)
}

function goToDashboard() {
  dismissToast()
  router.push('/dashboard')
}

// ── Handlers ────────────────────────────────────────────────────────────────
async function handleSeedFileChange(event) {
  seedError.value = ''
  seedPayload.value = []
  seedRecordCount.value = 0
  seedFileName.value = ''
  seedChanges.value = []
  expandedDiffs.clear()

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
  seedError.value = ''
  seedChanges.value = []
  expandedDiffs.clear()

  if (seedRecordCount.value === 0) {
    seedError.value = 'Upload a JSON file with at least one record first.'
    return
  }
  seedLoading.value = true
  try {
    const result = await aiSeed(seedPayload.value)
    seedChanges.value = result.changes ?? []

    // Auto-expand all changed records so the user sees them immediately
    seedChanges.value.forEach(rec => expandedDiffs.add(rec.index))

    const correctedCount = seedChanges.value.length
    const msg = correctedCount > 0
      ? `Inserted ${result.inserted} record(s). AI corrected ${correctedCount} of them — see the panel below.`
      : `Inserted ${result.inserted} record(s). All records were already clean.`
    showImportToast(msg)
  } catch (err) {
    seedError.value = err.message || 'AI seed import failed.'
  } finally {
    seedLoading.value = false
  }
}
</script>
