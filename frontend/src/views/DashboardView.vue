<template>
  <div class="page">

    <!-- Header row -->
    <div class="flex items-center justify-between" style="flex-wrap:wrap; gap:1rem;">
      <div>
        <h1>Hardware List</h1>
        <p class="text-muted mt-1">Browse and rent company equipment.</p>
      </div>
      <div class="flex items-center gap-2">
        <!-- Bulk delete — admin only -->
        <template v-if="isAdmin">
          <span v-if="selectedIds.size > 0" class="text-muted" style="font-size:.82rem;">
            {{ selectedIds.size }} selected
          </span>
          <button
            class="btn btn-sm bulk-delete-btn"
            :disabled="selectedIds.size === 0"
            @click="handleBulkDelete"
          >
            Delete selected
          </button>
        </template>

        <!-- Add Hardware button — admin only -->
        <div v-if="isAdmin" style="position:relative;">
          <button
            class="btn btn-primary btn-sm"
            @click="toggleAddForm"
            title="Add new hardware item"
          >
            + Add Hardware
          </button>

          <!-- Add Hardware popover -->
          <Transition name="popover">
            <div v-if="showAddForm" class="add-popover">
              <div class="add-popover-header">
                <span>New Hardware</span>
                <button class="btn-icon" @click="closeAddForm" title="Close">✕</button>
              </div>
              <form @submit.prevent="handleAddHardware" class="add-popover-body">
                <div class="form-group">
                  <label>Name *</label>
                  <input v-model="newItem.name" class="input" placeholder="MacBook Pro 14"" required minlength="1" />
                </div>
                <div class="form-group mt-1">
                  <label>Brand</label>
                  <input v-model="newItem.brand" class="input" placeholder="Apple" />
                </div>
                <div class="form-group mt-1">
                  <label>Purchase Date</label>
                  <input v-model="newItem.purchase_date" class="input" type="date" />
                </div>
                <div class="form-group mt-1">
                  <label>Status</label>
                  <select v-model="newItem.status">
                    <option value="Available">Available</option>
                    <option value="In Use">In Use</option>
                    <option value="Repair">Repair</option>
                  </select>
                </div>
                <div v-if="addError" class="alert alert-error mt-1" style="font-size:.8rem;">{{ addError }}</div>
                <button type="submit" class="btn btn-primary mt-2 w-full" :disabled="addLoading">
                  <span v-if="addLoading" class="spinner"></span>
                  {{ addLoading ? 'Adding…' : 'Add Item' }}
                </button>
              </form>
            </div>
          </Transition>
        </div>

        <button class="btn btn-ghost btn-sm" @click="loadHardware" title="Refresh list">
          ↻ Refresh
        </button>
      </div>
    </div>

    <!-- Search bar -->
    <div class="mt-2">
      <div class="search-bar-extended" :class="{ 'search-bar-ai-active': aiResults !== null }">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          v-model="searchQuery"
          :placeholder="searchPlaceholder"
          :disabled="aiResults !== null"
          @input="filterLocally()"
          @keyup.enter="searchQuery.trim() ? runAiSearch() : undefined"
        />
        <button v-if="aiResults !== null" class="btn-icon search-clear-btn" @click="clearAiResults" title="Clear AI results">
          ✕
        </button>
        <button
          v-else
          class="btn btn-sm ai-search-btn"
          :disabled="aiLoading || !searchQuery.trim()"
          @click="runAiSearch"
        >
          <span v-if="aiLoading" class="spinner" style="width:12px;height:12px;"></span>
          <span v-else>⚡ Search with AI</span>
        </button>
      </div>
    </div>

    <!-- Status filter pills (hidden while AI results showing) -->
    <div v-if="aiResults === null" class="flex gap-1 mt-2" style="flex-wrap:wrap;">
      <button
        v-for="s in ['All', 'Available', 'In Use', 'Repair']"
        :key="s"
        class="btn btn-sm"
        :class="statusFilter === s ? 'btn-primary' : 'btn-ghost'"
        @click="setStatusFilter(s)"
      >{{ s }}</button>
    </div>

    <div v-if="error" class="alert alert-error mt-2">{{ error }}</div>

    <!-- Table -->
    <div class="mt-2">
      <!-- AI search loading state -->
      <div v-if="aiLoading" class="ai-loading-state">
        <span class="spinner ai-loading-spinner"></span>
        <p class="ai-loading-title">Searching with AI…</p>
        <p class="text-muted" style="font-size:.85rem; margin-top:.25rem;">
          Analyzing <strong>{{ allHardware.length }}</strong> records
          for <strong>"{{ searchQuery }}"</strong>
        </p>
      </div>
      <div v-else-if="loading" style="text-align:center; padding:3rem;">
        <span class="spinner"></span>
      </div>
      <div v-else-if="displayedRows.length === 0" class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
        <p>No hardware items found.</p>
      </div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th v-if="isAdmin" class="col-check">
                <input
                  ref="headerCheckboxRef"
                  type="checkbox"
                  class="row-checkbox"
                  :checked="allFilteredSelected"
                  @change="toggleAllDisplayed"
                />
              </th>
              <th>Name</th>
              <th style="width:140px">Brand</th>
              <th style="width:104px">Status</th>
              <th style="width:132px">Purchase Date</th>
              <th style="width:90px">Action</th>
              <th v-if="isAdmin" class="col-del"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in displayedRows" :key="item.id" :class="{ 'row-selected': selectedIds.has(item.id) }">
              <td v-if="isAdmin" class="col-check">
                <input
                  type="checkbox"
                  class="row-checkbox"
                  :checked="selectedIds.has(item.id)"
                  @change="toggleSelect(item.id)"
                />
              </td>
              <td style="white-space:normal"><strong>{{ item.name }}</strong></td>
              <td>{{ item.brand || '—' }}</td>
              <td>
                <span class="badge" :class="statusClass(item.status)">{{ item.status }}</span>
              </td>
              <td class="text-muted">{{ item.purchase_date ?? '—' }}</td>
              <td>
                <button
                  v-if="item.status === 'Available'"
                  class="btn btn-sm btn-primary"
                  style="width:100%; justify-content:center;"
                  :disabled="rentingId === item.id"
                  @click="handleRent(item)"
                >
                  Rent
                </button>
                <span v-else class="text-muted" style="font-size:.8rem;">—</span>
              </td>
              <!-- Delete button — admin only -->
              <td v-if="isAdmin" class="col-del">
                <button
                  class="row-delete-btn"
                  :disabled="deletingId === item.id"
                  @click="handleDelete(item)"
                  title="Delete this item"
                >
                  <span v-if="deletingId === item.id" class="spinner" style="width:10px;height:10px;"></span>
                  <span v-else>✕</span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>

  <!-- Backdrop for closing the add popover when clicking outside -->
  <div v-if="showAddForm" class="popover-backdrop" @click="closeAddForm"></div>

  <!-- Fixed toast — rent/action feedback, no layout shift -->
  <Transition name="toast">
    <div v-if="toast" class="action-toast" role="alert">
      <span>{{ toast }}</span>
      <button class="btn-icon" style="margin-left:.5rem;" @click="toast = ''">×</button>
    </div>
  </Transition>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, watchEffect } from 'vue'
import { listHardware, rentHardware, aiSearch, createHardware, deleteHardware, updateHardware } from '../api/client.js'
import { getStoredUser } from '../api/client.js'

const user    = getStoredUser()
const isAdmin = user?.role === 'admin'

// ── Hardware data ───────────────────────────────────────────────────────────
const allHardware = ref([])
const loading     = ref(false)
const error       = ref('')

async function loadHardware() {
  loading.value = true
  error.value   = ''
  try {
    allHardware.value = await listHardware()
  } catch (err) {
    error.value = err.message || 'Failed to load hardware.'
  } finally {
    loading.value = false
  }
}

onMounted(loadHardware)

// ── Local filter ─────────────────────────────────────────────────────────────
const searchQuery  = ref('')
const statusFilter = ref('All')

function setStatusFilter(s) {
  statusFilter.value = s
}

function filterLocally() {
  // reactive — displayedRows recomputes automatically
}

const locallyFiltered = computed(() => {
  let rows = allHardware.value
  if (statusFilter.value !== 'All') {
    rows = rows.filter(h => h.status === statusFilter.value)
  }
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    rows = rows.filter(h =>
      h.name.toLowerCase().includes(q) ||
      (h.brand ?? '').toLowerCase().includes(q) ||
      (h.status ?? '').toLowerCase().includes(q) ||
      (h.notes ?? '').toLowerCase().includes(q) ||
      (h.purchase_date ?? '').toString().includes(q)
    )
  }
  return rows
})

// ── AI search ────────────────────────────────────────────────────────────────
const aiLoading   = ref(false)
const aiResults   = ref(null)   // null = no AI results; array = showing AI results
const lastAiQuery = ref('')

async function runAiSearch() {
  const q = searchQuery.value.trim()
  if (!q) return
  aiLoading.value = true
  error.value     = ''
  try {
    const results = await aiSearch(q)
    aiResults.value   = results
    lastAiQuery.value = q
  } catch (err) {
    error.value = err.message || 'AI search failed.'
  } finally {
    aiLoading.value = false
  }
}

function clearAiResults() {
  aiResults.value   = null
  lastAiQuery.value = ''
  searchQuery.value = ''
}

// ── Search placeholder ────────────────────────────────────────────────────────
const searchPlaceholder = computed(() =>
  aiResults.value !== null
    ? `AI results for \u201c${lastAiQuery.value}\u201d — click \u2715 to clear`
    : 'Filter by name, brand, status, date, or search with AI\u2026'
)

// ── Displayed rows ──────────────────────────────────────────────────────────
const displayedRows = computed(() =>
  aiResults.value !== null ? aiResults.value : locallyFiltered.value
)

// ── Toast (fixed-position, no layout shift) ───────────────────────────────────
const toast = ref('')
let toastTimer = null
function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 4000)
}

// ── Rent ─────────────────────────────────────────────────────────────────────
const rentingId = ref(null)

async function handleRent(item) {
  if (!user) { error.value = 'You must be logged in to rent.'; return }
  rentingId.value = item.id
  error.value     = ''
  try {
    await rentHardware(user.id, item.id)
    showToast(`✓ "${item.name}" rented successfully.`)
    item.status = 'In Use'
  } catch (err) {
    error.value = err.message || 'Failed to rent item.'
  } finally {
    rentingId.value = null
  }
}

// ── Selection (admin only) ────────────────────────────────────────────────────
const selectedIds        = reactive(new Set())
const headerCheckboxRef  = ref(null)

const allFilteredSelected = computed(() =>
  displayedRows.value.length > 0 &&
  displayedRows.value.every(item => selectedIds.has(item.id))
)
const someSelected = computed(() =>
  selectedIds.size > 0 && !allFilteredSelected.value
)

// Keep header checkbox indeterminate state in sync
watchEffect(() => {
  if (headerCheckboxRef.value) {
    headerCheckboxRef.value.indeterminate = someSelected.value
  }
})

function toggleSelect(id) {
  selectedIds.has(id) ? selectedIds.delete(id) : selectedIds.add(id)
}

function selectAllFiltered() {
  displayedRows.value.forEach(item => selectedIds.add(item.id))
}

function toggleAllDisplayed() {
  allFilteredSelected.value ? selectedIds.clear() : selectAllFiltered()
}

// ── Delete (admin only) ───────────────────────────────────────────────────────
const deletingId = ref(null)
const bulkDeleting = ref(false)

async function handleDelete(item) {
  if (!confirm(`Delete "${item.name}"?\n\nThis will permanently remove the item and all its rental history.`)) return
  deletingId.value = item.id
  error.value      = ''
  try {
    await deleteHardware(item.id)
    allHardware.value = allHardware.value.filter(h => h.id !== item.id)
    if (aiResults.value !== null) {
      aiResults.value = aiResults.value.filter(h => h.id !== item.id)
    }
    selectedIds.delete(item.id)
  } catch (err) {
    error.value = err.message || 'Failed to delete item.'
  } finally {
    deletingId.value = null
  }
}

async function handleBulkDelete() {
  const ids = [...selectedIds]
  const names = allHardware.value
    .filter(h => selectedIds.has(h.id))
    .map(h => h.name)
  if (!confirm(`Delete ${ids.length} item(s)?\n\n${names.join('\n')}\n\nThis cannot be undone.`)) return
  bulkDeleting.value = true
  error.value = ''
  const failed = []
  for (const id of ids) {
    try {
      await deleteHardware(id)
      allHardware.value = allHardware.value.filter(h => h.id !== id)
      if (aiResults.value !== null) {
        aiResults.value = aiResults.value.filter(h => h.id !== id)
      }
      selectedIds.delete(id)
    } catch {
      failed.push(id)
    }
  }
  bulkDeleting.value = false
  if (failed.length) error.value = `Failed to delete ${failed.length} item(s).`
}

// ── Add Hardware (admin only) ─────────────────────────────────────────────────
const showAddForm = ref(false)
const addLoading  = ref(false)
const addError    = ref('')

const newItem = ref({
  name: '',
  brand: '',
  purchase_date: '',
  status: 'Available',
})

function toggleAddForm() {
  showAddForm.value = !showAddForm.value
  if (!showAddForm.value) resetAddForm()
}

function closeAddForm() {
  showAddForm.value = false
  resetAddForm()
}

function resetAddForm() {
  addError.value = ''
  newItem.value  = { name: '', brand: '', purchase_date: '', status: 'Available' }
}

async function handleAddHardware() {
  addError.value = ''
  addLoading.value = true
  try {
    const payload = {
      name:          newItem.value.name.trim(),
      brand:         newItem.value.brand.trim() || null,
      purchase_date: newItem.value.purchase_date || null,
      status:        newItem.value.status,
    }
    const created = await createHardware(payload)
    allHardware.value = [...allHardware.value, created]
    closeAddForm()
  } catch (err) {
    addError.value = err.message || 'Failed to add hardware.'
  } finally {
    addLoading.value = false
  }
}

// ── Inline notes editing (admin only) ────────────────────────────────────────
const editingNotesId    = ref(null)
const editingNotesValue = ref('')

function startEditNotes(item) {
  editingNotesId.value    = item.id
  editingNotesValue.value = item.notes ?? ''
  nextTick(() => {
    document.getElementById(`notes-input-${item.id}`)?.focus()
  })
}

async function saveNotes(item) {
  if (editingNotesId.value !== item.id) return
  const newNotes = editingNotesValue.value.trim() || null
  editingNotesId.value = null
  if (newNotes === (item.notes ?? null)) return   // no change
  try {
    await updateHardware(item.id, { notes: newNotes })
    item.notes = newNotes
  } catch (err) {
    error.value = err.message || 'Failed to save notes.'
  }
}

function cancelEditNotes() {
  editingNotesId.value = null
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function statusClass(status) {
  return {
    'Available': 'badge-available',
    'In Use':    'badge-in-use',
    'Repair':    'badge-repair',
  }[status] ?? ''
}
</script>

<style scoped>
/* ── Add Hardware popover ────────────────────────────────────────────────── */
.add-popover {
  position: absolute;
  top: calc(100% + .5rem);
  right: 0;
  width: 300px;
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 8px 24px rgba(0,0,0,.12);
  z-index: 200;
}

.add-popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .75rem 1rem;
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  font-size: .9rem;
}

.add-popover-body {
  padding: 1rem;
}

.popover-backdrop {
  position: fixed;
  inset: 0;
  z-index: 199;
}

/* ── Popover enter/leave transition ─────────────────────────────────────── */
.popover-enter-active,
.popover-leave-active {
  transition: opacity .15s ease, transform .15s ease;
}
.popover-enter-from,
.popover-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ── Checkbox column ──────────────────────────────────────────────────── */
.col-check {
  width: 32px;
  padding-right: 0;
}
.col-del {
  width: 28px;
  padding-left: 0;
}

.row-checkbox {
  accent-color: var(--brand);
  width: 14px;
  height: 14px;
  cursor: pointer;
  display: block;
  margin: 0 auto;
}

.row-selected td {
  background: rgba(99, 102, 241, .04);
}

/* ── Subtle per-row delete button ─────────────────────────────────────── */
.row-delete-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  font-size: .7rem;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  opacity: 0;
  transition: opacity .15s, background .15s, color .15s;
}
tr:hover .row-delete-btn { opacity: 1; }
.row-delete-btn:hover {
  background: rgba(220, 38, 38, .1);
  color: #dc2626;
}
.row-delete-btn:disabled { opacity: .4; cursor: not-allowed; }

/* ── Bulk delete button ───────────────────────────────────────────────── */
.bulk-delete-btn {
  background: rgba(220, 38, 38, .08);
  color: #dc2626;
  border: 1px solid rgba(220, 38, 38, .25);
  font-size: .78rem;
}
.bulk-delete-btn:hover {
  background: rgba(220, 38, 38, .15);
}

/* ── Extended search bar ──────────────────────────────────────────────── */
.search-bar-extended {
  display: flex;
  align-items: center;
  gap: .5rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--white, #fff);
  padding: .4rem .5rem .4rem .75rem;
  transition: border-color .15s, box-shadow .15s;
}
.search-bar-extended:focus-within {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(37,99,235,.12);
}
.search-bar-extended .search-icon {
  flex-shrink: 0;
  color: var(--text-muted);
}
.search-bar-extended input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: .9rem;
  color: var(--text);
  min-width: 0;
}
.search-bar-extended input::placeholder { color: var(--text-muted); }
.search-bar-extended input:disabled { opacity: .7; }

.search-bar-ai-active {
  border-color: var(--brand);
  background: rgba(37, 99, 235, .04);
}

.search-clear-btn {
  flex-shrink: 0;
  font-size: .9rem;
  color: var(--text-muted);
}
.search-clear-btn:hover { color: var(--text); }

.ai-search-btn {
  flex-shrink: 0;
  white-space: nowrap;
  font-size: .78rem;
  background: var(--brand);
  color: #fff;
  border: none;
  border-radius: calc(var(--radius) - 2px);
  padding: .3rem .75rem;
  cursor: pointer;
  transition: background .15s;
}
.ai-search-btn:hover:not(:disabled) { background: var(--brand-dark); }
.ai-search-btn:disabled { opacity: .45; cursor: not-allowed; }

/* ── AI loading state ─────────────────────────────────────────────────── */
.ai-loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  gap: .75rem;
  text-align: center;
}
.ai-loading-spinner {
  width: 36px !important;
  height: 36px !important;
  border-width: 3px !important;
}
.ai-loading-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--brand);
  margin: 0;
}

/* ── Fixed action toast ───────────────────────────────────────────────── */
.action-toast {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  z-index: 400;
  display: flex;
  align-items: center;
  background: #166534;
  color: #fff;
  padding: .6rem 1rem;
  border-radius: var(--radius);
  font-size: .85rem;
  box-shadow: 0 4px 16px rgba(0,0,0,.18);
  max-width: 360px;
}
.toast-enter-active, .toast-leave-active { transition: opacity .2s, transform .2s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }

/* ── Inline notes editing ─────────────────────────────────────────────── */
.notes-cell {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: text;
  border-radius: 4px;
  padding: .1rem .25rem;
  margin: -.1rem -.25rem;
  transition: background .15s;
}
.notes-cell:hover {
  background: var(--bg);
  outline: 1px dashed var(--border);
}

.notes-input {
  width: 100%;
  font-size: inherit;
  font-family: inherit;
  border: 1px solid var(--brand);
  border-radius: 4px;
  padding: .1rem .3rem;
  background: var(--white, #fff);
  outline: none;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, .15);
}
</style>
