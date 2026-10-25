import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { LogOut, ShieldCheck, Moon, Sun, Award, Sparkles, User as UserIcon } from 'lucide-react'
import { api } from '../api'
import { useDarkMode } from '../hooks/useDarkMode'

export default function Me({ user, onLogout }) {
  const [me, setMe] = useState(user)
  const [dark, toggleDark] = useDarkMode()

  useEffect(() => {
    api('/api/me').then((r) => setMe(r.user)).catch(() => {})
  }, [])

  const score = me.trust_score ?? 100
  const tier =
    score >= 90
      ? { title: 'Campus Sentinel', color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-500' }
      : score >= 75
      ? { title: 'Verified Scout', color: 'text-teal-600 dark:text-teal-400', bg: 'bg-teal-500' }
      : { title: 'Standard Reporter', color: 'text-slate-600 dark:text-slate-400', bg: 'bg-slate-500' }

  const initials = (me.name || 'Student')
    .split(' ')
    .map((n) => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <div className="mx-auto max-w-md space-y-4 p-4 lg:p-8">
      {/* Profile Header Card */}
      <div className="card space-y-5">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 to-emerald-600 text-lg font-bold text-white shadow-md shadow-teal-500/25">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h2 className="truncate text-lg font-bold text-slate-900 dark:text-white">{me.name}</h2>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                {me.role}
              </span>
            </div>
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">{me.email}</p>
            {me.cusat_id && (
              <p className="font-mono text-xs text-slate-400 dark:text-slate-500">ID: {me.cusat_id}</p>
            )}
          </div>
        </div>

        {/* Trust Score & Rank Meter */}
        <div className="rounded-2xl border border-slate-200/80 bg-slate-50/70 p-4 dark:border-slate-800/80 dark:bg-slate-900/60">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              <ShieldCheck size={14} className="text-accent" /> Integrity Rating
            </span>
            <span className={`flex items-center gap-1 text-xs font-bold ${tier.color}`}>
              <Award size={13} /> {tier.title}
            </span>
          </div>

          <div className="mt-2.5 flex items-baseline justify-between">
            <span className="font-mono text-2xl font-black text-slate-900 dark:text-white">
              {score}<span className="text-sm font-normal text-slate-400">/100</span>
            </span>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              {score >= 90 ? 'High trust · Instant ledger triage' : 'Reports subject to peer audit'}
            </span>
          </div>

          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
            <div
              className={`h-full rounded-full transition-all duration-700 ${tier.bg}`}
              style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
            />
          </div>
        </div>

        {/* Quick App Preferences */}
        <div className="flex items-center justify-between rounded-xl border border-slate-200/60 p-3 dark:border-slate-800/60">
          <span className="flex items-center gap-2 text-xs font-semibold text-slate-700 dark:text-slate-300">
            {dark ? <Moon size={15} className="text-indigo-400" /> : <Sun size={15} className="text-amber-500" />}
            Interface Theme
          </span>
          <button
            onClick={toggleDark}
            className="btn-ghost !min-h-[30px] rounded-lg px-2.5 text-xs"
          >
            Switch to {dark ? 'Light' : 'Dark'}
          </button>
        </div>
      </div>

      {me.role !== 'student' && (
        <Link to="/admin" className="btn-primary w-full">
          Open Staff Dashboard
        </Link>
      )}

      <button onClick={onLogout} className="btn-ghost w-full">
        <LogOut size={16} /> Sign out
      </button>
    </div>
  )
}

