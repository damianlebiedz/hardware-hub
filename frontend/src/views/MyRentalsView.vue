<template>
  <div class="page">
    <div class="flex items-center justify-between" style="flex-wrap:wrap; gap:1rem;">
      <div>
        <h1>My Rentals</h1>
        <p class="text-muted mt-1">Items you currently have checked out.</p>
      </div>
    </div>

    <div v-if="error" class="alert alert-error mt-2">{{ error }}</div>

    <div
      class="mt-2 rentals-body"
      :class="{
        'rentals-body--pending': fetching && rentals.length === 0,
        'rentals-body--refreshing': fetching && rentals.length > 0,
      }"
    >
      <template v-if="!(fetching && rentals.length === 0)">
      <div v-if="rentals.length === 0" class="empty-state card">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M20 7H4a2 2 0 00-2 2v6a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2z"/>
          <path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/>
        </svg>
        <p>You have no active rentals.</p>
        <RouterLink
          to="/dashboard"
          class="btn btn-ghost btn-sm browse-hardware-link"
          style="margin-top:.75rem;"
        >
          Browse hardware
        </RouterLink>
      </div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Hardware</th>
              <th style="width:130px">Brand</th>
              <th style="width:160px">Rented At</th>
              <th style="width:110px">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rental in rentals" :key="rental.id">
              <td style="white-space:normal">
                <strong>{{ rental.hardware_name || `Hardware #${rental.hardware_id}` }}</strong>
              </td>
              <td>{{ rental.hardware_brand || '—' }}</td>
              <td class="text-muted">{{ formatDate(rental.rented_at) }}</td>
              <td style="text-align: center;">
                <button
                  type="button"
                  class="btn btn-sm btn-danger btn-return-narrow"
                  :disabled="returningId === rental.id"
                  @click="handleReturn(rental)"
                >
                  Return
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      </template>
    </div>
  </div>

  <Transition name="toast">
    <div v-if="toast" class="action-toast" role="alert">
      <span>{{ toast }}</span>
      <button style="margin-left:.5rem; background:none; border:none; color:inherit; cursor:pointer; font-size:.875rem; line-height:1;" @click="toast = ''">×</button>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import { myRentals, returnHardware, listHardware } from '../api/client.js'
import { getStoredUser } from '../api/client.js'

const user = getStoredUser()

const AUTO_REFRESH_MS = 60_000
let rentalsRefreshTimer = null

const rentals     = ref([])
const fetching    = ref(false)
const error       = ref('')
const returningId = ref(null)
const toast       = ref('')
let toastTimer    = null

function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 4000)
}

async function loadRentals() {
  if (!user) return
  if (fetching.value) return
  error.value = ''
  fetching.value = true
  try {
    const [rentalList, hardwareList] = await Promise.all([
      myRentals(user.id),
      listHardware(),
    ])
    // Join hardware name/brand onto each rental for display
    const hwMap = Object.fromEntries(hardwareList.map(h => [h.id, h]))
    rentals.value = rentalList.map(r => ({
      ...r,
      hardware_name:  hwMap[r.hardware_id]?.name  ?? null,
      hardware_brand: hwMap[r.hardware_id]?.brand ?? null,
    }))
  } catch (err) {
    error.value = err.message || 'Failed to load rentals.'
  } finally {
    fetching.value = false
  }
}

function onRentalsVisibilityChange() {
  if (document.visibilityState === 'visible') loadRentals()
}

onMounted(() => {
  loadRentals()
  rentalsRefreshTimer = window.setInterval(loadRentals, AUTO_REFRESH_MS)
  document.addEventListener('visibilitychange', onRentalsVisibilityChange)
})

onUnmounted(() => {
  if (rentalsRefreshTimer !== null) {
    window.clearInterval(rentalsRefreshTimer)
    rentalsRefreshTimer = null
  }
  document.removeEventListener('visibilitychange', onRentalsVisibilityChange)
})

async function handleReturn(rental) {
  returningId.value = rental.id
  error.value       = ''
  try {
    await returnHardware(rental.id)
    showToast(`✓ "${rental.hardware_name ?? 'Item'}" returned successfully.`)
    rentals.value = rentals.value.filter(r => r.id !== rental.id)
  } catch (err) {
    error.value = err.message || 'Failed to return item.'
  } finally {
    returningId.value = null
  }
}

// ── helpers ───────────────────────────────────────────────────────────────────
function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  } catch {
    return iso
  }
}
</script>

<style scoped>
.browse-hardware-link {
  text-decoration: none;
}
.browse-hardware-link:hover,
.browse-hardware-link:focus-visible {
  text-decoration: none;
}

.rentals-body--pending {
  min-height: 10rem;
}
.rentals-body--refreshing {
  opacity: 0.92;
  transition: opacity 0.12s ease-out;
}

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
  border-radius: var(--radius, 8px);
  font-size: .85rem;
  box-shadow: var(--shadow-md, 0 4px 6px rgba(0,0,0,.07), 0 2px 4px rgba(0,0,0,.06));
  max-width: 360px;
}
.toast-enter-active, .toast-leave-active { transition: opacity .2s, transform .2s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }
</style>
