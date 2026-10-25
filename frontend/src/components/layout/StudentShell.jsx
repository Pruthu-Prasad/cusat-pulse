import { NavLink, Outlet } from 'react-router-dom'
import { Activity, ClipboardList, Map, User, LayoutDashboard, Sun, Moon } from 'lucide-react'
import { useDarkMode } from '../../hooks/useDarkMode'

const NAV = [
  { to: '/map', label: 'Map', Icon: Map },
  { to: '/reports', label: 'My Reports', Icon: ClipboardList },
  { to: '/me', label: 'Me', Icon: User },
]

export default function StudentShell({ user }) {
  const [dark, toggleDark] = useDarkMode()
  const staff = user.role !== 'student'

  const desktopLink = ({ isActive }) =>
    `relative flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold transition-all duration-150 ${
      isActive
        ? 'text-teal-700 bg-teal-500/10 shadow-sm shadow-teal-500/10 dark:text-teal-300 dark:bg-teal-500/15'
        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800/60'
    }`

  const mobileLink = ({ isActive }) =>
    `relative flex flex-1 flex-col items-center justify-center gap-1 py-2.5 text-[11px] font-semibold transition-all duration-150 ${
      isActive
        ? 'text-teal-600 dark:text-teal-400'
        : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
    }`

  return (
    <div className="flex h-full flex-col" data-dark={dark}>
      <header className="glass-header safe-top z-20 hidden items-center justify-between px-6 py-3 lg:flex">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-teal-500 to-emerald-600 text-white shadow-md shadow-teal-600/25">
            <Activity size={20} className="animate-pulse" />
          </div>
          <div>
            <span className="font-bold tracking-tight text-slate-900 dark:text-white">CUSAT-Pulse</span>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
              <span>Campus Live</span>
            </div>
          </div>
        </div>

        <nav className="flex items-center gap-1.5">
          {NAV.map(({ to, label, Icon }) => (
            <NavLink key={to} to={to} className={desktopLink}>
              <Icon size={17} /> {label}
            </NavLink>
          ))}
          {staff && (
            <NavLink to="/admin" className={desktopLink}>
              <LayoutDashboard size={17} /> Dashboard
            </NavLink>
          )}

          <div className="ml-3 h-5 w-px bg-slate-200 dark:bg-slate-800" />

          <button
            onClick={toggleDark}
            className="btn-ghost !min-h-[36px] ml-1 rounded-xl p-2 text-slate-600 dark:text-slate-300"
            aria-label="Toggle dark mode"
          >
            {dark ? <Sun size={17} className="text-amber-400" /> : <Moon size={17} />}
          </button>
        </nav>
      </header>

      <main className="relative min-h-0 flex-1 overflow-y-auto">
        <Outlet context={{ dark }} />
      </main>

      <nav className="glass-nav safe-bottom z-20 flex shadow-lg lg:hidden">
        {NAV.map(({ to, label, Icon }) => (
          <NavLink key={to} to={to} className={mobileLink}>
            {({ isActive }) => (
              <>
                <div className={`relative flex items-center justify-center rounded-full px-3 py-1 transition-all ${
                  isActive ? 'bg-teal-500/15 dark:bg-teal-500/20' : ''
                }`}>
                  <Icon size={20} className={isActive ? 'stroke-[2.4]' : 'stroke-[1.8]'} />
                </div>
                <span>{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

