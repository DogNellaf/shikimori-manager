// Tiny fetch wrapper around the backend API.
async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  let data = null
  try {
    data = await res.json()
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const detail = (data && data.detail) || res.statusText
    throw new Error(detail)
  }
  return data
}

export const api = {
  getConfig: () => request('/config'),
  saveConfig: (body) => request('/config', { method: 'POST', body: JSON.stringify(body) }),
  authUrl: () => request('/auth/url'),
  authStatus: () => request('/auth/status'),
  submitCode: (code) => request('/auth/code', { method: 'POST', body: JSON.stringify({ code }) }),
  me: () => request('/me'),
  lists: (media = 'anime') => request(`/lists?media=${media}`),
  stats: (media = 'anime') => request(`/stats?media=${media}`),
  // Starts a background job, returns { job_id }.
  startRun: (rules, apply, sample = 50) =>
    request('/run', { method: 'POST', body: JSON.stringify({ rules, apply, sample }) }),
  // Polls job progress/result.
  runStatus: (jobId) => request(`/run/${jobId}`),
  exportUrl: (media = 'anime', status) =>
    `/api/export?media=${media}${status ? `&status=${status}` : ''}`,
}
