<template>
  <span class="tag">
    {{ statusLabel(wish.status) }}<template v-if="quality"> · {{ wish.data_quality }}</template>
    <template v-if="wish.remaining_seconds != null">
      · <span v-if="wish.is_paused" class="badge paused">已暂停</span>
      剩余 {{ text }}
    </template>
  </span>
</template>
<script setup>
import { useCountdown } from '../composables/useCountdown'
import { statusLabel } from '../utils/wish'

const props = defineProps({
  wish: { type: Object, required: true },
  quality: { type: Boolean, default: false },
})
const { text } = useCountdown(() => props.wish)
</script>
