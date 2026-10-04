<template>
  <div class="wall">
    <h1 class="serif">我的认领</h1>
    <input v-model="name" @change="load" placeholder="认领人名" />
    <article v-for="w in rows" :key="w.id" class="card">
      <h3>{{ w.title }}</h3>
      <WishTag :wish="w" />
      <p class="tag" v-if="w.status !== 'sourcing_paused'">到期 {{ w.expires_at }}</p>
    </article>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import WishTag from '../components/WishTag.vue'
import { loadClaimer, saveClaimer } from '../utils/wish'
const name = ref(loadClaimer() || '访客')
const rows = ref([])
async function load() {
  saveClaimer(name.value)
  rows.value = await api('/mine?claimer=' + encodeURIComponent(name.value))
}
onMounted(load)
</script>
