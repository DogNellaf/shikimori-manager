<script setup>
import { ref, onMounted, provide } from 'vue'
import { api } from './api.js'
import { locale, setLocale, t } from './i18n.js'
import Settings from './components/Settings.vue'
import Dashboard from './components/Dashboard.vue'
import RuleMover from './components/RuleMover.vue'

const tab = ref('settings')
const authorized = ref(false)
const me = ref(null)
const toast = ref(null)

function notify(message, kind = 'ok') {
  toast.value = { message, kind }
  setTimeout(() => (toast.value = null), 3500)
}
provide('notify', notify)

async function refreshAuth() {
  try {
    const s = await api.authStatus()
    authorized.value = s.authorized
    if (s.authorized) {
      try { me.value = await api.me() } catch { me.value = null }
      if (tab.value === 'settings') tab.value = 'dashboard'
    }
  } catch {
    authorized.value = false
  }
}
provide('refreshAuth', refreshAuth)

function toggleLocale() {
  setLocale(locale.value === 'en' ? 'ru' : 'en')
}

onMounted(refreshAuth)
</script>

<template>
  <div class="app">
    <div class="header">
      <div class="brand">
        Shikimori&nbsp;Manager
        <small v-if="me">· {{ me.nickname }} (#{{ me.id }})</small>
      </div>
      <div style="display:flex; gap:10px; align-items:center;">
        <button class="lang" @click="toggleLocale">{{ locale === 'en' ? 'RU' : 'EN' }}</button>
        <span class="pill" :class="authorized ? 'badge-ok' : 'badge-no'">
          {{ authorized ? t('status.authorized') : t('status.unauthorized') }}
        </span>
      </div>
    </div>

    <div class="tabs">
      <div class="tab" :class="{ active: tab === 'settings' }" @click="tab = 'settings'">{{ t('tab.settings') }}</div>
      <div class="tab" :class="{ active: tab === 'dashboard' }" @click="tab = 'dashboard'">{{ t('tab.dashboard') }}</div>
      <div class="tab" :class="{ active: tab === 'mover' }" @click="tab = 'mover'">{{ t('tab.mover') }}</div>
    </div>

    <Settings v-if="tab === 'settings'" :authorized="authorized" />
    <Dashboard v-else-if="tab === 'dashboard'" :authorized="authorized" />
    <RuleMover v-else-if="tab === 'mover'" :authorized="authorized" />

    <div v-if="toast" class="toast" :class="toast.kind === 'ok' ? 'ok' : 'err'">
      {{ toast.message }}
    </div>
  </div>
</template>
