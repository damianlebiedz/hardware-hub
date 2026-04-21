<template>
  <div class="page">

    <!-- Header row -->
    <div class="flex items-center justify-between" style="flex-wrap:wrap; gap:1rem;">
      <div>
        <h1>Hardware Dashboard</h1>
        <p class="text-muted mt-1">Browse and rent company equipment.</p>
      </div>
      <button class="btn btn-ghost btn-sm" @click="loadHardware" title="Refresh list">
        ↻ Refresh
      </button>
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
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Rent success toast -->
    <div v-if="rentSuccess" class="alert alert-success mt-2">{{ rentSuccess }}</div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { listHardware, rentHardware, aiSearch } from '../api/client.js'
import { getStoredUser } from '../api/client.js'

const user = getStoredUser()

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
    // Update status locally for immediate feedback
    item.status = 'In Use'
  } catch (err) {
    error.value = err.message || 'Failed to rent item.'
  } finally {
    rentingId.value = null
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
