import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { formatRemaining } from '../utils/wish'

// Server-authoritative countdown: it seeds from the projected
// remaining_seconds and ticks locally only while the wish is live.
// Paused wishes never tick (the frozen value stays pinned).
export function useCountdown(wish) {
  const get = () => (typeof wish === 'function' ? wish() : wish)
  const remaining = ref(get()?.remaining_seconds ?? null)

  watch(
    () => [get()?.remaining_seconds, get()?.is_paused],
    () => { remaining.value = get()?.remaining_seconds ?? null },
  )

  let timer = null
  onMounted(() => {
    timer = setInterval(() => {
      const w = get()
      if (!w || w.is_paused || remaining.value == null) return
      if (remaining.value > 0) remaining.value -= 1
    }, 1000)
  })
  onUnmounted(() => clearInterval(timer))

  return { remaining, text: computed(() => formatRemaining(remaining.value)) }
}
