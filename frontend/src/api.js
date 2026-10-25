const TOKEN_KEY = 'cp_token'
const USER_KEY = 'cp_user'

function read(key) {
  try { return localStorage.getItem(key) } catch { return null }
}

export const session = {
  get token() { return read(TOKEN_KEY) },
  get user() {
    try { return JSON.parse(read(USER_KEY) || 'null') } catch { return null }
  },
  save(token, user) {
    try { localStorage.setItem(TOKEN_KEY, token); localStorage.setItem(USER_KEY, JSON.stringify(user)) } catch { /* private mode */ }
  },
  clear() {
    try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY) } catch { /* ignore */ }
  },
}

export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  if (session.token) headers.Authorization = `Bearer ${session.token}`
  let payload
  if (form) payload = form
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  let res
  try {
    res = await fetch(path, { method: form || body !== undefined ? (method === 'GET' ? 'POST' : method) : method, headers, body: payload })
  } catch {
    throw new Error('Could not reach the server. Check your connection.')
  }
  const data = await res.json().catch(() => ({}))
  if (res.status === 401 && session.token) { session.clear(); window.location.href = '/' }
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Something went wrong. Please try again.')
  return data
}

export const photo = (name) => (name ? `/uploads/${name}?token=${encodeURIComponent(session.token || '')}` : null)

export function stream(path, onMessage) {
  const es = new EventSource(`${path}?token=${encodeURIComponent(session.token || '')}`)
  es.onmessage = (e) => { try { onMessage(JSON.parse(e.data)) } catch { /* ignore */ } }
  return es
}

export const CATEGORY_COLORS = {
  Electrical: '#ef4444', Plumbing: '#3b82f6', Structural: '#f59e0b', IT: '#a855f7',
  Sanitation: '#14b8a6', Safety: '#f97316', Other: '#6b7280', Resolved: '#10b981',
}

export const STATUS_LABEL = {
  OPEN: 'Open', FIX_SUBMITTED: 'Checking fix', AWAITING_STUDENT_CHECK: 'Awaiting check',
  REOPENED: 'Reopened', RESOLVED: 'Resolved', DISMISSED: 'Dismissed (invalid)',
}

export function ordinal(n) {
  const s = ['th', 'st', 'nd', 'rd'], v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}
