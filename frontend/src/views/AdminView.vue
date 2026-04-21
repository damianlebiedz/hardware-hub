<template>
  <div class="page">
    <h1>Admin Panel</h1>
    <p class="text-muted mt-1">Manage users and import legacy hardware data.</p>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:1.5rem; margin-top:1.5rem;">

      <!-- ── Add User ────────────────────────────────────────────────────────── -->
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

      <!-- ── AI Seed Import ──────────────────────────────────────────────────── -->
      <div class="card ai-seed-card">

        <!-- Header -->
        <h2>AI Seed Import</h2>
        <p class="text-muted mt-1" style="margin-bottom:.75rem; font-size:.85rem;">
          Upload a legacy JSON file and send it through the Gemini AI sanitizer
          to bulk-insert cleaned records into the database.
        </p>

        <!-- File picker -->
        <div class="form-group" style="margin-bottom:.75rem;">
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

        <!-- Ready banner -->
        <div v-if="seedRecordCount > 0 && !seedChanges.length"
             class="alert alert-info"
             style="margin-bottom:.75rem; font-size:.82rem;">
          <strong>{{ seedRecordCount }} record{{ seedRecordCount !== 1 ? 's' : '' }}</strong>
          from <strong>{{ seedFileName }}</strong> ready — AI will clean typos, dates
          and statuses before inserting.
        </div>

        <div v-if="seedError" class="alert alert-error" style="margin-bottom:.75rem;">{{ seedError }}</div>

        <!-- Action row: AI import + preview trigger -->
        <div style="display:flex; gap:.5rem; align-items:center; flex-wrap:wrap;">
          <button class="btn btn-primary" :disabled="seedLoading || seedRecordCount === 0" @click="handleSeedImport">
            <span v-if="seedLoading" class="spinner"></span>
            {{ seedLoading ? 'Importing via AI…' : '⚡ Run AI Seed Import' }}
          </button>
          <button
            v-if="seedRecordCount > 0 && !seedChanges.length"
            class="btn btn-ghost btn-sm preview-btn"
            @click="showPreviewModal = true"
          >
            Show raw data preview
          </button>
        </div>

        <!-- AI corrections diff panel -->
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

        <!-- ── Plain Seed bar ────────────────────────────────────────────────── -->
        <div class="plain-seed-bar">
          <div class="plain-seed-bar-top">
            <div class="plain-seed-bar-label">
              <strong style="font-size:.82rem;">
                Seed Import <span class="text-muted" style="font-weight:400;">(without AI)</span>
              </strong>
              <p class="text-muted" style="font-size:.72rem; margin:.15rem 0 0; line-height:1.35;">
                Seed must be valid — records with missing or invalid fields are skipped and listed below.
              </p>
            </div>
            <div class="plain-seed-bar-actions">
              <input
                id="plain-seed-file"
                type="file"
                class="input plain-seed-input"
                accept=".json,application/json"
                :disabled="plainSeedLoading"
                @change="handlePlainSeedFileChange"
              />
              <button
                class="btn btn-ghost btn-sm"
                style="white-space:nowrap;"
                :disabled="plainSeedLoading || plainSeedRecordCount === 0"
                @click="handlePlainSeed"
              >
                <span v-if="plainSeedLoading" class="spinner" style="width:12px;height:12px;"></span>
                {{ plainSeedLoading ? 'Importing…' : 'Import' }}
              </button>
            </div>
          </div>

          <div v-if="plainSeedError" class="alert alert-error" style="margin-top:.5rem; font-size:.78rem;">
            {{ plainSeedError }}
          </div>

          <div v-if="plainSeedResult" style="margin-top:.5rem;">
            <div
              class="alert"
              :class="plainSeedResult.rejected.length ? 'alert-warning' : 'alert-success'"
              style="font-size:.78rem; margin-bottom:0;"
            >
              Inserted <strong>{{ plainSeedResult.inserted }}</strong> record{{ plainSeedResult.inserted !== 1 ? 's' : '' }}.
              <span v-if="plainSeedResult.rejected.length">
                <strong>{{ plainSeedResult.rejected.length }}</strong>
                record{{ plainSeedResult.rejected.length !== 1 ? 's' : '' }} skipped due to invalid data.
              </span>
            </div>

            <div v-if="plainSeedResult.rejected.length" class="rejected-list">
              <div class="rejected-list-title">Skipped records:</div>
              <div
                v-for="rej in plainSeedResult.rejected"
                :key="rej.index"
                class="rejected-item"
              >
                <span class="rejected-index">#{{ rej.index + 1 }}</span>
                <span class="rejected-name">{{ recordLabel(rej.record) }}</span>
                <span class="rejected-reason">{{ firstLine(rej.reason) }}</span>
              </div>
            </div>
          </div>
        </div>

      </div><!-- /.card -->

    </div>
  </div>

  <!-- ── Raw data preview modal ──────────────────────────────────────────────── -->
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="showPreviewModal"
        class="modal-backdrop"
        @click.self="showPreviewModal = false"
      >
        <div class="modal-cloud" role="dialog" aria-modal="true" aria-label="Raw data preview">
          <div class="modal-cloud-header">
            <span>Raw data preview — {{ seedRecordCount }} record{{ seedRecordCount !== 1 ? 's' : '' }}</span>
            <button class="toast-close" @click="showPreviewModal = false" aria-label="Close">×</button>
          </div>
          <pre class="modal-cloud-body">{{ JSON.stringify(seedPayload, null, 2) }}</pre>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- ── Toast notification ─────────────────────────────────────────────────── -->
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
import { createUser, aiSeed, plainSeed } from '../api/client.js'

const router = useRouter()

// ── Add user state ──────────────────────────────────────────────────────────
const newEmail    = ref('')
const newPassword = ref('')
const userLoading = ref(false)
const userError   = ref('')
const userSuccess = ref('')

async function handleCreateUser() {
  userError.value = userSuccess.value = ''
  userLoading.value = true
  try {
    const user = await createUser(newEmail.value.trim(), newPassword.value)
    userSuccess.value = `User "${user.email}" created.`
    newEmail.value = ''
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
const seedChanges     = ref([])
const showPreviewModal = ref(false)

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

async function handleSeedFileChange(event) {
  seedError.value = ''
  seedPayload.value = []
  seedRecordCount.value = 0
  seedFileName.value = ''
  seedChanges.value = []
  expandedDiffs.clear()
  showPreviewModal.value = false

  const file = event.target.files?.[0]
  if (!file) return

  try {
    const rawText = await file.text()
    const parsed = JSON.parse(rawText)
    if (!Array.isArray(parsed)) throw new Error('Seed file must contain a JSON array.')
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

// ── Plain Seed state ────────────────────────────────────────────────────────
const plainSeedLoading     = ref(false)
const plainSeedError       = ref('')
const plainSeedPayload     = ref([])
const plainSeedRecordCount = ref(0)
const plainSeedResult      = ref(null)  // { inserted, items, rejected }

async function handlePlainSeedFileChange(event) {
  plainSeedError.value = ''
  plainSeedPayload.value = []
  plainSeedRecordCount.value = 0
  plainSeedResult.value = null

  const file = event.target.files?.[0]
  if (!file) return

  try {
    const rawText = await file.text()
    const parsed = JSON.parse(rawText)
    if (!Array.isArray(parsed)) throw new Error('Seed file must contain a JSON array.')
    plainSeedPayload.value = parsed
    plainSeedRecordCount.value = parsed.length
  } catch (err) {
    plainSeedError.value = err.message || 'Failed to parse JSON file.'
  }
}

async function handlePlainSeed() {
  plainSeedError.value = ''
  plainSeedResult.value = null

  if (plainSeedRecordCount.value === 0) {
    plainSeedError.value = 'Upload a JSON file with at least one record first.'
    return
  }
  plainSeedLoading.value = true
  try {
    const result = await plainSeed(plainSeedPayload.value)
    plainSeedResult.value = result
  } catch (err) {
    plainSeedError.value = err.message || 'Seed import failed.'
  } finally {
    plainSeedLoading.value = false
  }
}

function recordLabel(record) {
  if (!record || typeof record !== 'object') return ''
  return record.name ?? record.id ?? ''
}

function firstLine(reason) {
  return (reason ?? '').split('\n')[0].replace(/^.*?:\s*/, '').trim()
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
</script>

<style scoped>
/* ── AI seed card ─────────────────────────────────────────────────────────── */
.ai-seed-card {
  display: flex;
  flex-direction: column;
}

.preview-btn {
  font-size: .78rem;
  opacity: .8;
}
.preview-btn:hover {
  opacity: 1;
}

/* ── Plain Seed bar ───────────────────────────────────────────────────────── */
.plain-seed-bar {
  margin-top: auto;
  padding-top: .9rem;
  margin-top: .9rem;
  border-top: 1px solid var(--border);
}

.plain-seed-bar-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: .75rem;
  flex-wrap: wrap;
}

.plain-seed-bar-label {
  flex: 1;
  min-width: 0;
}

.plain-seed-bar-actions {
  display: flex;
  align-items: center;
  gap: .4rem;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.plain-seed-input {
  font-size: .75rem;
  width: auto;
  max-width: 180px;
  padding: .25rem .4rem;
  height: auto;
}

/* ── Alert warning ────────────────────────────────────────────────────────── */
.alert-warning {
  background: rgba(234, 179, 8, .1);
  border: 1px solid rgba(234, 179, 8, .35);
  color: #92700a;
}

/* ── Rejected list ────────────────────────────────────────────────────────── */
.rejected-list {
  margin-top: .4rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  font-size: .72rem;
}

.rejected-list-title {
  padding: .3rem .6rem;
  background: var(--bg);
  font-weight: 600;
  border-bottom: 1px solid var(--border);
  color: var(--text-muted, #6b7280);
}

.rejected-item {
  display: flex;
  align-items: baseline;
  gap: .4rem;
  padding: .3rem .6rem;
  border-bottom: 1px solid var(--border);
}
.rejected-item:last-child {
  border-bottom: none;
}

.rejected-index {
  font-weight: 600;
  color: var(--text-muted, #6b7280);
  flex-shrink: 0;
  min-width: 2rem;
}

.rejected-name {
  font-weight: 500;
  flex-shrink: 0;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rejected-reason {
  color: #dc2626;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Preview modal ────────────────────────────────────────────────────────── */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, .45);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}

.modal-cloud {
  background: var(--card, #fff);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 12px 48px rgba(0, 0, 0, .22);
  max-width: 700px;
  width: 100%;
  max-height: 78vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-cloud-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: .7rem 1rem;
  border-bottom: 1px solid var(--border);
  font-size: .8rem;
  font-weight: 600;
  flex-shrink: 0;
}

.modal-cloud-body {
  font-size: .72rem;
  line-height: 1.5;
  overflow: auto;
  padding: .75rem 1rem;
  margin: 0;
  background: var(--bg, #f9fafb);
  flex: 1;
}

/* Modal transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity .15s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
