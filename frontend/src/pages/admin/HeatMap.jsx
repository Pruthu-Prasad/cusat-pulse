import { useEffect, useMemo, useState } from 'react'
import { Flame, MapPin, Filter, X, ChevronDown, RotateCcw } from 'lucide-react'
import { api, CATEGORY_COLORS, STATUS_LABEL } from '../../api'
import CampusMap from '../../components/CampusMap'
import IssueDetail from './IssueDetail'

const LEVELS = ['Low', 'Medium', 'High', 'Critical']
const STATUSES = { open: ['OPEN', 'FIX_SUBMITTED'], awaiting: ['AWAITING_STUDENT_CHECK'], reopened: ['REOPENED'], resolved: ['RESOLVED'] }

export default function HeatMap({ version, dark }) {
  const [issues, setIssues] = useState([])
  const [links, setLinks] = useState([])
  const [mode, setMode] = useState('heat')
  const [cats, setCats] = useState(new Set())
  const [levels, setLevels] = useState(new Set())
  const [status, setStatus] = useState(new Set(['open', 'awaiting', 'reopened']))
  const [selected, setSelected] = useState(null)
  const [filtersOpen, setFiltersOpen] = useState(false)

  useEffect(() => {
    Promise.all([api('/api/issues?include_resolved=true'), api('/api/admin/heatmap')]).then(([m, h]) => {
      const weights = Object.fromEntries(h.points.map((p) => [p.id, p.weight]))
      setIssues(m.issues.map((i) => ({ ...i, weight: weights[i.id] ?? 0 })))
      setLinks(m.links)
    }).catch(() => {})
  }, [version])

  const shown = useMemo(() => issues.filter((i) =>
    (!cats.size || cats.has(i.category)) && (!levels.size || levels.has(i.threat_level)) &&
    [...status].some((s) => STATUSES[s].includes(i.status))), [issues, cats, levels, status])

  const toggle = (set, setter, v) => { const n = new Set(set); n.has(v) ? n.delete(v) : n.add(v); setter(n) }

  const activeFilterCount = cats.size + levels.size + (status.size < 4 ? 4 - status.size : 0)

  const resetFilters = () => {
    setCats(new Set())
    setLevels(new Set())
    setStatus(new Set(['open', 'awaiting', 'reopened']))
  }

  return (
    <div className="relative h-full w-full overflow-hidden">
      <CampusMap
        issues={shown}
        links={links}
        dark={dark}
        showPins={mode === 'pins'}
        heatPoints={mode === 'heat' ? shown : null}
        onIssueClick={(i) => setSelected(i.id)}
      />

      {/* Floating Control Bar */}
      <div className="absolute left-4 top-4 z-[500] flex flex-col gap-2 max-w-[calc(100%-32px)] sm:max-w-md">
        <div className="flex items-center gap-2 rounded-2xl border border-white/60 bg-white/85 p-1.5 shadow-xl shadow-slate-900/10 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-900/85">
          {/* Segmented Mode Switcher */}
          <div className="flex rounded-xl bg-slate-100/90 p-1 dark:bg-slate-800/90">
            <button
              onClick={() => setMode('heat')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                mode === 'heat'
                  ? 'bg-gradient-to-r from-teal-600 to-emerald-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              <Flame size={14} className={mode === 'heat' ? 'animate-pulse' : ''} />
              Heatmap
            </button>
            <button
              onClick={() => setMode('pins')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                mode === 'pins'
                  ? 'bg-gradient-to-r from-teal-600 to-emerald-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              <MapPin size={14} />
              Pins
            </button>
          </div>

          {/* Filter Toggle Button */}
          <button
            onClick={() => setFiltersOpen(!filtersOpen)}
            className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition-all ${
              filtersOpen || activeFilterCount > 0
                ? 'border-teal-500/50 bg-teal-50 text-teal-800 dark:bg-teal-500/15 dark:text-teal-300'
                : 'border-slate-200/80 bg-white/70 text-slate-700 hover:bg-slate-100 dark:border-slate-700/80 dark:bg-slate-800/70 dark:text-slate-300'
            }`}
          >
            <Filter size={13} />
            Filters
            {activeFilterCount > 0 && (
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-teal-600 text-[10px] font-bold text-white">
                {activeFilterCount}
              </span>
            )}
            <ChevronDown size={13} className={`transition-transform duration-200 ${filtersOpen ? 'rotate-180' : ''}`} />
          </button>

          <span className="ml-auto hidden pr-2 text-xs font-medium text-slate-500 dark:text-slate-400 sm:inline">
            <span className="font-bold text-slate-800 dark:text-white">{shown.length}</span> active
          </span>
        </div>

        {/* Expandable Filter Drawer Panel */}
        {filtersOpen && (
          <div className="slide-in rounded-2xl border border-white/60 bg-white/90 p-4 shadow-2xl backdrop-blur-xl dark:border-slate-800/80 dark:bg-slate-900/90 space-y-3.5 text-xs">
            <div className="flex items-center justify-between border-b border-slate-200/70 pb-2 dark:border-slate-800/70">
              <span className="font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 text-[11px]">
                Filter Incidents
              </span>
              {activeFilterCount > 0 && (
                <button
                  onClick={resetFilters}
                  className="flex items-center gap-1 text-[11px] font-semibold text-teal-600 hover:underline dark:text-teal-400"
                >
                  <RotateCcw size={11} /> Reset
                </button>
              )}
            </div>

            {/* Categories */}
            <div>
              <p className="mb-1.5 font-semibold text-slate-600 dark:text-slate-400">Category</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.keys(CATEGORY_COLORS).filter((c) => c !== 'Resolved').map((c) => {
                  const on = cats.has(c)
                  return (
                    <button
                      key={c}
                      onClick={() => toggle(cats, setCats, c)}
                      className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-all ${
                        on
                          ? 'bg-slate-900 text-white shadow-sm dark:bg-white dark:text-slate-900'
                          : 'border border-slate-200 bg-slate-50/80 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
                      }`}
                    >
                      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: CATEGORY_COLORS[c] }} />
                      {c}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Severity Levels */}
            <div>
              <p className="mb-1.5 font-semibold text-slate-600 dark:text-slate-400">Threat Level</p>
              <div className="flex flex-wrap gap-1.5">
                {LEVELS.map((l) => {
                  const on = levels.has(l)
                  return (
                    <button
                      key={l}
                      onClick={() => toggle(levels, setLevels, l)}
                      className={`rounded-full px-2.5 py-1 text-xs font-medium transition-all ${
                        on
                          ? 'bg-teal-600 text-white shadow-sm'
                          : 'border border-slate-200 bg-slate-50/80 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
                      }`}
                    >
                      {l}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Statuses */}
            <div>
              <p className="mb-1.5 font-semibold text-slate-600 dark:text-slate-400">Status</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.keys(STATUSES).map((s) => {
                  const on = status.has(s)
                  return (
                    <button
                      key={s}
                      onClick={() => toggle(status, setStatus, s)}
                      className={`rounded-full px-2.5 py-1 text-xs font-medium transition-all ${
                        on
                          ? 'bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900'
                          : 'border border-slate-200 bg-slate-50/80 text-slate-500 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400'
                      }`}
                    >
                      {STATUS_LABEL[STATUSES[s][0]]}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="pt-1 text-[11px] text-slate-400 dark:text-slate-500">
              {mode === 'heat' ? 'Density reflects priority weight.' : 'Click any pin marker to view full incident details.'}
            </div>
          </div>
        )}
      </div>

      {/* Selected Issue Drawer */}
      {selected && (
        <div className="absolute inset-y-0 right-0 z-[600] w-full max-w-lg overflow-y-auto border-l border-slate-200/80 bg-white shadow-2xl backdrop-blur-xl dark:border-slate-800 dark:bg-slate-950">
          <IssueDetail id={selected} version={version} onBack={() => setSelected(null)} />
        </div>
      )}
    </div>
  )
}
