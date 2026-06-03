<script setup>
import { ref, onMounted, inject } from 'vue'
import { api } from '../api.js'
import { t } from '../i18n.js'

defineProps({ authorized: Boolean })
const notify = inject('notify')
const refreshAuth = inject('refreshAuth')

const form = ref({
  client_id: '',
  client_secret: '',
  user: '',
  user_agent: 'shikimori-manager',
  redirect_uri: 'urn:ietf:wg:oauth:2.0:oob',
  base_url: 'https://shikimori.one',
  request_delay: 0.3,
})
const hasSecret = ref(false)
const authLink = ref('')
const code = ref('')
const busy = ref(false)

onMounted(async () => {
  try {
    const cfg = await api.getConfig()
    Object.assign(form.value, cfg)
    form.value.client_secret = '' // never round-trip the secret
    hasSecret.value = cfg.has_secret
  } catch (e) {
    notify(e.message, 'err')
  }
})

async function save() {
  busy.value = true
  try {
    const body = { ...form.value }
    if (!body.client_secret) delete body.client_secret // keep existing
    await api.saveConfig(body)
    hasSecret.value = hasSecret.value || !!form.value.client_secret
    notify(t('settings.saved'))
    refreshAuth()
  } catch (e) {
    notify(e.message, 'err')
  } finally {
    busy.value = false
  }
}

async function getLink() {
  try {
    const r = await api.authUrl()
    authLink.value = r.url
    window.open(r.url, '_blank')
  } catch (e) {
    notify(e.message, 'err')
  }
}

async function submitCode() {
  if (!code.value.trim()) return
  busy.value = true
  try {
    await api.submitCode(code.value.trim())
    code.value = ''
    notify(t('settings.authorized'))
    refreshAuth()
  } catch (e) {
    notify(e.message, 'err')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="card">
    <h2>{{ t('settings.credsTitle') }}</h2>
    <p class="muted">
      {{ t('settings.credsHelp.pre') }}
      <a href="https://shikimori.one/oauth/applications" target="_blank">shikimori.one/oauth/applications</a>
      {{ t('settings.credsHelp.post') }}
    </p>
    <label>{{ t('settings.clientId') }}</label>
    <input v-model="form.client_id" :placeholder="t('settings.clientId')" />
    <label>{{ t('settings.clientSecret') }} <span v-if="hasSecret" class="muted">{{ t('settings.secretSaved') }}</span></label>
    <input v-model="form.client_secret" type="password" :placeholder="t('settings.clientSecret')" />
    <div class="row">
      <div>
        <label>{{ t('settings.user') }}</label>
        <input v-model="form.user" :placeholder="t('settings.optional')" />
      </div>
      <div>
        <label>{{ t('settings.userAgent') }}</label>
        <input v-model="form.user_agent" />
      </div>
    </div>
    <div class="row">
      <div>
        <label>{{ t('settings.baseUrl') }}</label>
        <input v-model="form.base_url" />
      </div>
      <div>
        <label>{{ t('settings.requestDelay') }}</label>
        <input v-model.number="form.request_delay" type="number" step="0.1" min="0" />
      </div>
    </div>
    <div class="btn-row">
      <button class="primary" :disabled="busy" @click="save">{{ t('settings.save') }}</button>
    </div>
  </div>

  <div class="card">
    <h2>{{ t('settings.authTitle') }}</h2>
    <p class="muted" v-if="authorized">{{ t('settings.authOk') }}</p>
    <p class="muted" v-else>{{ t('settings.authHelp') }}</p>
    <div class="btn-row">
      <button @click="getLink">{{ t('settings.openAuth') }}</button>
    </div>
    <div v-if="authLink" class="muted" style="margin-top:8px; word-break:break-all;">
      {{ t('settings.ifNotOpen') }} <a :href="authLink" target="_blank">{{ authLink }}</a>
    </div>
    <label style="margin-top:14px;">{{ t('settings.code') }}</label>
    <input v-model="code" :placeholder="t('settings.codePlaceholder')" @keyup.enter="submitCode" />
    <div class="btn-row">
      <button class="primary" :disabled="busy || !code" @click="submitCode">{{ t('settings.submitCode') }}</button>
    </div>
  </div>
</template>
