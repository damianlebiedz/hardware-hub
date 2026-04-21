<template>
  <div class="page">

    <!-- Header row -->
    <div class="flex items-center justify-between" style="flex-wrap:wrap; gap:1rem;">
      <div>
        <h1>Hardware Dashboard</h1>
        <p class="text-muted mt-1">Browse and rent company equipment.</p>
      </div>
      <div class="flex items-center gap-2">
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
                <div class="form-group mt-1">
                  <label>Notes</label>
                  <input v-model="newItem.notes" class="input" placeholder="Optional notes…" />
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

    <!-- Search bar + AI toggle -->
    <div class="flex items-center gap-2 mt-2" style="flex-wrap:wrap;">
      <div class="search-bar" :class="{ 'ai-active': aiMode && aiResults !== null }">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          v-model="searchQuery"
          :placeholder="searchPlaceholder"
          :disabled="aiMode && aiResults !== null"
          @keyup.enter="aiMode ? runAiSearch() : undefined"
          @input="!aiMode ? filterLocally() : undefined"
        />
        <!-- X button — clears AI results -->
        <button v-if="aiMode && aiResults !== null" class="btn-icon" @click="clearAiResults" title="Clear AI results">
          ✕
        </button>
        <!-- Search button — only visible in AI mode before results arrive -->
        <button v-else-if="aiMode" class="btn btn-sm btn-primary" :disabled="aiLoading || !searchQuery.trim()" @click="runAiSearch">
          <span v-if="aiLoading" class="spinner"></span>
          <span v-else>Search</span>
        </button>
      </div>

      <!-- AI toggle -->
      <div class="ai-toggle-wrap">
        <label class="toggle">
          <input type="checkbox" v-model="aiMode" @change="onAiToggle" />
          <span class="toggle-slider"></span>
        </label>
        <span :style="{ color: aiMode ? 'var(--brand)' : 'var(--text-muted)' }">
          AI Search {{ aiMode ? 'ON' : 'OFF' }}
        </span>
      </div>
    </div>

    <!-- Status filter pills (only in standard mode) -->
    <div v-if="!aiMode" class="flex gap-1 mt-2" style="flex-wrap:wrap;">
      <button
        v-for="s in ['All', 'Available', 'In Use', 'Repair']"
        :key="s"
        class="btn btn-sm"
        :class="statusFilter === s ? 'btn-primary' : 'btn-ghost'"
        @click="setStatusFilter(s)"
      >{{ s }}</button>
    </div>

    <!-- AI mode label when showing AI results -->
    <div v-if="aiMode && aiResults !== null" class="alert alert-info mt-2">
      Showing AI search results for <strong>"{{ lastAiQuery }}"</strong> — click ✕ to return to the full list.
    </div>

    <div v-if="error" class="alert alert-error mt-2">{{ error }}</div>

    <!-- Table -->
    <div class="mt-2">
      <div v-if="loading" style="text-align:center; padding:3rem;">
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
              <th>ID</th>
              <th>Name</th>
              <th>Brand</th>
              <th>Status</th>
              <th>Purchase Date</th>
              <th>Notes</th>
              <th>Action</th>
              <th v-if="isAdmin"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in displayedRows" :key="item.id">
              <td class="text-muted">{{ item.id }}</td>
              <td><strong>{{ item.name }}</strong></td>
              <td>{{ item.brand || '—' }}</td>
              <td>
                <span class="badge" :class="statusClass(item.status)">{{ item.status }}</span>
              </td>
              <td class="text-muted">{{ item.purchase_date ?? '—' }}</td>
              <td style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"
                  :title="item.notes">{{ item.notes || '—' }}</td>
              <td>
                <button
                  v-if="item.status === 'Available'"
                  class="btn btn-sm btn-primary"
                  :disabled="rentingId === item.id"
                  @click="handleRent(item)"
                >
                  <span v-if="rentingId === item.id" class="spinner"></span>
                  <span v-else>Rent</span>
                </button>
                <span v-else class="text-muted" style="font-size:.8rem;">—</span>
              </td>
              <!-- Delete button — admin only -->
              <td v-if="isAdmin">
                <button
                  class="btn btn-sm btn-danger delete-btn"
                  :disabled="deletingId === item.id"
                  @click="handleDelete(item)"
                  title="Delete this item"
                >
                  <span v-if="deletingId === item.id" class="spinner"></span>
                  <span v-else>✕</span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Rent success toast -->
    <div v-if="rentSuccess" class="alert alert-success mt-2">{{ rentSuccess }}</div>

  </div>

  <!-- Backdrop for closing the add popover when clicking outside -->
  <div v-if="showAddForm" class="popover-backdrop" @click="closeAddForm"></div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { listHardware, rentHardware, aiSearch, createHardware, deleteHardware } from '../api/client.js'
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
      (h.brand ?? '').toLowerCase().includes(q)
    )
  }
  return rows
})

// ── AI search ────────────────────────────────────────────────────────────────
const aiMode      = ref(false)
const aiLoading   = ref(false)
const aiResults   = ref(null)   // null = no AI results yet; array = showing AI results
const lastAiQuery = ref('')

function onAiToggle() {
  clearAiResults()
}

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

// ── Search placeholder text ──────────────────────────────────────────────────
const searchPlaceholder = computed(() =>
  aiMode.value
    ? 'Natural language: broken Apple laptops…'
    : 'Filter by name or brand…'
)

// ── Displayed rows ──────────────────────────────────────────────────────────
const displayedRows = computed(() =>
  aiMode.value && aiResults.value !== null
    ? aiResults.value
    : locallyFiltered.value
)

// ── Rent ─────────────────────────────────────────────────────────────────────
const rentingId   = ref(null)
const rentSuccess = ref('')

async function handleRent(item) {
  if (!user) { error.value = 'You must be logged in to rent.'; return }
  rentingId.value   = item.id
  rentSuccess.value = ''
  error.value       = ''
  try {
    await rentHardware(user.id, item.id)
    rentSuccess.value = `✓ "${item.name}" has been rented to you.`
    item.status = 'In Use'
  } catch (err) {
    error.value = err.message || 'Failed to rent item.'
  } finally {
    rentingId.value = null
  }
}

// ── Delete (admin only) ───────────────────────────────────────────────────────
const deletingId = ref(null)

async function handleDelete(item) {
  if (!confirm(`Delete "${item.name}"?\n\nThis will permanently remove the item and all its rental history.`)) return
  deletingId.value = item.id
  error.value      = ''
  try {
    await deleteHardware(item.id)
    allHardware.value = allHardware.value.filter(h => h.id !== item.id)
  } catch (err) {
    error.value = err.message || 'Failed to delete item.'
  } finally {
    deletingId.value = null
  }
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
  notes: '',
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
  newItem.value  = { name: '', brand: '', purchase_date: '', status: 'Available', notes: '' }
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
      notes:         newItem.value.notes.trim() || null,
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

/* ── Delete button subtle styling ─────────────────────────────────────── */
.delete-btn {
  padding: .25rem .55rem;
  font-size: .8rem;
  min-width: 28px;
}
</style>
