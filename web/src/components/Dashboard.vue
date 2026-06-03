<script setup>
import { ref, inject } from 'vue'
import { api } from '../api.js'
import { t } from '../i18n.js'

defineProps({ authorized: Boolean })
const notify = inject('notify')

const STATUSES = ['planned', 'watching', 'rewatching', 'completed', 'on_hold', 'dropped']
const media = ref('anime')
const stats = ref(null)
const userId = ref(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const r = await api.stats(media.value)
    stats.value = r.stats
    userId.value = r.user_id
  } catch (e) {
    notify(e.message, 'err')
  } finally {
    loading.value = false
  }
}

function setMedia(m) {
  media.value = m
  stats.value = null
}

function exportAll() {
  window.open(api.exportUrl(media.value), '_blank')
}
</script>

<template>
  <div class="card">
    <h2>{{ t('dash.title') }}</h2>
    <p class="muted" v-if="!authorized">{{ t('dash.authFirst') }}</p>

    <div class="tabs" style="margin-bottom:12px;">
      <div class="tab" :class="{ active: media === 'anime' }" @click="setMedia('anime')">{{ t('media.anime') }}</div>
      <div class="tab" :class="{ active: media === 'manga' }" @click="setMedia('manga')">{{ t('media.manga') }}</div>
    </div>

    <div class="btn-row">
      <button class="primary" :disabled="!authorized || loading" @click="load">
        {{ loading ? t('dash.loading') : t('dash.load') }}
      </button>
      <button :disabled="!authorized" @click="exportAll">{{ t('dash.export') }}</button>
    </div>

    <table v-if="stats" style="margin-top:14px;">
      <thead>
        <tr>
          <th>{{ t('dash.col.list') }}</th>
          <th class="num">{{ t('dash.col.count') }}</th>
          <th class="num">{{ t(`dash.col.progress.${media}`) }}</th>
          <th class="num">{{ t('dash.col.rated') }}</th>
          <th class="num">{{ t('dash.col.avg') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in STATUSES" :key="s">
          <td><span class="pill">{{ s }}</span></td>
          <td class="num">{{ stats[s].count }}</td>
          <td class="num">{{ stats[s].progress }}</td>
          <td class="num">{{ stats[s].rated }}</td>
          <td class="num">{{ stats[s].avg_score || '—' }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="userId" class="muted" style="margin-top:8px;">{{ t('dash.userId') }} {{ userId }}</p>
  </div>
</template>
