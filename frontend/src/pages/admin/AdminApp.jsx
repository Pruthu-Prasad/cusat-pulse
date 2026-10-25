import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { Activity, Flame, LayoutList, LogOut, Moon, QrCode, ScrollText, Sun, Wrench, Map as MapIcon } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { stream } from '../../api'
import { useDarkMode } from '../../hooks/useDarkMode'
import Issues from './Issues'
import Resolve from './Resolve'
import HeatMap from './HeatMap'
import Ledger from './Ledger'

export default function AdminApp({ user, onLogout }) {
  const [dark, toggleDark] = useDarkMode(true)
  const [version, setVersion] = useState(0)
  const [live, setLive] = useState(false)
  const [qr, setQr] = useState(false)

  useEffect(() => {
    const es = stream('/api/stream/dashboard', () => setVersion((v) => v + 1))
    es.onopen = () => setLive(true)
    es.onerror = () => setLive(false)
    return () => es.close()
  }, [])

  const tabs = [
    { to: '/admin/heatmap', label: 'Heat Map', Icon: Flame },
    { to: '/admin/issues', label: 'Issues', Icon: LayoutList },
    { to: '/admin/resolve', label: 'Resolve', Icon: Wrench },
    ...(user.role === 'admin' ? [{ to: '/admin/ledger', label: 'Ledger', Icon: ScrollText }] : []),
  ]
  const side = ({ isActive }) =>
    `flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-semibold transition-all duration-150 ${
      isActive
        ? 'bg-gradient-to-r from-teal-600 to-emerald-600 text-white shadow-sm shadow-teal-700/20'
        : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-slate-200'
    }`
  const bottom = ({ isActive }) =>
    `flex flex-1 flex-col items-center gap-0.5 py-2 text-xs font-semibold transition-all duration-150 ${
      isActive ? 'text-teal-600 dark:text-teal-400' : 'text-slate-500 dark:text-slate-400'
    }`
  const props = { version, dark, user }

  return (
    <div className="flex h-full">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-200/80 bg-white/80 p-3.5 backdrop-blur-xl dark:border-slate-800/80 dark:bg-slate-950/80 md:flex">
        <div className="mb-6 flex items-center gap-2.5 px-2 pt-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-teal-500 to-emerald-600 text-white shadow-md shadow-teal-600/25">
            <Activity size={20} className="animate-pulse" />
          </div>
          <div>
            <span className="font-bold tracking-tight text-slate-900 dark:text-white">CUSAT-Pulse</span>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-teal-600 dark:text-teal-400">Admin Console</p>
          </div>
        </div>

        <nav className="space-y-1.5">
          {tabs.map(({ to, label, Icon }) => (
            <NavLink key={to} to={to} className={side}>
              <Icon size={18} /> {label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto space-y-1.5 border-t border-slate-200/70 pt-3 dark:border-slate-800/70">
          <NavLink to="/map" className={side}>
            <MapIcon size={18} /> Student view
          </NavLink>
          <button
            onClick={onLogout}
            className="flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-semibold text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          >
            <LogOut size={18} /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass-header safe-top flex items-center gap-3 px-4 py-2.5">
          <div className="flex items-center gap-2 md:hidden">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-white">
              <Activity size={16} />
            </div>
            <span className="font-bold text-slate-900 dark:text-white">Pulse</span>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-slate-200/80 bg-slate-100/80 px-2.5 py-1 text-xs dark:border-slate-800 dark:bg-slate-800/80">
            <span className="relative flex h-2 w-2">
              {live && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />}
              <span className={`relative inline-flex h-2 w-2 rounded-full ${live ? 'bg-emerald-500' : 'bg-slate-400'}`} />
            </span>
            <span className="font-semibold text-slate-700 dark:text-slate-300">{live ? 'Live SSE' : 'Connecting'}</span>
          </div>

          <div className="ml-auto hidden items-center gap-2 sm:flex">
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-300">
              {user.name} · <span className="uppercase text-teal-600 dark:text-teal-400">{user.role}</span>
            </span>
          </div>

          <div className="relative">
            <button
              className="btn-ghost !min-h-[36px] rounded-xl px-2.5"
              onClick={() => setQr(!qr)}
              aria-label="Show QR code"
            >
              <QrCode size={18} />
            </button>
            {qr && (
              <>
                <div className="fixed inset-0 z-[1050] bg-black/40 backdrop-blur-sm" onClick={() => setQr(false)} />
                <div className="fixed left-1/2 top-1/2 z-[1100] -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900">
                  <div className="flex flex-col items-center gap-3">
                    <p className="text-sm font-bold text-slate-900 dark:text-white">Mobile Test Tunnel</p>
                    <div className="rounded-2xl border border-slate-100 bg-white p-3 shadow-inner">
                      <QRCodeSVG value={window.location.origin} size={190} />
                    </div>
                    <p className="max-w-[220px] break-all text-center font-mono text-[11px] text-slate-500 dark:text-slate-400">
                      {window.location.origin}
                    </p>
                    <button className="btn-primary w-full text-xs" onClick={() => setQr(false)}>Close</button>
                  </div>
                </div>
              </>
            )}
          </div>

          <button
            className="btn-ghost !min-h-[36px] rounded-xl px-2.5"
            onClick={toggleDark}
            aria-label="Toggle dark mode"
          >
            {dark ? <Sun size={18} className="text-amber-400" /> : <Moon size={18} />}
          </button>
        </header>

        <main className="min-h-0 flex-1 overflow-hidden">
          <Routes>
            <Route path="heatmap" element={<HeatMap {...props} />} />
            <Route path="issues" element={<Issues {...props} />} />
            <Route path="resolve" element={<Resolve {...props} />} />
            {user.role === 'admin' && <Route path="ledger" element={<Ledger {...props} />} />}
            <Route path="*" element={<Navigate to="/admin/issues" replace />} />
          </Routes>
        </main>

        <nav className="glass-nav safe-bottom flex shadow-lg md:hidden">
          {tabs.map(({ to, label, Icon }) => (
            <NavLink key={to} to={to} className={bottom}>
              <Icon size={20} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}
