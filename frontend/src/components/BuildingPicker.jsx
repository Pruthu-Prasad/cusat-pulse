import { useMemo, useState } from 'react'
import { Search, X, Building2, MapPin } from 'lucide-react'
import { BUILDINGS, GROUPS } from '../buildings'

export default function BuildingPicker({ onPick, onClose }) {
  const [q, setQ] = useState('')
  const [activeGroup, setActiveGroup] = useState('All')

  const matches = useMemo(() => {
    let list = BUILDINGS
    if (activeGroup !== 'All') {
      list = list.filter((b) => b.group === activeGroup)
    }
    const s = q.trim().toLowerCase()
    return s ? list.filter((b) => `${b.name} ${b.full || ''} ${b.group}`.toLowerCase().includes(s)) : list
  }, [q, activeGroup])

  const tabs = ['All', ...GROUPS]

  return (
    <div className="fixed inset-0 z-[1000] flex items-end justify-center bg-black/50 backdrop-blur-sm lg:items-center p-0 lg:p-4" onClick={onClose}>
      <div
        className="safe-bottom flex max-h-[85vh] w-full flex-col rounded-t-3xl border border-slate-200/80 bg-white/95 shadow-2xl backdrop-blur-2xl dark:border-slate-800/80 dark:bg-slate-900/95 lg:max-w-lg lg:rounded-3xl overflow-hidden sheet-enter"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header & Search Bar */}
        <div className="border-b border-slate-200/80 p-4 dark:border-slate-800/80">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Building2 size={18} className="text-accent" />
              <h3 className="font-bold text-base text-slate-900 dark:text-white">Campus Buildings</h3>
            </div>
            <button
              className="btn-ghost !min-h-[32px] h-8 w-8 rounded-full p-0"
              onClick={onClose}
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>

          <div className="relative flex items-center">
            <Search size={16} className="absolute left-3 text-slate-400" />
            <input
              autoFocus
              className="w-full rounded-xl border border-slate-200 bg-slate-50/80 pl-9 pr-9 py-2 text-sm outline-none transition focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20 dark:border-slate-700 dark:bg-slate-800/80 dark:focus:bg-slate-900 dark:text-white"
              placeholder="Search by name (e.g. Sahara, SOE, Physics...)"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            {q && (
              <button
                onClick={() => setQ('')}
                className="absolute right-3 text-xs text-slate-400 hover:text-slate-600"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Group Filter Chips */}
          <div className="flex gap-1.5 overflow-x-auto pt-3 pb-1 [scrollbar-width:none]">
            {tabs.map((g) => (
              <button
                key={g}
                onClick={() => setActiveGroup(g)}
                className={`chip !min-h-[28px] text-xs font-semibold ${
                  activeGroup === g
                    ? 'border-accent bg-accent text-white shadow-sm'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
                }`}
              >
                {g}
              </button>
            ))}
          </div>
        </div>

        {/* Building List */}
        <div className="overflow-y-auto p-3 space-y-1 divide-y divide-slate-100 dark:divide-slate-800/60">
          {matches.map((b) => (
            <button
              key={b.name}
              onClick={() => onPick(b)}
              className="flex w-full items-start gap-3 rounded-xl p-3 text-left transition-all hover:bg-slate-100/80 dark:hover:bg-slate-800/60 active:scale-[0.99]"
            >
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 text-accent dark:bg-teal-500/20">
                <MapPin size={16} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-sm text-slate-900 dark:text-white">{b.name}</p>
                {b.full && <p className="text-xs text-slate-500 dark:text-slate-400">{b.full}</p>}
                <span className="inline-block mt-0.5 text-[10px] font-medium text-slate-400 dark:text-slate-500">
                  {b.group}
                </span>
              </div>
            </button>
          ))}

          {!matches.length && (
            <div className="p-8 text-center">
              <Building2 size={32} className="mx-auto mb-2 text-slate-300 dark:text-slate-600" />
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">No building found matching &ldquo;{q}&rdquo;</p>
              <p className="text-xs text-slate-400 mt-1">Tap directly on the campus map instead to drop a custom pin.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

