<template>
  <div class="wall">
    <h1 class="serif">{{ w.title }}</h1>
    <p>{{ w.note }}</p>
    <WishTag :wish="w" />
    <span v-if="w.is_paused" class="badge paused" style="margin-left:8px">寻货已暂停 · 倒计时冻结</span>
    <p class="tag">认领人 {{ w.claimer || '—' }}</p>
    <p v-if="err" class="err">{{ err }}</p>
    <input v-model="claimer" placeholder="你的名字" />
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button :disabled="busy || !['open','released'].includes(w.status)" @click="claim">认领锁定</button>
      <button class="ghost" :disabled="busy || !isOwner || w.status !== 'claimed'" @click="pause">暂停寻货</button>
      <button class="ghost" :disabled="busy || !isOwner || w.status !== 'sourcing_paused'" @click="resume">恢复寻货</button>
      <button class="ghost" :disabled="busy || w.status !== 'claimed'" @click="fulfill">核销完成</button>
      <button class="ghost" :disabled="busy || !['claimed','sourcing_paused'].includes(w.status)" @click="release">释放</button>
    </div>
  </div>
</template>
<script setup>
import { computed, ref, onMounted } from 'vue'
import { api } from '../api'
import WishTag from '../components/WishTag.vue'
import { loadClaimer, saveClaimer } from '../utils/wish'
const props = defineProps({ id: String })
const w = ref({})
const claimer = ref(loadClaimer() || '访客')
const err = ref('')
const busy = ref(false)
const isOwner = computed(() => !!w.value.claimer && w.value.claimer === claimer.value)
async function load() { w.value = await api('/wishes/' + props.id) }
async function act(path, body) {
  err.value = ''; busy.value = true
  try {
    saveClaimer(claimer.value)
    await api('/wishes/' + props.id + path, { method: 'POST', body: JSON.stringify(body || {}) })
    await load()
  } catch (e) { err.value = e.message } finally { busy.value = false }
}
function claim() { act('/claim', { claimer: claimer.value }) }
function pause() { act('/pause', { claimer: claimer.value }) }
function resume() { act('/resume', { claimer: claimer.value }) }
function release() { act('/release') }
function fulfill() { act('/fulfill') }
onMounted(load)
</script>
