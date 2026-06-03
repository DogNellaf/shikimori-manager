// Minimal dependency-free i18n: a reactive locale + t() lookup.
import { ref } from 'vue'

const messages = {
  en: {
    'tab.settings': 'Settings & Auth',
    'tab.dashboard': 'Dashboard',
    'tab.mover': 'Rule mover',
    'status.authorized': 'authorized',
    'status.unauthorized': 'not authorized',

    // Settings
    'settings.credsTitle': '1. Credentials (.env)',
    'settings.credsHelp.pre': 'Create an app at',
    'settings.credsHelp.post':
      'with redirect URI urn:ietf:wg:oauth:2.0:oob and scope user_rates.',
    'settings.clientId': 'Client ID',
    'settings.clientSecret': 'Client Secret',
    'settings.secretSaved': '(saved — leave blank to keep)',
    'settings.user': 'User (id or nickname, blank = token owner)',
    'settings.optional': '(optional)',
    'settings.userAgent': 'User-Agent (required by API)',
    'settings.baseUrl': 'Base URL',
    'settings.requestDelay': 'Request delay (s)',
    'settings.save': 'Save settings',
    'settings.saved': 'Settings saved',
    'settings.authTitle': '2. Authorize',
    'settings.authOk': '✓ A valid token is stored and refreshed automatically.',
    'settings.authHelp':
      'Get the authorization link, approve access, then paste the one-time code below. The code expires in ~2 minutes.',
    'settings.openAuth': 'Open authorization page',
    'settings.ifNotOpen': "If it didn't open:",
    'settings.code': 'Authorization code',
    'settings.codePlaceholder': 'Paste code here',
    'settings.submitCode': 'Submit code',
    'settings.authorized': 'Authorized!',

    // Dashboard
    'dash.title': 'Your lists',
    'dash.authFirst': 'Authorize first on the Settings tab.',
    'dash.load': 'Load statistics',
    'dash.loading': 'Loading…',
    'dash.export': 'Export all to JSON',
    'dash.col.list': 'List',
    'dash.col.count': 'Count',
    'dash.col.progress.anime': 'Episodes watched',
    'dash.col.progress.manga': 'Chapters read',
    'dash.col.rated': 'Rated',
    'dash.col.avg': 'Avg score',
    'dash.userId': 'user id =',
    'media.anime': 'Anime',
    'media.manga': 'Manga',

    // Rule mover
    'mover.title': 'Move rules',
    'mover.help':
      'Entries are moved from source to target when the conditions hold. Rules are checked top-to-bottom per source list; the first match wins. All conditions are optional and inclusive.',
    'mover.presetPlanned': 'Preset: tidy “Planned”',
    'mover.presetDropped': 'Preset: clean “Dropped”',
    'mover.name': 'Name (optional)',
    'mover.label': 'label',
    'mover.media': 'Media',
    'mover.source': 'Source',
    'mover.target': 'Target',
    'cond.min_episodes': 'min ep',
    'cond.max_episodes': 'max ep',
    'cond.min_chapters': 'min ch',
    'cond.max_chapters': 'max ch',
    'cond.min_score': 'min score',
    'cond.max_score': 'max score',
    'cond.min_rating': 'min rating',
    'cond.max_rating': 'max rating',
    'mover.remove': 'Remove',
    'mover.addRule': '+ Add rule',
    'mover.preview': 'Preview (dry run)',
    'mover.working': 'Working…',
    'mover.apply': 'Apply',
    'mover.tip': 'Tip: community scores are floats — use 8.01 for “strictly > 8”. Big lists can take ~20–30 s to scan.',
    'mover.planTitle': 'Plan',
    'mover.nothing': 'Nothing matches the current rules.',
    'mover.col.count': 'Count',
    'mover.total': 'total',
    'mover.sample': 'Sample',
    'mover.col.media': 'Media',
    'mover.col.title': 'Title',
    'mover.col.progress': 'Progress',
    'mover.col.rating': 'Rating',
    'mover.andMore': '…and more (showing first {n}).',
    'mover.appliedN': 'Applied {n} moves.',
    'mover.errorsN': '{n} errors:',
    'mover.movedToast': 'Moved {applied}/{total} entries',

    // Progress
    'progress.starting': 'Starting…',
    'progress.fetching': 'Fetching lists…',
    'progress.scanning': 'Scanning (community scores)…',
    'progress.titling': 'Resolving titles…',
    'progress.applying': 'Applying…',
    'progress.done': 'Done',
  },

  ru: {
    'tab.settings': 'Настройки и вход',
    'tab.dashboard': 'Обзор',
    'tab.mover': 'Перенос по правилам',
    'status.authorized': 'авторизован',
    'status.unauthorized': 'не авторизован',

    // Settings
    'settings.credsTitle': '1. Учётные данные (.env)',
    'settings.credsHelp.pre': 'Создайте приложение на',
    'settings.credsHelp.post':
      'с redirect URI urn:ietf:wg:oauth:2.0:oob и доступом user_rates.',
    'settings.clientId': 'Client ID',
    'settings.clientSecret': 'Client Secret',
    'settings.secretSaved': '(сохранён — оставьте пустым, чтобы не менять)',
    'settings.user': 'Пользователь (id или ник, пусто = владелец токена)',
    'settings.optional': '(необязательно)',
    'settings.userAgent': 'User-Agent (обязателен для API)',
    'settings.baseUrl': 'Базовый URL',
    'settings.requestDelay': 'Задержка между запросами (с)',
    'settings.save': 'Сохранить настройки',
    'settings.saved': 'Настройки сохранены',
    'settings.authTitle': '2. Авторизация',
    'settings.authOk': '✓ Токен сохранён и обновляется автоматически.',
    'settings.authHelp':
      'Получите ссылку авторизации, подтвердите доступ и вставьте одноразовый код ниже. Код живёт ~2 минуты.',
    'settings.openAuth': 'Открыть страницу авторизации',
    'settings.ifNotOpen': 'Если не открылось:',
    'settings.code': 'Код авторизации',
    'settings.codePlaceholder': 'Вставьте код сюда',
    'settings.submitCode': 'Отправить код',
    'settings.authorized': 'Авторизовано!',

    // Dashboard
    'dash.title': 'Ваши списки',
    'dash.authFirst': 'Сначала авторизуйтесь на вкладке «Настройки».',
    'dash.load': 'Загрузить статистику',
    'dash.loading': 'Загрузка…',
    'dash.export': 'Экспорт всего в JSON',
    'dash.col.list': 'Список',
    'dash.col.count': 'Кол-во',
    'dash.col.progress.anime': 'Просмотрено серий',
    'dash.col.progress.manga': 'Прочитано глав',
    'dash.col.rated': 'С оценкой',
    'dash.col.avg': 'Сред. балл',
    'dash.userId': 'id пользователя =',
    'media.anime': 'Аниме',
    'media.manga': 'Манга',

    // Rule mover
    'mover.title': 'Правила переноса',
    'mover.help':
      'Записи переносятся из «откуда» в «куда», когда выполняются условия. Правила проверяются сверху вниз по каждому списку-источнику; срабатывает первое подходящее. Все условия необязательны и включительны.',
    'mover.presetPlanned': 'Пресет: прибрать «Запланировано»',
    'mover.presetDropped': 'Пресет: почистить «Брошено»',
    'mover.name': 'Название (необязательно)',
    'mover.label': 'метка',
    'mover.media': 'Тип',
    'mover.source': 'Откуда',
    'mover.target': 'Куда',
    'cond.min_episodes': 'мин. серий',
    'cond.max_episodes': 'макс. серий',
    'cond.min_chapters': 'мин. глав',
    'cond.max_chapters': 'макс. глав',
    'cond.min_score': 'мин. оценка',
    'cond.max_score': 'макс. оценка',
    'cond.min_rating': 'мин. балл',
    'cond.max_rating': 'макс. балл',
    'mover.remove': 'Удалить',
    'mover.addRule': '+ Добавить правило',
    'mover.preview': 'Предпросмотр (без изменений)',
    'mover.working': 'Выполняется…',
    'mover.apply': 'Применить',
    'mover.tip': 'Подсказка: баллы аниме дробные — для «строго > 8» используйте 8.01. Большие списки сканируются ~20–30 с.',
    'mover.planTitle': 'План',
    'mover.nothing': 'Под текущие правила ничего не подходит.',
    'mover.col.count': 'Кол-во',
    'mover.total': 'итого',
    'mover.sample': 'Примеры',
    'mover.col.media': 'Тип',
    'mover.col.title': 'Название',
    'mover.col.progress': 'Прогресс',
    'mover.col.rating': 'Балл',
    'mover.andMore': '…и ещё (показаны первые {n}).',
    'mover.appliedN': 'Применено переносов: {n}.',
    'mover.errorsN': 'Ошибок: {n}:',
    'mover.movedToast': 'Перенесено {applied}/{total} записей',

    // Progress
    'progress.starting': 'Запуск…',
    'progress.fetching': 'Загрузка списков…',
    'progress.scanning': 'Сканирование (баллы)…',
    'progress.titling': 'Получение названий…',
    'progress.applying': 'Применение…',
    'progress.done': 'Готово',
  },
}

const locale = ref(localStorage.getItem('locale') || 'en')

function setLocale(l) {
  locale.value = l
  localStorage.setItem('locale', l)
}

// t('key', { n: 5 }) -> string, with {placeholder} interpolation.
function t(key, params) {
  const table = messages[locale.value] || messages.en
  let str = table[key] ?? messages.en[key] ?? key
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      str = str.replace(`{${k}}`, v)
    }
  }
  return str
}

export { locale, setLocale, t }
