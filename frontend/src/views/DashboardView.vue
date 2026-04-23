<template>
  <div class="page" :class="{ 'page--add-popover-open': showAddForm }">

    <!-- Header row -->
    <div class="flex items-center justify-between" style="flex-wrap:wrap; gap:1rem;">
      <div>
        <h1>Hardware List</h1>
        <p class="text-muted mt-1">Browse and rent company equipment.</p>
      </div>
      <div class="flex items-center gap-2">
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
        <div v-if="isAdmin" class="add-hardware-anchor">
          <button
            class="btn btn-primary btn-sm"
            @click="toggleAddForm"
            title="Add new hardware item"
          >
            + Add Hardware
          </button>
          <Transition name="popover">
            <div v-if="showAddForm" class="add-popover">
              <div class="add-popover-header">
                <span>New Hardware</span>
                <button class="btn-icon" @click="closeAddForm" title="Close">✕</button>
              </div>
              <form @submit.prevent="handleAddHardware" class="add-popover-body">
                <div class="form-group">
                  <label>Name *</label>
                  <input v-model="newItem.name" class="input" placeholder="e.g. MacBook Pro 14" required minlength="1" />
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
      </div>
    </div>

    <!-- Search bar (own rounded frame) + AI button (same size as Add Hardware) -->
    <div class="mt-2">
      <div class="search-ai-row">
        <div
          class="search-bar-extended"
          :class="{ 'search-bar-ai-active': aiFilterUiActive }"
        >
          <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            v-model="searchQuery"
            :placeholder="searchPlaceholder"
            :disabled="aiLoading"
            @input="filterLocally()"
          />
        </div>
        <button
          type="button"
          class="btn btn-primary btn-sm ai-search-cta"
          :disabled="aiLoading || !searchQuery.trim() || aiFilterUiActive"
          :title="aiFilterUiActive ? 'Clear the AI filter below to run a new AI search' : ''"
          @click="runAiSearch"
        >
          <span v-if="aiLoading" class="spinner" style="width:12px;height:12px;"></span>
          <span v-else>⚡ Search with AI</span>
        </button>
      </div>

      <div v-if="aiFilterUiActive && lastAiQuery" class="ai-filter-prompt-row">
        <span class="ai-filter-prompt-label">AI filter</span>
        <span class="ai-filter-prompt-text" :title="lastAiQuery">“{{ lastAiQuery }}”</span>
        <button
          type="button"
          class="btn-icon ai-filter-prompt-clear"
          title="Clear AI filter"
          aria-label="Clear AI filter"
          @click="clearAiResults"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- Status filter pills -->
    <div class="flex gap-1 mt-2" style="flex-wrap:wrap;">
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
    <div class="mt-2" :class="{ 'hardware-table-section--raised': rowMenuOpenId !== null }">
      <!-- AI search loading state -->
      <div v-if="aiLoading" class="ai-loading-state">
        <span class="spinner ai-loading-spinner"></span>
        <p class="ai-loading-title">Searching with AI…</p>
        <p class="text-muted" style="font-size:.85rem; margin-top:.25rem;">
          Analyzing <strong>{{ allHardware.length }}</strong> records
          for <strong>"{{ aiSearchPrompt }}"</strong>
        </p>
      </div>
      <div
        v-else
        class="hardware-list-body"
        :class="{
          'hardware-list-body--pending': fetching && allHardware.length === 0,
          'hardware-list-body--refreshing': fetching && allHardware.length > 0,
        }"
      >
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th v-if="isAdmin" class="col-check">
                <input
                  ref="headerCheckboxRef"
                  type="checkbox"
                  class="row-checkbox"
                  :checked="allFilteredSelected"
                  :disabled="displayedRows.length === 0"
                  @change="toggleAllDisplayed"
                />
              </th>
              <th>Name</th>
              <th style="width:140px">Brand</th>
              <th style="width:104px">Status</th>
              <th style="width:132px">Purchase Date</th>
              <th style="width:90px">Action</th>
              <th v-if="isAdmin" class="col-actions" aria-label="Row menu"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in displayedRows"
              :key="item.id"
              :class="{ 'row-selected': selectedIds.has(item.id) }"
            >
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
                  type="button"
                  class="btn btn-sm btn-primary btn-table-action"
                  :disabled="rentingId === item.id"
                  @click="handleRent(item)"
                >
                  Rent
                </button>
                <span v-else class="text-muted" style="font-size:.8rem;">—</span>
              </td>
              <td v-if="isAdmin" class="col-actions">
                <div class="row-actions-wrap">
                  <button
                    type="button"
                    class="row-actions-trigger"
                    :class="{ 'is-open': rowMenuOpenId === item.id }"
                    :aria-expanded="rowMenuOpenId === item.id"
                    aria-haspopup="true"
                    aria-label="Actions for this row"
                    @click.stop="toggleRowMenu(item.id, $event)"
                  >
                    ⋮
                  </button>
                  <Transition name="row-menu">
                    <div
                      v-if="rowMenuOpenId === item.id"
                      class="row-actions-menu"
                      :style="rowMenuPositionStyle"
                      role="menu"
                      @click.stop
                    >
                      <button
                        type="button"
                        class="row-actions-item"
                        role="menuitem"
                        @click="openEditModal(item)"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        class="row-actions-item"
                        role="menuitem"
                        :disabled="rowActionBusyId === item.id"
                        @click="item.status === 'Repair' ? handleRowRestoreFromRepair(item) : handleRowSendToRepair(item)"
                      >
                        {{ item.status === 'Repair' ? 'Restore from repair' : 'Send to repair' }}
                      </button>
                      <button
                        type="button"
                        class="row-actions-item row-actions-item--danger"
                        role="menuitem"
                        :disabled="deletingId === item.id || rowActionBusyId === item.id"
                        @click="handleDelete(item)"
                      >
                        Delete
                      </button>
                    </div>
                  </Transition>
                </div>
              </td>
            </tr>
            <tr
              v-if="fetching && allHardware.length === 0 && showTableLoadingRow"
              class="table-loading-row"
            >
              <td :colspan="isAdmin ? 7 : 5">
                <div class="table-loading-cell" role="status" aria-live="polite">
                  <span class="spinner table-loading-spinner" aria-hidden="true" />
                  <p class="table-loading-label">Loading hardware…</p>
                </div>
              </td>
            </tr>
            <tr v-if="displayedRows.length === 0 && !fetching" class="table-empty-message-row">
              <td :colspan="isAdmin ? 7 : 5">
                <div class="empty-state">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
                  </svg>
                  <p>No hardware items found.</p>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      </div>
    </div>

    <div v-if="rowMenuOpenId !== null" class="row-menu-backdrop" @click="closeRowMenu"></div>

  </div>

  <!-- Backdrop for closing the add popover when clicking outside -->
  <div v-if="showAddForm" class="popover-backdrop" @click="closeAddForm"></div>

  <div
    v-if="showEditModal"
    class="edit-modal-backdrop"
    @click.self="closeEditModal"
  >
    <div class="edit-modal card" role="dialog" aria-labelledby="edit-modal-title" @click.stop>
      <div class="edit-modal-header">
        <h2 id="edit-modal-title" class="edit-modal-title">Edit hardware</h2>
        <button type="button" class="btn-icon" title="Close" aria-label="Close" @click="closeEditModal">✕</button>
      </div>
      <form class="edit-modal-body" @submit.prevent="submitEditModal">
        <div class="form-group">
          <label>Name *</label>
          <input v-model="editForm.name" class="input" required minlength="1" />
        </div>
        <div class="form-group mt-1">
          <label>Brand</label>
          <input v-model="editForm.brand" class="input" placeholder="Optional" />
        </div>
        <div class="form-group mt-1">
          <label>Purchase date</label>
          <input v-model="editForm.purchase_date" class="input" type="date" />
        </div>
        <div class="form-group mt-1">
          <label>Status</label>
          <select v-model="editForm.status">
            <option v-for="s in editStatusOptions" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div v-if="editModalError" class="alert alert-error mt-1" style="font-size:.8rem;">{{ editModalError }}</div>
        <div class="edit-modal-actions mt-2">
          <button type="button" class="btn btn-ghost btn-sm" @click="closeEditModal">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="editSaving">
            <span v-if="editSaving" class="spinner" style="width:12px;height:12px;"></span>
            <span v-else>Save</span>
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- Fixed toast — rent/action feedback, no layout shift -->
  <Transition name="toast">
    <div v-if="toast" class="action-toast" role="alert">
      <span>{{ toast }}</span>
      <button class="btn-icon" style="margin-left:.5rem;" @click="toast = ''">×</button>
    </div>
  </Transition>
  <Transition name="toast">
    <div v-if="errorToast" class="action-toast action-toast--error" role="alert">
      <span>{{ errorToast }}</span>
      <button class="btn-icon" style="margin-left:.5rem; flex-shrink:0;" @click="dismissErrorToast">×</button>
    </div>
  </Transition>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watchEffect } from 'vue'
import { listHardware, rentHardware, aiSearch, createHardware, deleteHardware, updateHardware } from '../api/client.js'
import { getStoredUser } from '../api/client.js'
import { useDelayedTableLoading } from '../composables/useDelayedTableLoading.js'

const AI_FILTER_SESSION_KEY = 'hardware_hub_dashboard_ai_filter'
const AUTO_REFRESH_MS = 60_000

let hardwareLoadInFlight = false
let hardwareRefreshTimer = null

const user    = getStoredUser()
const isAdmin = user?.role === 'admin'

// ── Hardware data ───────────────────────────────────────────────────────────
const allHardware = ref([])
const fetching    = ref(true)
const error       = ref('')

const hardwareListEmpty = computed(() => allHardware.value.length === 0)
const showTableLoadingRow = useDelayedTableLoading(fetching, hardwareListEmpty)

const searchQuery  = ref('')
const statusFilter = ref('All')

// AI list filter (must exist before persist / reapply helpers)
const aiLoading       = ref(false)
const aiResults       = ref(null)
const lastAiQuery     = ref('')
const aiSearchPrompt  = ref('')

/** Read saved AI prompt synchronously so the first paint matches filter mode (no placeholder flicker). */
function hydrateAiFilterMetadataFromSession() {
  const raw = sessionStorage.getItem(AI_FILTER_SESSION_KEY)
  if (!raw) return
  try {
    const { query, ids } = JSON.parse(raw)
    if (typeof query !== 'string' || !query.trim() || !Array.isArray(ids)) {
      sessionStorage.removeItem(AI_FILTER_SESSION_KEY)
      return
    }
    lastAiQuery.value = query
  } catch {
    sessionStorage.removeItem(AI_FILTER_SESSION_KEY)
  }
}
hydrateAiFilterMetadataFromSession()

function clearAiResults() {
  aiResults.value      = null
  lastAiQuery.value    = ''
  aiSearchPrompt.value = ''
  searchQuery.value    = ''
  sessionStorage.removeItem(AI_FILTER_SESSION_KEY)
}

function persistAiFilter() {
  if (lastAiQuery.value && aiResults.value !== null) {
    sessionStorage.setItem(
      AI_FILTER_SESSION_KEY,
      JSON.stringify({
        query: lastAiQuery.value,
        ids: aiResults.value.map((r) => r.id),
      })
    )
  } else {
    sessionStorage.removeItem(AI_FILTER_SESSION_KEY)
  }
}

function reapplyAiFilterFromStorage() {
  const raw = sessionStorage.getItem(AI_FILTER_SESSION_KEY)
  if (!raw) return
  try {
    const { query, ids } = JSON.parse(raw)
    if (!query || !Array.isArray(ids)) {
      sessionStorage.removeItem(AI_FILTER_SESSION_KEY)
      return
    }
    const byId = Object.fromEntries(allHardware.value.map((h) => [h.id, h]))
    const rows = ids.map((id) => byId[id]).filter(Boolean)
    if (rows.length === 0 && ids.length > 0) {
      clearAiResults()
      return
    }
    lastAiQuery.value = query
    aiResults.value = rows
    if (rows.length < ids.length) {
      persistAiFilter()
    }
  } catch {
    sessionStorage.removeItem(AI_FILTER_SESSION_KEY)
  }
}

async function loadHardware() {
  if (hardwareLoadInFlight) return
  hardwareLoadInFlight = true
  fetching.value = true
  error.value   = ''
  try {
    allHardware.value = await listHardware()
  } catch (err) {
    error.value = err.message || 'Failed to load hardware.'
  } finally {
    fetching.value = false
    hardwareLoadInFlight = false
    reapplyAiFilterFromStorage()
  }
}

function onDashboardVisibilityChange() {
  if (document.visibilityState === 'visible') loadHardware()
}

onMounted(() => {
  loadHardware()
  hardwareRefreshTimer = window.setInterval(loadHardware, AUTO_REFRESH_MS)
  document.addEventListener('visibilitychange', onDashboardVisibilityChange)
})

onUnmounted(() => {
  closeRowMenu()
  if (hardwareRefreshTimer !== null) {
    window.clearInterval(hardwareRefreshTimer)
    hardwareRefreshTimer = null
  }
  document.removeEventListener('visibilitychange', onDashboardVisibilityChange)
})

// ── Local filter ─────────────────────────────────────────────────────────────
function setStatusFilter(s) {
  statusFilter.value = s
}

function filterLocally() {
  // reactive — displayedRows recomputes automatically
}

function applyStatusAndSearchFilter(rows) {
  let out = rows
  if (statusFilter.value !== 'All') {
    out = out.filter((h) => h.status === statusFilter.value)
  }
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    out = out.filter(
      (h) =>
        h.name.toLowerCase().includes(q) ||
        (h.brand ?? '').toLowerCase().includes(q) ||
        (h.status ?? '').toLowerCase().includes(q) ||
        (h.notes ?? '').toLowerCase().includes(q) ||
        (h.purchase_date ?? '').toString().includes(q)
    )
  }
  return out
}

const locallyFiltered = computed(() => applyStatusAndSearchFilter(allHardware.value))

/** True while AI filter applies: has rows or still restoring prompt from session before rows hydrate. */
const aiFilterUiActive = computed(
  () => aiResults.value !== null || !!lastAiQuery.value
)

async function runAiSearch() {
  const q = searchQuery.value.trim()
  if (!q || aiResults.value !== null || lastAiQuery.value) return
  aiSearchPrompt.value = q
  aiLoading.value = true
  error.value     = ''
  try {
    const results = await aiSearch(q)
    aiResults.value   = results
    lastAiQuery.value = q
    searchQuery.value = ''
    persistAiFilter()
  } catch (err) {
    showErrorToast(err.message || 'AI search failed.')
  } finally {
    aiLoading.value = false
    if (aiResults.value === null) {
      aiSearchPrompt.value = ''
    }
  }
}

// ── Search placeholder ────────────────────────────────────────────────────────
const searchPlaceholder = computed(() =>
  aiResults.value !== null || lastAiQuery.value
    ? 'Filter within AI results (name, brand, status, date\u2026)'
    : 'Filter by name, brand, status, date, or search with AI\u2026'
)

// ── Displayed rows ──────────────────────────────────────────────────────────
const displayedRows = computed(() => {
  if (aiResults.value !== null) {
    return applyStatusAndSearchFilter(aiResults.value)
  }
  if (lastAiQuery.value) {
    return []
  }
  return locallyFiltered.value
})

// ── Toast (fixed-position, no layout shift) ───────────────────────────────────
const toast = ref('')
let toastTimer = null
function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 4000)
}

const errorToast = ref('')
let errorToastTimer = null
function showErrorToast(msg) {
  errorToast.value = msg
  clearTimeout(errorToastTimer)
  errorToastTimer = setTimeout(() => { errorToast.value = '' }, 10_000)
}
function dismissErrorToast() {
  errorToast.value = ''
  clearTimeout(errorToastTimer)
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

// ── Row actions menu (admin) — fixed position, right-aligned to ⋮ (no table overflow flash) ─
const rowMenuOpenId = ref(null)
const rowActionBusyId = ref(null)
const rowMenuPosition = ref({ top: '0px', right: '0px' })
let rowMenuWindowListenersCleanup = null

const rowMenuPositionStyle = computed(() => {
  if (rowMenuOpenId.value === null) return {}
  const p = rowMenuPosition.value
  return { top: p.top, right: p.right }
})

function closeRowMenu() {
  rowMenuOpenId.value = null
  if (rowMenuWindowListenersCleanup) {
    rowMenuWindowListenersCleanup()
    rowMenuWindowListenersCleanup = null
  }
}

function bindRowMenuWindowListeners() {
  if (rowMenuWindowListenersCleanup) return
  const onDismiss = () => closeRowMenu()
  window.addEventListener('scroll', onDismiss, true)
  window.addEventListener('resize', onDismiss)
  rowMenuWindowListenersCleanup = () => {
    window.removeEventListener('scroll', onDismiss, true)
    window.removeEventListener('resize', onDismiss)
  }
}

function openRowMenu(id, triggerEl) {
  if (triggerEl instanceof HTMLElement) {
    const r = triggerEl.getBoundingClientRect()
    rowMenuPosition.value = {
      top: `${r.bottom + 4}px`,
      right: `${document.documentElement.clientWidth - r.right}px`,
    }
  }
  rowMenuOpenId.value = id
  bindRowMenuWindowListeners()
}

function toggleRowMenu(id, event) {
  if (rowMenuOpenId.value === id) {
    closeRowMenu()
    return
  }
  openRowMenu(id, event?.currentTarget)
}

function applyHardwareRead(updated) {
  const id = updated.id
  const patch = (row) => {
    if (!row || row.id !== id) return
    row.name = updated.name
    row.brand = updated.brand
    row.purchase_date = updated.purchase_date
    row.status = updated.status
    row.notes = updated.notes
  }
  for (const h of allHardware.value) patch(h)
  if (aiResults.value !== null) {
    for (const h of aiResults.value) patch(h)
    persistAiFilter()
  }
}

async function handleRowSendToRepair(item) {
  if (item.status === 'Repair') return
  closeRowMenu()
  if (!confirm(`Send “${item.name}” to repair?`)) return
  rowActionBusyId.value = item.id
  error.value = ''
  try {
    const updated = await updateHardware(item.id, { status: 'Repair' })
    applyHardwareRead(updated)
    showToast(`“${item.name}” sent to repair.`)
  } catch (err) {
    error.value = err.message || 'Failed to send item to repair.'
  } finally {
    rowActionBusyId.value = null
  }
}

async function handleRowRestoreFromRepair(item) {
  if (item.status !== 'Repair') return
  closeRowMenu()
  if (!confirm(`Restore “${item.name}” from repair (set status to Available)?`)) return
  rowActionBusyId.value = item.id
  error.value = ''
  try {
    const updated = await updateHardware(item.id, { status: 'Available' })
    applyHardwareRead(updated)
    showToast(`“${item.name}” restored from repair.`)
  } catch (err) {
    error.value = err.message || 'Failed to restore item from repair.'
  } finally {
    rowActionBusyId.value = null
  }
}

// ── Edit hardware modal (admin) ─────────────────────────────────────────────
const showEditModal = ref(false)
const editTargetId = ref(null)
const editOriginalStatus = ref('Available')
const editSaving = ref(false)
const editModalError = ref('')
const editForm = reactive({
  name: '',
  brand: '',
  purchase_date: '',
  status: 'Available',
})

const editStatusOptions = computed(() => {
  const o = editOriginalStatus.value
  if (o === 'Available') return ['Available', 'Repair']
  if (o === 'In Use') return ['In Use', 'Repair']
  if (o === 'Repair') return ['Repair', 'Available']
  return ['Available', 'In Use', 'Repair']
})

function openEditModal(item) {
  closeRowMenu()
  editTargetId.value = item.id
  editOriginalStatus.value = item.status
  editForm.name = item.name
  editForm.brand = item.brand ?? ''
  editForm.purchase_date = item.purchase_date ?? ''
  editForm.status = item.status
  editModalError.value = ''
  showEditModal.value = true
}

function closeEditModal() {
  showEditModal.value = false
  editTargetId.value = null
  editModalError.value = ''
}

async function submitEditModal() {
  if (!editTargetId.value) return
  const name = editForm.name.trim()
  if (!name) {
    editModalError.value = 'Name is required.'
    return
  }
  if (!confirm(`Save changes to “${name}”?`)) return
  editModalError.value = ''
  editSaving.value = true
  error.value = ''
  try {
    const payload = {
      name,
      brand: editForm.brand.trim() || null,
      purchase_date: editForm.purchase_date || null,
      status: editForm.status,
    }
    const updated = await updateHardware(editTargetId.value, payload)
    applyHardwareRead(updated)
    showToast('Changes saved.')
    closeEditModal()
  } catch (err) {
    editModalError.value = err.message || 'Failed to save changes.'
  } finally {
    editSaving.value = false
  }
}

// ── Delete (admin only) ───────────────────────────────────────────────────────
const deletingId = ref(null)
const bulkDeleting = ref(false)

async function handleDelete(item) {
  closeRowMenu()
  if (!confirm(`Delete "${item.name}"?\n\nThis will permanently remove the item and all its rental history.`)) return
  deletingId.value = item.id
  error.value      = ''
  try {
    await deleteHardware(item.id)
    allHardware.value = allHardware.value.filter(h => h.id !== item.id)
    if (aiResults.value !== null) {
      aiResults.value = aiResults.value.filter(h => h.id !== item.id)
      persistAiFilter()
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
  if (aiResults.value !== null) {
    persistAiFilter()
  }
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
    showToast(`✓ "${created.name}" added.`)
  } catch (err) {
    addError.value = err.message || 'Failed to add hardware.'
  } finally {
    addLoading.value = false
  }
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
.page {
  position: relative;
  isolation: isolate;
}
/* Whole page above .popover-backdrop (199) so Add Hardware form receives clicks */
.page--add-popover-open {
  z-index: 200;
}

.hardware-table-section--raised {
  position: relative;
  z-index: 10;
}

/* Row ⋮ menu — full-screen hit target; must stay below .hardware-table-section--raised */
.row-menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9;
  background: transparent;
}
.col-actions {
  width: 40px;
  padding-left: 0;
  text-align: right;
  vertical-align: middle;
  overflow: visible;
}
.row-actions-wrap {
  position: relative;
  display: flex;
  justify-content: flex-end;
  overflow: visible;
}
.row-actions-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  padding: 0;
  border: none;
  border-radius: var(--radius);
  background: transparent;
  color: var(--text-muted);
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  transition: background .15s, color .15s;
}
.row-actions-trigger:hover,
.row-actions-trigger.is-open {
  background: var(--bg);
  color: var(--text);
}
.row-actions-menu {
  position: fixed;
  left: auto;
  min-width: 11rem;
  padding: 0.35rem 0;
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  z-index: 50;
  transform-origin: top right;
}
.row-actions-item {
  display: block;
  width: 100%;
  padding: 0.5rem 0.85rem;
  border: none;
  background: none;
  font: inherit;
  font-size: 0.82rem;
  text-align: left;
  color: var(--text);
  cursor: pointer;
  transition: background .12s;
}
.row-actions-item:hover:not(:disabled) {
  background: var(--bg);
}
.row-actions-item:disabled {
  opacity: 0.45;
  cursor: default;
}
.row-actions-item--danger {
  color: #b91c1c;
}
.row-actions-item--danger:hover:not(:disabled) {
  background: rgba(220, 38, 38, 0.08);
}

/* Edit modal (teleported) */
.edit-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.45);
}
.edit-modal {
  width: 100%;
  max-width: 420px;
  max-height: 90vh;
  overflow: auto;
  padding: 0;
  margin: 0;
}
.edit-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border);
}
.edit-modal-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}
.edit-modal-body {
  padding: 1rem;
}
.edit-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.add-hardware-anchor {
  position: relative;
}

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

/* Row ⋮ menu — opens from the right edge (transform origin) */
.row-menu-enter-active,
.row-menu-leave-active {
  transition: opacity 0.12s ease, transform 0.12s ease;
  transform-origin: top right;
}
.row-menu-enter-from,
.row-menu-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
  transform-origin: top right;
}

/* ── Checkbox column ──────────────────────────────────────────────────── */
.col-check {
  width: 32px;
  padding-right: 0;
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

/* ── Bulk delete button ───────────────────────────────────────────────── */
.bulk-delete-btn {
  background: rgba(220, 38, 38, .08);
  color: #dc2626;
  border: 1px solid rgba(220, 38, 38, .25);
}
.bulk-delete-btn:hover {
  background: rgba(220, 38, 38, .15);
}

/* ── Search row: rounded bar + separate primary button (matches Add Hardware height) ─ */
.search-ai-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  max-width: 100%;
}
.search-bar-extended {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--white, #fff);
  padding: 0.4rem 0.5rem 0.4rem 0.75rem;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.search-bar-extended:focus-within {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
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
  font-size: 0.9rem;
  color: var(--text);
  min-width: 0;
}
.search-bar-extended input::placeholder {
  color: var(--text-muted);
}
.search-bar-extended input:disabled {
  opacity: 0.7;
}
.search-bar-ai-active {
  border-color: var(--brand);
  background: rgba(37, 99, 235, 0.04);
}
.ai-search-cta {
  flex-shrink: 0;
  white-space: nowrap;
}

.ai-filter-prompt-row {
  display: flex;
  align-items: center;
  gap: .5rem;
  margin-top: .5rem;
  padding: .4rem .65rem;
  background: rgba(37, 99, 235, .08);
  border: 1px solid rgba(37, 99, 235, .2);
  border-radius: var(--radius);
  font-size: .82rem;
}
.ai-filter-prompt-label {
  font-size: .68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .04em;
  color: var(--brand);
  flex-shrink: 0;
}
.ai-filter-prompt-text {
  flex: 1;
  min-width: 0;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ai-filter-prompt-clear {
  flex-shrink: 0;
  color: var(--text-muted);
}
.ai-filter-prompt-clear:hover {
  color: var(--text);
}

.search-clear-btn {
  flex-shrink: 0;
  font-size: .9rem;
  color: var(--text-muted);
}
.search-clear-btn:hover { color: var(--text); }

/* ── AI loading state ─────────────────────────────────────────────────── */
.hardware-list-body--pending {
  min-height: 0;
}

.table-empty-message-row td {
  padding: 0;
  vertical-align: middle;
}
.table-empty-message-row .empty-state {
  padding: 3rem 1.5rem;
}
.hardware-list-body--refreshing {
  opacity: 0.92;
  transition: opacity 0.12s ease-out;
}

.ai-loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  gap: .75rem;
  text-align: center;
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
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
  background: var(--white, #fff);
  color: var(--text);
  border: 1px solid var(--border);
  padding: .6rem 1rem;
  border-radius: var(--radius);
  font-size: .85rem;
  box-shadow: var(--shadow-md);
  max-width: 360px;
}
.action-toast--error {
  z-index: 450;
  border-color: #fecaca;
  background: #fef2f2;
  color: #7f1d1d;
  box-shadow: 0 8px 24px rgba(127, 29, 29, 0.12);
}
.toast-enter-active, .toast-leave-active { transition: opacity .2s, transform .2s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }
</style>
