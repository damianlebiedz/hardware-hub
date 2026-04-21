<template>
  <div class="page">
    <div class="flex items-center justify-between" style="flex-wrap:wrap; gap:1rem;">
      <div>
        <h1>My Rentals</h1>
        <p class="text-muted mt-1">Items you currently have checked out.</p>
      </div>
      <button class="btn btn-ghost btn-sm" @click="loadRentals">↻ Refresh</button>
    </div>

    <div v-if="error"   class="alert alert-error mt-2">{{ error }}</div>
    <div v-if="success" class="alert alert-success mt-2">{{ success }}</div>

    <div class="mt-2">
      <div v-if="loading" style="text-align:center; padding:3rem;">
        <span class="spinner"></span>
      </div>
      <div v-else-if="rentals.length === 0" class="empty-state card">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M20 7H4a2 2 0 00-2 2v6a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2z"/>
          <path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/>
        </svg>
        <p>You have no active rentals.</p>
        <RouterLink to="/dashboard" class="btn btn-ghost btn-sm" style="margin-top:.75rem;">
          Browse hardware →
        </RouterLink>
      </div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Rental ID</th>
              <th>Hardware</th>
              <th>Brand</th>
              <th>Rented At</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rental in rentals" :key="rental.id">
              <td class="text-muted">#{{ rental.id }}</td>
              <td>
                <strong>{{ rental.hardware_name || `Hardware #${rental.hardware_id}` }}</strong>
              </td>
              <td>{{ rental.hardware_brand || '—' }}</td>
              <td class="text-muted">{{ formatDate(rental.rented_at) }}</td>
              <td>
                <button
                  class="btn btn-sm btn-danger"
                  :disabled="returningId === rental.id"
                  @click="handleReturn(rental)"
                >
                  <span v-if="returningId === rental.id" class="spinner"></span>
                  <span v-else>Return</span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { myRentals, returnHardware, listHardware } from '../api/client.js'
import { getStoredUser } from '../api/client.js'

const user = getStoredUser()

const rentals     = ref([])
const loading     = ref(false)
const error       = ref('')
const success     = ref('')
const returningId = ref(null)

async function loadRentals() {
  if (!user) return
  loading.value = true
  error.value   = ''
  success.value = ''
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
    loading.value = false
  }
}

onMounted(loadRentals)

async function handleReturn(rental) {
  returningId.value = rental.id
  error.value       = ''
  success.value     = ''
  try {
    await returnHardware(rental.id)
    success.value = `✓ "${rental.hardware_name ?? 'Item'}" has been returned successfully.`
    // Remove from list immediately
    rentals.value = rentals.value.filter(r => r.id !== rental.id)
  } catch (err) {
    error.value = err.message || 'Failed to return item.'
  } finally {
    returningId.value = null
  }
}

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
