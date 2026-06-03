<script setup>
import { ref, computed, inject } from 'vue'
import { api } from '../api.js'
import { t } from '../i18n.js'

defineProps({ authorized: Boolean })
const notify = inject('notify')

const MEDIA = ['anime', 'manga']
const STATUSES = ['planned', 'watching', 'rewatching', 'completed', 'on_hold', 'dropped']
// Canonical (media-neutral) condition keys sent to the API.
const COND_FIELDS = [
  'min_progress', 'max_progress',
  'min_score', 'max_score',
  'min_rating', 'max_rating',
]

function blankRule(media = 'anime', source = 'planned', target = 'watching') {
  return {
    name: '', media, source, target,
    min_progress: '', max_progress: '',
    min_score: '', max_score: '',
    min_rating: '', max_rating: '',
  }
}

const rules = ref([blankRule()])
const result = ref(null)
const busy = ref(false)
const progress = ref(null)

function addRule() { rules.value.push(blankRule()) }
function removeRule(i) { rules.value.splice(i, 1) }

// Progress label depends on media (episodes vs chapters).
function condLabel(key, media) {
  if (key === 'min_progress') return t(media === 'manga' ? 'cond.min_chapters' : 'cond.min_episodes')
  if (key === 'max_progress') return t(media === 'manga' ? 'cond.max_chapters' : 'cond.max_episodes')
  return t(`cond.${key}`)
}

function presetPlanned() {
  rules.value = [
    { ...blankRule('anime', 'planned', 'watching'), name: 'started → watching', min_progress: 1 },
    { ...blankRule('anime', 'planned', 'on_hold'), name: 'rated >8 → on_hold', max_progress: 0, min_rating: 8.01 },
  ]
}
function presetDropped() {
  rules.value = [
    { ...blankRule('anime', 'dropped', 'on_hold'), name: 'unrated, great → on_hold', max_score: 0, max_progress: 0, min_rating: 8.01 },
    { ...blankRule('anime', 'dropped', 'planned'), name: 'unrated rest → planned', max_score: 0, max_progress: 0 },
  ]
}

function toPayload() {
  return rules.value.map((r) => {
    const out = { media: r.media, source: r.source, target: r.target }
    if (r.name) out.name = r.name
    for (const key of COND_FIELDS) {
      if (r[key] !== '' && r[key] !== null) out[key] = Number(r[key])
    }
    return out
  })
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const progressPct = computed(() => {
  const p = progress.value
  if (!p || !p.total) return 0
  return Math.min(100, Math.round((p.current / p.total) * 100))
})
const progressLabel = computed(() => t(`progress.${progress.value?.phase || 'starting'}`))
const indeterminate = computed(() => !progress.value?.total)

async function run(apply) {
  busy.value = true
  result.value = null
  progress.value = { phase: 'starting', current: 0, total: 0 }
  try {
    const { job_id } = await api.startRun(toPayload(), apply)
    while (true) {
      const job = await api.runStatus(job_id)
      progress.value = { phase: job.phase, current: job.current, total: job.total }
      if (job.state === 'error') throw new Error(job.error || 'Job failed')
      if (job.state === 'done') {
        result.value = job.result
        if (apply) notify(t('mover.movedToast', { applied: job.result.applied, total: job.result.total }))
        break
      }
      await sleep(500)
    }
  } catch (e) {
    notify(e.message, 'err')
  } finally {
    busy.value = false
    progress.value = null
  }
}
</script>

<template>
  <div class="card">
    <h2>{{ t('mover.title') }}</h2>
    <p class="muted">{{ t('mover.help') }}</p>
    <div class="btn-row">
      <button @click="presetPlanned">{{ t('mover.presetPlanned') }}</button>
      <button @click="presetDropped">{{ t('mover.presetDropped') }}</button>
    </div>

    <div v-for="(r, i) in rules" :key="i" class="rule">
      <div class="row">
        <div>
          <label>{{ t('mover.name') }}</label>
          <input v-model="r.name" :placeholder="t('mover.label')" />
        </div>
        <div>
          <label>{{ t('mover.media') }}</label>
          <select v-model="r.media"><option v-for="m in MEDIA" :key="m" :value="m">{{ t(`media.${m}`) }}</option></select>
        </div>
        <div>
          <label>{{ t('mover.source') }}</label>
          <select v-model="r.source"><option v-for="s in STATUSES" :key="s">{{ s }}</option></select>
        </div>
        <div>
          <label>{{ t('mover.target') }}</label>
          <select v-model="r.target"><option v-for="s in STATUSES" :key="s">{{ s }}</option></select>
        </div>
      </div>
      <div class="row" style="margin-top:8px;">
        <div v-for="key in COND_FIELDS" :key="key">
          <label>{{ condLabel(key, r.media) }}</label>
          <input v-model="r[key]" type="number" step="0.01" placeholder="—" />
        </div>
      </div>
      <div class="btn-row">
        <button class="danger" @click="removeRule(i)" :disabled="rules.length === 1">{{ t('mover.remove') }}</button>
      </div>
    </div>

    <div class="btn-row">
      <button @click="addRule">{{ t('mover.addRule') }}</button>
    </div>

    <div class="btn-row" style="margin-top:16px;">
      <button class="primary" :disabled="!authorized || busy" @click="run(false)">
        {{ busy ? t('mover.working') : t('mover.preview') }}
      </button>
      <button class="danger" :disabled="!authorized || busy || !result || !result.total" @click="run(true)">
        {{ t('mover.apply') }} {{ result && result.total ? `(${result.total})` : '' }}
      </button>
    </div>

    <div v-if="progress" class="progress-wrap">
      <div class="progress-label">
        <span>{{ progressLabel }}</span>
        <span v-if="!indeterminate">{{ progress.current }} / {{ progress.total }} ({{ progressPct }}%)</span>
      </div>
      <div class="progress-track">
        <div class="progress-bar" :class="{ indeterminate }" :style="!indeterminate ? { width: progressPct + '%' } : {}"></div>
      </div>
    </div>

    <p class="muted" style="margin-top:6px;">{{ t('mover.tip') }}</p>
  </div>

  <div v-if="result" class="card">
    <h2>{{ t('mover.planTitle') }}</h2>
    <p v-if="!result.total" class="muted">{{ t('mover.nothing') }}</p>
    <template v-else>
      <table>
        <thead><tr><th>{{ t('mover.col.media') }}</th><th>{{ t('mover.source') }}</th><th>{{ t('mover.target') }}</th><th class="num">{{ t('mover.col.count') }}</th></tr></thead>
        <tbody>
          <tr v-for="(s, i) in result.summary" :key="i">
            <td><span class="pill">{{ t(`media.${s.media}`) }}</span></td>
            <td><span class="pill">{{ s.source }}</span></td>
            <td><span class="pill">{{ s.target }}</span></td>
            <td class="num">{{ s.count }}</td>
          </tr>
          <tr><td colspan="3"><b>{{ t('mover.total') }}</b></td><td class="num"><b>{{ result.total }}</b></td></tr>
        </tbody>
      </table>

      <h3 style="margin:16px 0 6px;">{{ t('mover.sample') }}</h3>
      <table>
        <thead><tr><th>{{ t('mover.col.media') }}</th><th>{{ t('mover.col.title') }}</th><th>→</th><th class="num">{{ t('mover.col.progress') }}</th><th class="num">{{ t('mover.col.rating') }}</th></tr></thead>
        <tbody>
          <tr v-for="(m, i) in result.moves" :key="i">
            <td>{{ t(`media.${m.media}`) }}</td>
            <td>{{ m.title }}</td>
            <td>{{ m.source }} → {{ m.target }}</td>
            <td class="num">{{ m.progress }}</td>
            <td class="num">{{ m.rating ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="result.truncated" class="muted">{{ t('mover.andMore', { n: result.moves.length }) }}</p>
      <p v-if="result.applied" class="badge-ok">{{ t('mover.appliedN', { n: result.applied }) }}</p>
      <div v-if="result.errors && result.errors.length" class="muted">
        <p class="badge-no">{{ t('mover.errorsN', { n: result.errors.length }) }}</p>
        <div v-for="(e, i) in result.errors.slice(0, 10)" :key="i">{{ e }}</div>
      </div>
    </template>
  </div>
</template>
