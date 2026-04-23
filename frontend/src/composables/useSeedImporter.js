import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { aiSeedPreview, plainSeed } from '../api/client.js'

const SESSION_KEY = 'hardware_hub_ai_preview'
const REJECTED_SESSION_KEY = 'hardware_hub_plain_rejected'

// ── Module-level state (survives leaving /admin while the SPA is open) ───────
const fileInputRef = ref(null)
const aiMode = ref(false)
const seedStep = ref('idle') // 'idle' | 'previewing' | 'importing'
const seedError = ref('')
const seedPayload = ref([])
const seedFileName = ref('')
const seedRecordCount = ref(0)
const showRawModal = ref(false)

const previewResult = ref(null)
const accepted = reactive(new Set())
const showReviewOverlay = ref(false)

const plainSeedResult = ref(null)
const showRejectedOverlay = ref(false)

const hasProposals = computed(() => previewResult.value !== null)
const correctedCount = computed(
  () => previewResult.value?.records.filter((r) => r.changes.length > 0).length ?? 0
)
const cleanCount = computed(
  () => previewResult.value?.records.filter((r) => r.changes.length === 0).length ?? 0
)

const showToast = ref(false)
const toastMessage = ref('')
let toastTimer = null

const showErrorToast = ref(false)
const errorToastMessage = ref('')
let errorToastTimer = null

// ── Session persistence ──────────────────────────────────────────────────────
function saveSession() {
  if (previewResult.value) {
    sessionStorage.removeItem(REJECTED_SESSION_KEY)
    sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({
        result: previewResult.value,
        acceptedIndices: [...accepted],
        rawPayload: seedPayload.value,
        rawFileName: seedFileName.value,
      })
    )
  } else {
    sessionStorage.removeItem(SESSION_KEY)
  }
}

function restorePlainFromSession() {
  const savedPlain = sessionStorage.getItem(REJECTED_SESSION_KEY)
  if (!savedPlain) return
  try {
    const data = JSON.parse(savedPlain)
    if (data && typeof data === 'object' && data.result && Array.isArray(data.rawPayload)) {
      plainSeedResult.value = data.result
      seedPayload.value = data.rawPayload
      seedRecordCount.value = data.rawPayload.length
      seedFileName.value = data.rawFileName ?? ''
      return
    }
    if (data && typeof data.inserted === 'number' && Array.isArray(data.rejected)) {
      sessionStorage.removeItem(REJECTED_SESSION_KEY)
    }
  } catch {
    sessionStorage.removeItem(REJECTED_SESSION_KEY)
  }
}

function restoreAiFromSession() {
  const savedAi = sessionStorage.getItem(SESSION_KEY)
  if (!savedAi) return
  try {
    const { result, acceptedIndices, rawPayload, rawFileName } = JSON.parse(savedAi)
    previewResult.value = result
    accepted.clear()
    acceptedIndices.forEach((i) => accepted.add(i))
    if (rawPayload?.length) {
      seedPayload.value = rawPayload
      seedRecordCount.value = rawPayload.length
      seedFileName.value = rawFileName ?? ''
      aiMode.value = true
    }
  } catch {
    sessionStorage.removeItem(SESSION_KEY)
  }
}

/**
 * Rehydrate from sessionStorage only when in-memory import state is empty
 * (first mount or full page reload), so navigation away from /admin does not reset
 * in-flight preview/import or a picked file.
 */
function restoreFromSessionIfMemoryEmpty() {
  if (seedStep.value === 'previewing' || seedStep.value === 'importing') return
  if (previewResult.value != null) return
  if (plainSeedResult.value != null) return
  if (seedRecordCount.value > 0) return

  restoreAiFromSession()
  restorePlainFromSession()
}

export function useSeedImporter() {
  const router = useRouter()

  restoreFromSessionIfMemoryEmpty()

  function onAiModeChange() {
    seedError.value = ''
  }

  function resetPlainImportResult() {
    plainSeedResult.value = null
    showRejectedOverlay.value = false
    sessionStorage.removeItem(REJECTED_SESSION_KEY)
  }

  function dismissPlainImportBanner() {
    resetPlainImportResult()
  }

  function clearFile() {
    seedPayload.value = []
    seedRecordCount.value = 0
    seedFileName.value = ''
    seedError.value = ''
    showRawModal.value = false
    if (fileInputRef.value) fileInputRef.value.value = ''
  }

  function clearPickedFile() {
    clearFile()
    resetPlainImportResult()
  }

  async function handleFileChange(event) {
    const file = event.target.files?.[0]
    clearFile()
    resetPlainImportResult()
    if (!file) return
    try {
      const parsed = JSON.parse(await file.text())
      if (!Array.isArray(parsed)) throw new Error('File must contain a JSON array.')
      seedPayload.value = parsed
      seedRecordCount.value = parsed.length
      seedFileName.value = file.name
    } catch (err) {
      seedError.value = err.message || 'Failed to parse JSON file.'
    }
  }

  async function handlePreview() {
    if (!seedRecordCount.value) {
      seedError.value = 'Upload a file first.'
      return
    }
    seedError.value = ''
    seedStep.value = 'previewing'
    try {
      const result = await aiSeedPreview(seedPayload.value)
      previewResult.value = result
      accepted.clear()
      result.records.forEach((r) => accepted.add(r.index))
      saveSession()
      showReviewOverlay.value = true
    } catch (err) {
      showErrorNotification(err.message || 'AI preview failed.')
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

  function toggleAccept(index) {
    accepted.has(index) ? accepted.delete(index) : accepted.add(index)
    saveSession()
  }
  function selectAll() {
    previewResult.value?.records.forEach((r) => accepted.add(r.index))
    saveSession()
  }
  function deselectAll() {
    accepted.clear()
    saveSession()
  }

  async function handleConfirmImport() {
    if (!accepted.size) return
    seedError.value = ''
    seedStep.value = 'importing'
    const toInsert = previewResult.value.records
      .filter((r) => accepted.has(r.index))
      .map((r) => (r.proposed_id != null ? { ...r.proposed, id: r.proposed_id } : { ...r.proposed }))
    try {
      const result = await plainSeed(toInsert)
      const corrected = previewResult.value.records.filter(
        (r) => accepted.has(r.index) && r.changes.length > 0
      ).length
      showImportToast(
        corrected > 0
          ? `Inserted ${result.inserted} record(s). AI corrected ${corrected} of them.`
          : `Inserted ${result.inserted} record(s). All records were already clean.`
      )
      showReviewOverlay.value = false
      resetPlainImportResult()
      resetProposals()
      clearFile()
    } catch (err) {
      showErrorNotification(err.message || 'Import failed.')
    } finally {
      seedStep.value = 'idle'
    }
  }

  async function handlePlainImport() {
    if (!seedRecordCount.value) {
      seedError.value = 'Upload a file first.'
      return
    }
    seedError.value = ''
    seedStep.value = 'importing'
    try {
      const result = await plainSeed(seedPayload.value)
      resetProposals()
      if (!result.rejected.length) {
        resetPlainImportResult()
        clearFile()
        if (result.inserted > 0) {
          showImportToast(`Inserted ${result.inserted} record(s) successfully.`)
        }
      } else {
        sessionStorage.removeItem(SESSION_KEY)
        plainSeedResult.value = result
        sessionStorage.setItem(
          REJECTED_SESSION_KEY,
          JSON.stringify({
            result,
            rawPayload: seedPayload.value,
            rawFileName: seedFileName.value,
          })
        )
        if (result.inserted > 0) {
          showImportToast(
            `Inserted ${result.inserted} record(s). ${result.rejected.length} skipped during import.`
          )
        }
      }
    } catch (err) {
      showErrorNotification(err.message || 'Import failed.')
    } finally {
      seedStep.value = 'idle'
    }
  }

  const FIELD_LABELS = {
    id: 'ID',
    name: 'Name',
    brand: 'Brand',
    purchase_date: 'Date',
    status: 'Status',
    notes: 'Notes',
  }
  function fieldLabel(f) {
    return FIELD_LABELS[f] ?? f
  }

  function statusClass(status) {
    return { Available: 'badge-available', 'In Use': 'badge-in-use', Repair: 'badge-repair' }[status] ?? ''
  }

  function recordLabel(record) {
    if (!record || typeof record !== 'object') return ''
    return record.name ?? record.id ?? ''
  }

  function formatRejectionReason(reason) {
    if (!reason) return ''
    const lines = reason.split('\n').map((l) => l.trim()).filter(Boolean)
    if (lines.length >= 3 && lines[0].includes('validation error')) {
      const field = lines[1]
      const msg = lines[2].replace(/\s*\[.*\]$/, '').trim()
      return `${field}: ${msg}`
    }
    if (lines.length > 1) return lines.join('\n')
    return lines[0] ?? ''
  }

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

  function showErrorNotification(message) {
    errorToastMessage.value = message
    showErrorToast.value = true
    clearTimeout(errorToastTimer)
    errorToastTimer = setTimeout(dismissErrorToast, 10_000)
  }
  function dismissErrorToast() {
    showErrorToast.value = false
    clearTimeout(errorToastTimer)
  }

  return {
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
  }
}
