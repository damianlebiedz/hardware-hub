<template>
  <div class="page">
    <h1>Admin Panel</h1>
    <p class="text-muted mt-1">Manage users and import legacy hardware data.</p>

    <div class="admin-dashboard-grid">

      <!-- ── Add User ────────────────────────────────────────────────────────── -->
      <div class="card admin-dashboard-card">
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
      <div class="card seed-card admin-dashboard-card" :class="{ 'seed-card-ai': aiMode }">

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
            <button
              class="btn btn-sm btn-danger-outline"
              type="button"
              title="Discard proposals"
              @click="resetProposals"
            >
              ✕ Discard
            </button>
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
              type="button"
              title="Remove file and import result"
              @click.stop="clearPickedFile"
            >✕</button>
          </div>
        </div>

        <div v-if="seedError" class="alert alert-error" style="margin-bottom:.75rem;">{{ seedError }}</div>

        <!-- Action buttons -->
        <div style="display:flex; gap:.5rem; align-items:center; flex-wrap:wrap; margin-bottom:.75rem;">
          <!-- AI mode: Preview button (disabled while proposals pending) -->
          <button
            v-if="aiMode"
            class="btn btn-ai"
            style="height:2.25rem; justify-content:center;"
            :class="{ 'btn--pending': seedStep === 'previewing' }"
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
            :class="{ 'btn--pending': seedStep === 'importing' }"
            :disabled="seedStep === 'importing' || seedRecordCount === 0"
            :aria-busy="seedStep === 'importing'"
            @click="handlePlainImport"
          >
            Import
          </button>

          <button
            v-if="seedRecordCount > 0"
            class="btn btn-ghost btn-sm"
            style="opacity:.8;"
            @click="showRawModal = true"
          >
            Show raw data
          </button>
        </div>

        <!-- Non-AI: fixed slot so card height does not jump when skipped banner appears -->
        <div v-if="!aiMode" class="plain-import-banner-reserved">
          <div
            v-if="plainSeedResult && plainSeedResult.rejected.length"
            class="proposals-banner proposals-banner-plain"
          >
            <div class="proposals-banner-info">
              <p class="plain-import-skip-line">
                <strong>{{ plainSeedResult.rejected.length }}</strong> skipped during the last import
              </p>
            </div>
            <div style="display:flex; gap:.4rem; flex-wrap:wrap; align-items:center;">
              <button
                class="btn btn-sm btn-danger-outline"
                type="button"
                @click="showRejectedOverlay = true"
              >
                Show skipped →
              </button>
              <button
                class="btn-icon"
                type="button"
                title="Dismiss import result (keeps the selected file)"
                @click="dismissPlainImportBanner"
              >✕</button>
            </div>
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
                  <div
                    v-for="(ch, chIdx) in rec.changes"
                    :key="`${rec.index}-${chIdx}-${ch.field}`"
                    class="diff-row"
                  >
                    <span class="diff-field">{{ fieldLabel(ch.field) }}</span>
                    <span class="diff-before">{{ ch.before ?? '—' }}</span>
                    <span class="diff-arrow">→</span>
                    <span class="diff-after">{{ ch.after ?? '—' }}</span>
                    <span v-if="ch.reason" class="diff-reason">{{ ch.reason }}</span>
                  </div>
                </div>
              </div>
            </label>
          </div>

          <div class="overlay-footer">
            <button class="btn btn-sm btn-danger-outline" type="button" @click="resetProposals">
              Discard all proposals
            </button>
            <button
              class="btn btn-primary"
              :class="{ 'btn--pending': seedStep === 'importing' }"
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
            <button class="btn-icon overlay-close" type="button" @click="showRejectedOverlay = false" aria-label="Close">✕</button>
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

  <!-- ── Toast (success) ────────────────────────────────────────────────────── -->
  <Transition name="toast">
    <div v-if="showToast" class="toast" role="alert">
      <div class="toast-header">
        <span class="toast-title">✓ Import successful</span>
        <button class="toast-close" @click="dismissToast">×</button>
      </div>
      <div class="toast-body">{{ toastMessage }}</div>
      <div class="toast-actions">
        <button class="btn btn-primary btn-sm" @click="goToDashboard">View in Dashboard →</button>
      </div>
    </div>
  </Transition>
  <Transition name="toast">
    <div v-if="showErrorToast" class="toast toast--error" role="alert">
      <div class="toast-header">
        <span class="toast-title">Error</span>
        <button class="toast-close" @click="dismissErrorToast">×</button>
      </div>
      <div class="toast-body">{{ errorToastMessage }}</div>
    </div>
  </Transition>
</template>

<script setup>
import { ref } from 'vue'
import { createUser } from '../api/client.js'
import { useSeedImporter } from '../composables/useSeedImporter.js'

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

const {
  fileInputRef,
  aiMode,
  seedStep,
  seedError,
  seedPayload,
  seedFileName,
  seedRecordCount,
  showRawModal,
  previewResult,
  accepted,
  showReviewOverlay,
  hasProposals,
  correctedCount,
  cleanCount,
  plainSeedResult,
  showRejectedOverlay,
  onAiModeChange,
  clearPickedFile,
  dismissPlainImportBanner,
  handleFileChange,
  handlePreview,
  resetProposals,
  toggleAccept,
  selectAll,
  deselectAll,
  handleConfirmImport,
  handlePlainImport,
  fieldLabel,
  statusClass,
  recordLabel,
  formatRejectionReason,
  showToast,
  toastMessage,
  dismissToast,
  goToDashboard,
  showErrorToast,
  errorToastMessage,
  dismissErrorToast,
} = useSeedImporter()
</script>

<style scoped>
.admin-dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-top: 1.5rem;
  align-items: stretch;
}

.admin-dashboard-card {
  height: 100%;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

/* Non-AI: reserve vertical space for the skipped banner (same height as when visible). */
.plain-import-banner-reserved {
  min-height: 4.5rem;
  margin-bottom: 0.75rem;
  flex-shrink: 0;
}
.plain-import-banner-reserved .proposals-banner {
  margin-bottom: 0;
}

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
  background: rgba(220, 38, 38, .06);
  border-color: rgba(220, 38, 38, .28);
  color: #991b1b;
}
.plain-import-skip-line {
  margin: 0;
  font-size: .84rem;
  line-height: 1.4;
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
  white-space: pre-wrap;
  word-break: break-word;
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
.overlay-close    { font-size: .875rem; color: var(--text-muted); flex-shrink: 0; }
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

.btn.btn-danger-outline {
  color: #dc2626;
  border: 1px solid #dc2626;
  background: transparent;
  font-weight: 600;
}
.btn.btn-danger-outline:hover:not(:disabled) {
  background: rgba(220, 38, 38, 0.08);
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
.diff-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: .35rem;
  font-size: .78rem;
}
.diff-field  { font-weight: 600; color: var(--text-muted); min-width: 46px; flex-shrink: 0; }
.diff-before { color: #dc2626; text-decoration: line-through; opacity: .8; }
.diff-arrow  { color: var(--text-muted); flex-shrink: 0; }
.diff-after  { color: #16a34a; font-weight: 500; }
.diff-reason {
  flex: 1 1 100%;
  font-size: 0.72rem;
  line-height: 1.35;
  color: var(--text-muted);
  font-style: italic;
  padding-left: calc(46px + 0.35rem);
}

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
