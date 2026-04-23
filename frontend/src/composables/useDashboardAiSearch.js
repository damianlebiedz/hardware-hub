import { ref, computed } from 'vue'
import { aiSearch } from '../api/client.js'

const AI_FILTER_SESSION_KEY = 'hardware_hub_dashboard_ai_filter'

// Module scope: survives client-side navigation away from the dashboard
const aiLoading = ref(false)
const aiResults = ref(null)
const lastAiQuery = ref('')
const aiSearchPrompt = ref('')

function hydrateLastQueryFromSession() {
  if (lastAiQuery.value) return
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

/**
 * @param {object} deps
 * @param {import('vue').Ref<object[]>} deps.allHardware
 * @param {import('vue').Ref<string>} deps.searchQuery
 * @param {import('vue').Ref<string>} deps.error
 * @param {(msg: string) => void} deps.showErrorToast
 */
export function useDashboardAiSearch({ allHardware, searchQuery, error, showErrorToast }) {
  hydrateLastQueryFromSession()

  function clearAiResults() {
    aiResults.value = null
    lastAiQuery.value = ''
    aiSearchPrompt.value = ''
    searchQuery.value = ''
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

  const aiFilterUiActive = computed(
    () => aiResults.value !== null || !!lastAiQuery.value
  )

  const searchPlaceholder = computed(() =>
    aiResults.value !== null || lastAiQuery.value
      ? 'Filter within AI results (name, brand, status, date\u2026)'
      : 'Filter by name, brand, status, date, or search with AI\u2026'
  )

  async function runAiSearch() {
    const q = searchQuery.value.trim()
    if (!q || aiResults.value !== null || lastAiQuery.value) return
    aiSearchPrompt.value = q
    aiLoading.value = true
    error.value = ''
    try {
      const results = await aiSearch(q)
      aiResults.value = results
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

  return {
    aiLoading,
    aiResults,
    lastAiQuery,
    aiSearchPrompt,
    aiFilterUiActive,
    searchPlaceholder,
    clearAiResults,
    persistAiFilter,
    reapplyAiFilterFromStorage,
    runAiSearch,
  }
}
