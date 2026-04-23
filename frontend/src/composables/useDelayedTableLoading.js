import { ref, watchEffect } from 'vue'

/** Spinner row appears only after `delayMs` if still fetching with an empty list (avoids flash on fast responses). */
export function useDelayedTableLoading(fetching, isEmpty, delayMs = 180) {
  const visible = ref(false)
  watchEffect((onCleanup) => {
    if (fetching.value && isEmpty.value) {
      visible.value = false
      const id = setTimeout(() => {
        if (fetching.value && isEmpty.value) visible.value = true
      }, delayMs)
      onCleanup(() => clearTimeout(id))
    } else {
      visible.value = false
    }
  })
  return visible
}
