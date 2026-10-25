import { useCallback, useEffect, useState } from 'react'
import { Laptop, LogOut, MonitorSmartphone, Smartphone } from 'lucide-react'
import { api, session } from '../api'
import { timeAgo } from './Bits'

const isPhone = (device) => /Android|iPhone|iPad/.test(device)

// Devices signed in to this account, with per-device and everywhere sign-out (sessions live on the server).
export default function SessionsCard() {
  const [list, setList] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => api('/api/auth/sessions').then((r) => setList(r.sessions)).catch((e) => setError(e.message)), [])
  useEffect(() => { load() }, [load])

  async function revoke(id) {
    try { await api(`/api/auth/sessions/${id}/revoke`, { method: 'POST' }); load() } catch (e) { setError(e.message) }
  }

  async function signOutEverywhere() {
    if (!window.confirm('Sign out of CUSAT-Pulse on every device, including this one?')) return
    try { await api('/api/auth/logout-all', { method: 'POST' }) } catch { /* signed out anyway below */ }
    session.clear()
    window.location.href = '/'
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
        <MonitorSmartphone size={14} className="text-accent" /> Signed-in devices
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {!list ? <div className="shimmer h-12 w-full" /> : (
        <ul className="space-y-2">
          {list.map((s) => (
            <li key={s.id} className="flex items-center gap-3 rounded-xl border border-slate-200/60 p-2.5 dark:border-slate-800/60">
              {isPhone(s.device) ? <Smartphone size={16} className="shrink-0 text-slate-400" /> : <Laptop size={16} className="shrink-0 text-slate-400" />}
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-semibold text-slate-800 dark:text-slate-200">
                  {s.device}
                  {s.current && <span className="ml-1.5 rounded-full bg-accent/15 px-1.5 py-0.5 text-[10px] font-bold text-accent">This device</span>}
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">Active {timeAgo(s.last_seen_at)} · signed in {timeAgo(s.created_at)}</p>
              </div>
              {!s.current && (
                <button className="btn-ghost !min-h-[30px] shrink-0 rounded-lg px-2.5 text-xs" onClick={() => revoke(s.id)}>Sign out</button>
              )}
            </li>
          ))}
        </ul>
      )}
      {list && list.length > 0 && (
        <button className="btn-ghost w-full text-xs text-red-700 dark:text-red-400" onClick={signOutEverywhere}>
          <LogOut size={14} /> Sign out of all devices
        </button>
      )}
    </div>
  )
}
