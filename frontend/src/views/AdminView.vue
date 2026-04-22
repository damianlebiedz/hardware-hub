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

      <!-- ── Seed Importer ───────────────────────────────────────────────────── -->
      <div class="card seed-card" :class="{ 'seed-card-ai': aiMode }">

        <!-- Header -->
        <div class="seed-header">
          <div>
            <h2>Seed Importer</h2>
            <p class="text-muted" style="font-size:.85rem; margin-top:.15rem;">
              Bulk-import hardware records from a JSON file.
            </p>
          </div>
          <div class="ai-toggle-wrap">
            <label class="toggle" title="Toggle AI mode">
              <input type="checkbox" v-model="aiMode" @change="onAiModeChange" />
              <span class="toggle-slider"></span>
            </label>
            <span class="ai-toggle-label" :class="{ 'ai-toggle-label-on': aiMode }">
              AI {{ aiMode ? 'ON' : 'OFF' }}
            </span>
          </div>
        </div>

        <!-- AI mode pending proposals banner -->
        <div v-if="aiMode && hasProposals" class="proposals-banner">
          <div class="proposals-banner-info">
            <strong>{{ previewResult.total }}</strong> record{{ previewResult.total !== 1 ? 's' : '' }} pending review
            <span class="text-muted" style="font-size:.78rem;">
              · {{ correctedCount }} corrected · {{ accepted.size }} selected
            </span>
          </div>
          <div style="display:flex; gap:.4rem; flex-wrap:wrap; align-items:center;">
            <button class="btn btn-primary btn-sm" @click="showReviewOverlay = true">
              Show proposals →
            </button>
            <button class="btn btn-ghost btn-sm" @click="resetProposals" title="Discard proposals">✕ Discard</button>
          </div>
        </div>

        <!-- File picker -->
        <div class="form-group" style="margin-bottom:.75rem;">
          <label>JSON file</label>
          <input
            ref="fileInputRef"
            type="file"
            accept=".json,application/json"
            style="display:none"
            @change="handleFileChange"
          />
          <div class="file-picker">
            <button
              class="btn btn-ghost btn-sm file-picker-btn"
              :disabled="seedStep === 'previewing' || seedStep === 'importing' || (aiMode && hasProposals)"
              @click="fileInputRef.click()"
            >
              Choose file
            </button>
            <span class="file-picker-name" :class="{ 'text-muted': !seedFileName }">
              {{ seedFileName || 'No file selected' }}
            </span>
            <button
              v-if="seedFileName"
              class="btn-icon file-picker-clear"
              title="Remove file"
              @click="clearFile"
            >✕</button>
          </div>
        </div>

        <!-- Ready info -->
        <div v-if="seedRecordCount > 0 && !(aiMode && hasProposals)"
             class="alert alert-info" style="margin-bottom:.75rem; font-size:.82rem;">
          <strong>{{ seedRecordCount }} record{{ seedRecordCount !== 1 ? 's' : '' }}</strong>
          from <strong>{{ seedFileName }}</strong> ready.
        </div>

        <div v-if="seedError" class="alert alert-error" style="margin-bottom:.75rem;">{{ seedError }}</div>

        <!-- Action buttons -->
        <div style="display:flex; gap:.5rem; align-items:center; flex-wrap:wrap; margin-bottom:.75rem;">
          <!-- AI mode: Preview button (disabled while proposals pending) -->
          <button
            v-if="aiMode"
            class="btn btn-ai"
            style="height:2.25rem; justify-content:center;"
            :disabled="seedStep === 'previewing' || seedRecordCount === 0 || hasProposals"
            :title="hasProposals ? 'Review or discard current proposals first' : ''"
            @click="handlePreview"
          >
            <span v-if="seedStep === 'previewing'" class="spinner"></span>
            {{ seedStep === 'previewing' ? 'Importing…' : '⚡ Import with AI' }}
          </button>

          <!-- Non-AI mode: Import button (never blocked by results) -->
          <button
            v-else
            class="btn btn-primary"
            style="height:2.25rem; justify-content:center;"
            :disabled="seedStep === 'importing' || seedRecordCount === 0"
            @click="handlePlainImport"
          >
            <span v-if="seedStep === 'importing'" class="spinner"></span>
            {{ seedStep === 'importing' ? 'Importing…' : 'Import' }}
          </button>

          <button
            v-if="seedRecordCount > 0 && !plainSeedResult"
            class="btn btn-ghost btn-sm"
            style="font-size:.78rem; opacity:.8;"
            @click="showRawModal = true"
          >
            Show raw data
          </button>
        </div>

        <!-- Non-AI mode: rejected records banner -->
        <div v-if="!aiMode && plainSeedResult" class="proposals-banner proposals-banner-plain">
          <div class="proposals-banner-info">
            <strong>{{ plainSeedResult.inserted }}</strong> inserted
            <span v-if="plainSeedResult.rejected.length">
              · <strong>{{ plainSeedResult.rejected.length }}</strong> skipped
            </span>
            <span class="text-muted" style="font-size:.78rem;">· last import result</span>
          </div>
          <div style="display:flex; gap:.4rem; flex-wrap:wrap; align-items:center;">
            <button
              v-if="plainSeedResult.rejected.length"
              class="btn btn-ghost btn-sm"
              @click="showRejectedOverlay = true"
            >
              Show skipped →
            </button>
            <button class="btn-icon" title="Dismiss" @click="dismissPlainResult">✕</button>
          </div>
        </div>

      </div><!-- /.card -->
    </div>
  </div>

  <!-- ── AI Proposals overlay ─────────────────────────────────────────────────── -->
  <Teleport to="body">
    <Transition name="overlay">
      <div v-if="showReviewOverlay" class="overlay-backdrop" @click.self="showReviewOverlay = false">
        <div class="overlay-panel" role="dialog" aria-modal="true" aria-label="AI Proposals">

          <div class="overlay-header">
            <div>
              <span class="overlay-title">AI Proposals</span>
              <span class="overlay-subtitle">
                {{ previewResult?.total }} record{{ previewResult?.total !== 1 ? 's' : '' }}
                · {{ correctedCount }} corrected · {{ cleanCount }} clean
              </span>
            </div>
            <button class="btn-icon overlay-close" @click="showReviewOverlay = false" aria-label="Close">✕</button>
          </div>

          <div class="overlay-toolbar">
            <span class="text-muted" style="font-size:.82rem;">
              {{ accepted.size }} of {{ previewResult?.total }} selected
            </span>
            <div style="display:flex; gap:.4rem;">
              <button class="btn btn-ghost btn-sm" @click="selectAll">Select all</button>
              <button class="btn btn-ghost btn-sm" @click="deselectAll">Deselect all</button>
            </div>
          </div>

          <div class="overlay-list">
            <label
              v-for="rec in previewResult?.records"
              :key="rec.index"
              class="review-item"
              :class="{ 'review-item-checked': accepted.has(rec.index) }"
            >
              <input
                type="checkbox"
                class="review-checkbox"
                :checked="accepted.has(rec.index)"
                @change="toggleAccept(rec.index)"
              />
              <div class="review-content">
                <div class="review-record-title">
                  <span class="review-record-name">{{ rec.proposed.name }}</span>
                  <span v-if="rec.proposed.brand" class="review-brand">{{ rec.proposed.brand }}</span>
                  <span v-if="rec.changes.length" class="diff-badge">
                    {{ rec.changes.length }} fix{{ rec.changes.length > 1 ? 'es' : '' }}
                  </span>
                  <span v-else class="clean-badge">✓ clean</span>
                </div>

                <div v-if="rec.changes.length" class="review-record-details">
                  <span class="review-detail">
                    <span class="review-detail-label">Status</span>
                    <span class="badge" :class="statusClass(rec.proposed.status)">{{ rec.proposed.status }}</span>
                  </span>
                  <span v-if="rec.proposed.purchase_date" class="review-detail">
                    <span class="review-detail-label">Date</span>{{ rec.proposed.purchase_date }}
                  </span>
                  <span v-if="rec.proposed.notes" class="review-detail review-detail-notes">
                    <span class="review-detail-label">Notes</span>{{ rec.proposed.notes }}
                  </span>
                </div>

                <div v-if="rec.changes.length" class="review-diffs">
                  <div class="review-diffs-label">AI corrections:</div>
                  <div v-for="ch in rec.changes" :key="ch.field" class="diff-row">
                    <span class="diff-field">{{ fieldLabel(ch.field) }}</span>
                    <span class="diff-before">{{ ch.before ?? '—' }}</span>
                    <span class="diff-arrow">→</span>
                    <span class="diff-after">{{ ch.after ?? '—' }}</span>
                  </div>
                </div>
              </div>
            </label>
          </div>

          <div class="overlay-footer">
            <button class="btn btn-ghost btn-sm" style="color:#dc2626;" @click="resetProposals">
              ✕ Discard all proposals
            </button>
            <button
              class="btn btn-primary"
              :disabled="accepted.size === 0 || seedStep === 'importing'"
              @click="handleConfirmImport"
            >
              <span v-if="seedStep === 'importing'" class="spinner"></span>
              {{ seedStep === 'importing' ? 'Importing…' : `Import selected (${accepted.size})` }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- ── Rejected records overlay ────────────────────────────────────────────── -->
  <Teleport to="body">
    <Transition name="overlay">
      <div v-if="showRejectedOverlay" class="overlay-backdrop" @click.self="showRejectedOverlay = false">
        <div class="overlay-panel" role="dialog" aria-modal="true" aria-label="Skipped records">

          <div class="overlay-header">
            <div>
              <span class="overlay-title">Import Result</span>
              <span class="overlay-subtitle">
                {{ plainSeedResult?.inserted }} inserted
                · {{ plainSeedResult?.rejected?.length }} skipped
              </span>
            </div>
            <button class="btn-icon overlay-close" @click="showRejectedOverlay = false">✕</button>
          </div>

          <div class="overlay-list">
            <div
              v-for="rej in plainSeedResult?.rejected"
              :key="rej.index"
              class="rejected-overlay-item"
            >
              <div class="rejected-overlay-header">
                <span class="rejected-index">#{{ rej.index + 1 }}</span>
                <span class="rejected-overlay-name">{{ recordLabel(rej.record) }}</span>
              </div>
              <div class="rejected-overlay-reason">{{ formatRejectionReason(rej.reason) }}</div>
            </div>
          </div>

          <div class="overlay-footer">
            <button class="btn btn-ghost btn-sm" style="color:#dc2626;" @click="dismissPlainResult">
              ✕ Dismiss results
            </button>
            <button class="btn btn-ghost btn-sm" @click="showRejectedOverlay = false">
              Close
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- ── Raw data modal ──────────────────────────────────────────────────────── -->
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="showRawModal" class="modal-backdrop" @click.self="showRawModal = false">
        <div class="modal-cloud" role="dialog" aria-modal="true">
          <div class="modal-cloud-header">
            <span>Raw data — {{ seedRecordCount }} record{{ seedRecordCount !== 1 ? 's' : '' }}</span>
            <button class="toast-close" @click="showRawModal = false">×</button>
          </div>
          <pre class="modal-cloud-body">{{ JSON.stringify(seedPayload, null, 2) }}</pre>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- ── Toast ──────────────────────────────────────────────────────────────── -->
  <Transition name="toast">
    <div v-if="showToast" class="toast" role="alert">
      <div class="toast-header">
        <span class="toast-title">✓ Import successful</span>
        <button class="toast-close" @click="dismissToast">×</button>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { createUser, aiSeedPreview, plainSeed } from '../api/client.js'

const router = useRouter()
const SESSION_KEY          = 'hardware_hub_ai_preview'
const REJECTED_SESSION_KEY = 'hardware_hub_plain_rejected'

// ── Add user ─────────────────────────────────────────────────────────────────
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

// ── Seed importer shared state ────────────────────────────────────────────────
const fileInputRef    = ref(null)
const aiMode          = ref(false)
const seedStep        = ref('idle')   // 'idle' | 'previewing' | 'importing'
const seedError       = ref('')
const seedPayload     = ref([])
const seedFileName    = ref('')
const seedRecordCount = ref(0)
const showRawModal    = ref(false)

// ── AI mode state (persisted) ─────────────────────────────────────────────────
const previewResult     = ref(null)
const accepted          = reactive(new Set())
const showReviewOverlay = ref(false)

const hasProposals   = computed(() => previewResult.value !== null)
const correctedCount = computed(() =>
  previewResult.value?.records.filter(r => r.changes.length > 0).length ?? 0)
const cleanCount = computed(() =>
  previewResult.value?.records.filter(r => r.changes.length === 0).length ?? 0)

// ── Non-AI mode state (persisted) ────────────────────────────────────────────
const plainSeedResult    = ref(null)
const showRejectedOverlay = ref(false)

// ── Session persistence ───────────────────────────────────────────────────────
function saveSession() {
  if (previewResult.value) {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({
      result: previewResult.value,
      acceptedIndices: [...accepted],
      rawPayload: seedPayload.value,
      rawFileName: seedFileName.value,
    }))
  } else {
    sessionStorage.removeItem(SESSION_KEY)
  }
}

onMounted(() => {
  // Restore AI proposals
  const savedAi = sessionStorage.getItem(SESSION_KEY)
  if (savedAi) {
    try {
      const { result, acceptedIndices, rawPayload, rawFileName } = JSON.parse(savedAi)
      previewResult.value = result
      acceptedIndices.forEach(i => accepted.add(i))
      if (rawPayload?.length) {
        seedPayload.value     = rawPayload
        seedRecordCount.value = rawPayload.length
        seedFileName.value    = rawFileName ?? ''
        aiMode.value          = true
      }
    } catch {
      sessionStorage.removeItem(SESSION_KEY)
    }
  }

  // Restore plain seed result
  const savedPlain = sessionStorage.getItem(REJECTED_SESSION_KEY)
  if (savedPlain) {
    try {
      plainSeedResult.value = JSON.parse(savedPlain)
    } catch {
      sessionStorage.removeItem(REJECTED_SESSION_KEY)
    }
  }
})

function onAiModeChange() {
  seedError.value = ''
}

function dismissPlainResult() {
  plainSeedResult.value     = null
  showRejectedOverlay.value = false
  sessionStorage.removeItem(REJECTED_SESSION_KEY)
  // File is intentionally NOT cleared here — user clears it via the ✕ on the picker.
}

// ── File handling ─────────────────────────────────────────────────────────────
function clearFile() {
  seedPayload.value     = []
  seedRecordCount.value = 0
  seedFileName.value    = ''
  seedError.value       = ''
  showRawModal.value    = false
  if (fileInputRef.value) fileInputRef.value.value = ''
}

async function handleFileChange(event) {
  const file = event.target.files?.[0]   // capture before clearFile resets the input
  clearFile()
  plainSeedResult.value = null           // new file → clear old result
  sessionStorage.removeItem(REJECTED_SESSION_KEY)
  if (!file) return
  try {
    const parsed = JSON.parse(await file.text())
    if (!Array.isArray(parsed)) throw new Error('File must contain a JSON array.')
    seedPayload.value     = parsed
    seedRecordCount.value = parsed.length
    seedFileName.value    = file.name
  } catch (err) {
    seedError.value = err.message || 'Failed to parse JSON file.'
  }
}

// ── AI mode: preview ──────────────────────────────────────────────────────────
async function handlePreview() {
  if (!seedRecordCount.value) { seedError.value = 'Upload a file first.'; return }
  seedError.value = ''
  seedStep.value = 'previewing'
  try {
    const result = await aiSeedPreview(seedPayload.value)
    previewResult.value = result
    accepted.clear()
    result.records.forEach(r => accepted.add(r.index))
    saveSession()
    showReviewOverlay.value = true
  } catch (err) {
    seedError.value = err.message || 'AI preview failed.'
  } finally {
    seedStep.value = 'idle'
  }
}

function resetProposals() {
  previewResult.value = null
  accepted.clear()
  showReviewOverlay.value = false
  saveSession()
}

// ── Accept/reject ─────────────────────────────────────────────────────────────
function toggleAccept(index) {
  accepted.has(index) ? accepted.delete(index) : accepted.add(index)
  saveSession()
}
function selectAll()   { previewResult.value?.records.forEach(r => accepted.add(r.index)); saveSession() }
function deselectAll() { accepted.clear(); saveSession() }

// ── AI mode: confirm import ───────────────────────────────────────────────────
async function handleConfirmImport() {
  if (!accepted.size) return
  seedError.value = ''
  seedStep.value = 'importing'
  const toInsert = previewResult.value.records
    .filter(r => accepted.has(r.index))
    .map(r => r.proposed_id != null ? { ...r.proposed, id: r.proposed_id } : { ...r.proposed })
  try {
    const result = await plainSeed(toInsert)
    const corrected = previewResult.value.records
      .filter(r => accepted.has(r.index) && r.changes.length > 0).length
    showImportToast(
      corrected > 0
        ? `Inserted ${result.inserted} record(s). AI corrected ${corrected} of them.`
        : `Inserted ${result.inserted} record(s). All records were already clean.`
    )
    showReviewOverlay.value = false
    resetProposals()
    clearFile()
  } catch (err) {
    seedError.value = err.message || 'Import failed.'
  } finally {
    seedStep.value = 'idle'
  }
}

// ── Non-AI mode: plain import ─────────────────────────────────────────────────
async function handlePlainImport() {
  if (!seedRecordCount.value) { seedError.value = 'Upload a file first.'; return }
  seedError.value = ''
  seedStep.value = 'importing'
  try {
    const result = await plainSeed(seedPayload.value)
    plainSeedResult.value = result
    sessionStorage.setItem(REJECTED_SESSION_KEY, JSON.stringify(result))
    if (!result.rejected.length) {
      // All records inserted — clear file to prevent re-import
      clearFile()
      showImportToast(`Inserted ${result.inserted} record(s) successfully.`)
    }
    // If there were skipped records, keep the file in the picker so the user
    // can see which file produced the errors. File clears on dismiss or new file.
  } catch (err) {
    seedError.value = err.message || 'Import failed.'
  } finally {
    seedStep.value = 'idle'
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const FIELD_LABELS = { id: 'ID', name: 'Name', brand: 'Brand', purchase_date: 'Date', status: 'Status', notes: 'Notes' }
function fieldLabel(f) { return FIELD_LABELS[f] ?? f }

function statusClass(status) {
  return { Available: 'badge-available', 'In Use': 'badge-in-use', Repair: 'badge-repair' }[status] ?? ''
}

function recordLabel(record) {
  if (!record || typeof record !== 'object') return ''
  return record.name ?? record.id ?? ''
}

function formatRejectionReason(reason) {
  if (!reason) return ''
  const lines = reason.split('\n').map(l => l.trim()).filter(Boolean)
  if (lines.length >= 3 && lines[0].includes('validation error')) {
    const field = lines[1]
    const msg   = lines[2].replace(/\s*\[.*\]$/, '').trim()
    return `${field}: ${msg}`
  }
  return lines[0].replace(/^.*?:\s*/, '').trim()
}

// ── Toast ─────────────────────────────────────────────────────────────────────
const showToast    = ref(false)
const toastMessage = ref('')
let toastTimer     = null

function showImportToast(message) {
  toastMessage.value = message
  showToast.value = true
  clearTimeout(toastTimer)
  toastTimer = setTimeout(dismissToast, 7000)
}
function dismissToast() { showToast.value = false; clearTimeout(toastTimer) }
function goToDashboard() { dismissToast(); router.push('/dashboard') }
</script>

<style scoped>
/* ── Seed card ────────────────────────────────────────────────────────────── */
.seed-card {
  display: flex;
  flex-direction: column;
  transition: border-color .2s, box-shadow .2s;
}

.seed-card-ai {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, .12);
}

.seed-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: .75rem;
}

/* ── AI toggle ────────────────────────────────────────────────────────────── */
.ai-toggle-wrap {
  display: flex;
  align-items: center;
  gap: .4rem;
  flex-shrink: 0;
}

.ai-toggle-label {
  font-size: .78rem;
  color: var(--text-muted);
  white-space: nowrap;
}
.ai-toggle-label-on {
  color: var(--brand);
  font-weight: 600;
}

/* ── AI title badge ──────────────────────────────────────────────────────── */
.ai-title-badge {
  display: inline-block;
  margin-left: .4rem;
  font-size: .6rem;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--brand);
  background: rgba(99, 102, 241, .12);
  border: 1px solid rgba(99, 102, 241, .3);
  border-radius: 4px;
  padding: .15rem .4rem;
  vertical-align: middle;
  line-height: 1;
}

/* ── Custom file picker ───────────────────────────────────────────────────── */
.file-picker {
  display: flex;
  align-items: center;
  gap: .5rem;
  margin-top: .3rem;
}

.file-picker-btn {
  flex-shrink: 0;
  white-space: nowrap;
}

.file-picker-name {
  flex: 1;
  font-size: .82rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.file-picker-clear {
  flex-shrink: 0;
  color: var(--text-muted);
  font-size: .8rem;
}
.file-picker-clear:hover { color: #dc2626; }

/* ── Proposals / result banners ───────────────────────────────────────────── */
.proposals-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: .75rem;
  flex-wrap: wrap;
  padding: .6rem .85rem;
  margin-bottom: .75rem;
  background: rgba(99, 102, 241, .06);
  border: 1px solid rgba(99, 102, 241, .25);
  border-radius: var(--radius);
  font-size: .82rem;
}
.proposals-banner-plain {
  background: rgba(234, 179, 8, .06);
  border-color: rgba(234, 179, 8, .35);
}
.proposals-banner-info {
  display: flex;
  flex-direction: column;
  gap: .1rem;
}

/* ── Rejected overlay items ───────────────────────────────────────────────── */
.rejected-overlay-item {
  padding: .65rem 1.25rem;
  border-bottom: 1px solid var(--border);
}
.rejected-overlay-item:last-child { border-bottom: none; }
.rejected-overlay-header {
  display: flex;
  align-items: center;
  gap: .5rem;
  margin-bottom: .2rem;
}
.rejected-overlay-name {
  font-weight: 600;
  font-size: .88rem;
}
.rejected-overlay-reason {
  font-size: .78rem;
  color: #dc2626;
  font-family: monospace;
}

/* ── Non-AI result ────────────────────────────────────────────────────────── */
.plain-result {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.plain-result-header {
  display: flex;
  align-items: center;
  gap: .5rem;
  padding: .4rem .6rem;
}

/* ── Rejected list ────────────────────────────────────────────────────────── */
.rejected-list {
  border-top: 1px solid var(--border);
  font-size: .72rem;
}
.rejected-list-title {
  padding: .3rem .6rem;
  background: var(--bg);
  font-weight: 600;
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
}
.rejected-item {
  display: flex;
  align-items: baseline;
  gap: .4rem;
  padding: .3rem .6rem;
  border-bottom: 1px solid var(--border);
}
.rejected-item:last-child { border-bottom: none; }
.rejected-index { font-weight: 600; color: var(--text-muted); flex-shrink: 0; min-width: 2rem; }
.rejected-name  { font-weight: 500; flex-shrink: 0; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rejected-reason { color: #dc2626; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── Full-page overlay ────────────────────────────────────────────────────── */
.overlay-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.55);
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}
.overlay-panel {
  background: var(--card, #fff);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 20px 60px rgba(0,0,0,.25);
  width: 100%;
  max-width: 860px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.overlay-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .9rem 1.25rem;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  gap: 1rem;
}
.overlay-title    { font-size: 1rem; font-weight: 700; margin-right: .5rem; }
.overlay-subtitle { font-size: .8rem; color: var(--text-muted); }
.overlay-close    { font-size: 1rem; color: var(--text-muted); flex-shrink: 0; }
.overlay-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .5rem 1.25rem;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
  flex-shrink: 0;
  gap: .5rem;
}
.overlay-list   { flex: 1; overflow-y: auto; }
.overlay-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .75rem 1.25rem;
  border-top: 1px solid var(--border);
  background: var(--bg);
  flex-shrink: 0;
  gap: .5rem;
}

/* ── Review items ─────────────────────────────────────────────────────────── */
.review-item {
  display: flex;
  align-items: flex-start;
  gap: .75rem;
  padding: .7rem 1.25rem;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background .1s;
}
.review-item:last-child { border-bottom: none; }
.review-item:hover { background: var(--bg); }
.review-item-checked { background: rgba(99,102,241,.03); }

.review-checkbox {
  margin-top: .2rem;
  flex-shrink: 0;
  accent-color: var(--brand);
  width: 15px;
  height: 15px;
  cursor: pointer;
}
.review-content { flex: 1; min-width: 0; }
.review-record-title { display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
.review-record-name  { font-weight: 600; font-size: .88rem; }
.review-brand        { color: var(--text-muted); font-size: .8rem; }

.clean-badge {
  font-size: .72rem; color: #16a34a;
  background: rgba(22,163,74,.1); border: 1px solid rgba(22,163,74,.25);
  border-radius: 999px; padding: .1rem .45rem;
}
.diff-badge {
  font-size: .72rem; color: #b45309;
  background: rgba(180,83,9,.1); border: 1px solid rgba(180,83,9,.25);
  border-radius: 999px; padding: .1rem .45rem;
}

.review-record-details {
  display: flex; flex-wrap: wrap; gap: .25rem .75rem;
  margin-top: .35rem; font-size: .78rem; color: var(--text-muted);
  padding: .35rem .6rem; background: var(--bg);
  border-radius: 4px; border: 1px solid var(--border);
}
.review-detail { display: flex; align-items: center; gap: .25rem; }
.review-detail-label {
  font-weight: 600; font-size: .7rem;
  text-transform: uppercase; letter-spacing: .02em; color: var(--text-muted);
}
.review-detail-notes { width: 100%; align-items: flex-start; color: var(--text); font-style: italic; }

.review-diffs { margin-top: .35rem; display: flex; flex-direction: column; gap: .15rem; }
.review-diffs-label {
  font-size: .7rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: .02em; color: var(--text-muted); margin-bottom: .1rem;
}
.diff-row { display: flex; align-items: baseline; gap: .35rem; font-size: .78rem; }
.diff-field  { font-weight: 600; color: var(--text-muted); min-width: 46px; flex-shrink: 0; }
.diff-before { color: #dc2626; text-decoration: line-through; opacity: .8; }
.diff-arrow  { color: var(--text-muted); flex-shrink: 0; }
.diff-after  { color: #16a34a; font-weight: 500; }

/* ── Alert warning ────────────────────────────────────────────────────────── */
.alert-warning {
  background: rgba(234,179,8,.1); border: 1px solid rgba(234,179,8,.35); color: #92700a;
}

/* ── Raw data modal ───────────────────────────────────────────────────────── */
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 200;
  display: flex; align-items: center; justify-content: center; padding: 1.5rem;
}
.modal-cloud {
  background: var(--card, #fff); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: 0 12px 48px rgba(0,0,0,.22);
  max-width: 700px; width: 100%; max-height: 78vh;
  display: flex; flex-direction: column; overflow: hidden;
}
.modal-cloud-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: .7rem 1rem; border-bottom: 1px solid var(--border);
  font-size: .8rem; font-weight: 600; flex-shrink: 0;
}
.modal-cloud-body {
  font-size: .72rem; line-height: 1.5; overflow: auto;
  padding: .75rem 1rem; margin: 0; background: var(--bg, #f9fafb); flex: 1;
}

/* ── Transitions ──────────────────────────────────────────────────────────── */
.overlay-enter-active, .overlay-leave-active { transition: opacity .2s ease; }
.overlay-enter-from,   .overlay-leave-to     { opacity: 0; }
.modal-enter-active,   .modal-leave-active    { transition: opacity .15s ease; }
.modal-enter-from,     .modal-leave-to        { opacity: 0; }
</style>
