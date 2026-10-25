import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, ChevronDown, ChevronRight, ShieldX, TrendingUp, Layers, Search } from 'lucide-react'
import { api } from '../../api'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import ThreatBadge, { CategoryDot, StatusChip } from '../../components/ThreatBadge'
import { GpsChip, Photo, Skeleton, timeAgo } from '../../components/Bits'
import AgentTrace from '../../components/AgentTrace'
import IssueDetail from './IssueDetail'
import MarkFakeButton from '../../components/MarkFakeButton'

export default function Issues({ version }) {
  const [data, setData] = useState(null)
  const [selected, setSelected] = useState(null)
  const [collapsed, setCollapsed] = useState({})
  const [showResolved, setShowResolved] = useState(false)
  const [search, setSearch] = useState('')
  const wide = useMediaQuery('(min-width: 1024px)')

  useEffect(() => { api('/api/admin/issues/grouped').then(setData).catch(() => {}) }, [version])

  const groups = useMemo(() => (data?.groups || []).map((g) => ({
    ...g,
    locations: g.locations.map((l) => ({ ...l, issues: l.issues.filter((i) => showResolved || !['RESOLVED', 'DISMISSED'].includes(i.status)) })).filter((l) => l.issues.length),
  })).filter((g) => g.locations.length), [data, showResolved])

  const flat = useMemo(() => groups.flatMap((g) => collapsed[g.category] ? [] : g.locations.flatMap((l) => l.issues)), [groups, collapsed])

  // Apply search filter
  const filteredGroups = useMemo(() => {
    if (!search.trim()) return groups
    const q = search.toLowerCase()
    return groups.map((g) => ({
      ...g,
      locations: g.locations.map((l) => ({
        ...l,
        issues: l.issues.filter((i) => i.title.toLowerCase().includes(q) || l.building.toLowerCase().includes(q)),
      })).filter((l) => l.issues.length),
    })).filter((g) => g.locations.length)
  }, [groups, search])

  const totalOpen = useMemo(() => groups.reduce((n, g) => n + g.locations.reduce((m, l) => m + l.issues.length, 0), 0), [groups])

  useEffect(() => {
    if (wide && !selected && data?.top?.[0]) setSelected(data.top[0].id)
  }, [wide, data, selected])

  useEffect(() => {
    function onKey(e) {
      if (!['ArrowDown', 'ArrowUp'].includes(e.key) || e.target.tagName === 'INPUT') return
      e.preventDefault()
      const idx = flat.findIndex((i) => i.id === selected)
      const next = flat[Math.max(0, Math.min(flat.length - 1, idx + (e.key === 'ArrowDown' ? 1 : -1)))]
      if (next) setSelected(next.id)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [flat, selected])

  if (!data) return <div className="p-8"><Skeleton rows={6} /></div>
  if (!wide && selected) return <div className="h-full overflow-y-auto"><IssueDetail id={selected} version={version} onBack={() => setSelected(null)} /></div>

  const list = (
    <div className="space-y-6 p-5 lg:p-8">
      {/* ── Page Header ── */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Issues</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {totalOpen} open issue{totalOpen !== 1 ? 's' : ''} across {groups.length} categor{groups.length !== 1 ? 'ies' : 'y'}
        </p>
      </div>

      {/* ── Top 5 Priority Strip ── */}
      {data.top.length > 0 && (
        <section>
          <div className="mb-3 flex items-center gap-2">
            <TrendingUp size={15} className="text-accent" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Top Priority</span>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2 snap-x snap-mandatory">
            {data.top.map((i, n) => (
              <button key={i.id} onClick={() => setSelected(i.id)}
                className={`card-hover !p-4 w-56 shrink-0 snap-start text-left ${selected === i.id ? '!border-accent ring-2 ring-accent/30' : ''}`}>
                <div className="flex items-center justify-between">
                  <span className={`flex h-8 w-8 items-center justify-center rounded-xl text-sm font-bold text-white ${
                    n === 0 ? 'bg-gradient-to-br from-red-500 to-rose-600' :
                    n === 1 ? 'bg-gradient-to-br from-orange-500 to-amber-600' :
                    'bg-gradient-to-br from-slate-500 to-slate-600'
                  }`}>
                    {n + 1}
                  </span>
                  <ThreatBadge level={i.threat_level} score={i.priority} />
                </div>
                <p className="mt-3 truncate text-sm font-bold text-slate-900 dark:text-white">{i.title}</p>
                <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">{i.building}</p>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── Toolbar ── */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className="input !pl-9 !py-2 !text-sm"
            placeholder="Search issues…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <label className="flex items-center gap-2 rounded-xl border border-slate-200/80 bg-white/80 px-3 py-2 text-sm font-medium text-slate-600 backdrop-blur-sm transition-colors hover:bg-slate-100/80 dark:border-slate-700/80 dark:bg-slate-900/80 dark:text-slate-300 dark:hover:bg-slate-800/80 cursor-pointer">
          <input type="checkbox" checked={showResolved} onChange={(e) => setShowResolved(e.target.checked)} className="accent-teal-600 h-3.5 w-3.5" />
          Show resolved
        </label>
      </div>

      {/* ── Category Groups ── */}
      <section className="space-y-4">
        {filteredGroups.length === 0 && (
          <div className="card text-center py-12">
            <Layers size={32} className="mx-auto mb-3 text-slate-400" />
            <p className="text-sm font-medium text-slate-600 dark:text-slate-300">No open issues. Nice.</p>
            <p className="mt-1 text-xs text-slate-400">Campus is looking good right now.</p>
          </div>
        )}
        {filteredGroups.map((g) => {
          const count = g.locations.reduce((n, l) => n + l.issues.length, 0)
          const isCollapsed = collapsed[g.category]
          return (
            <div key={g.category} className="card !p-0 overflow-hidden">
              <button
                className="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-slate-50/80 dark:hover:bg-slate-800/40"
                onClick={() => setCollapsed({ ...collapsed, [g.category]: !isCollapsed })}
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500 transition-transform dark:bg-slate-800 dark:text-slate-400">
                  {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                </span>
                <CategoryDot category={g.category} />
                <span className="text-sm font-bold text-slate-900 dark:text-white">{g.category}</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                  {count}
                </span>
              </button>

              {!isCollapsed && (
                <div className="border-t border-slate-100 dark:border-slate-800/80">
                  {g.locations.map((l) => l.issues.map((i) => (
                    <button key={i.id} onClick={() => setSelected(i.id)}
                      className={`group flex w-full items-center gap-4 px-5 py-3.5 text-left transition-all hover:bg-slate-50/80 dark:hover:bg-slate-800/40 ${
                        selected === i.id ? 'bg-teal-50/60 border-l-2 border-l-teal-500 dark:bg-teal-500/10' : 'border-l-2 border-l-transparent'
                      }`}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">{i.title}</p>
                        <p className="mt-0.5 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                          <span>{l.building}</span>
                          <span className="h-1 w-1 rounded-full bg-slate-300 dark:bg-slate-600" />
                          <span>{i.unique_reporters} reporter{i.unique_reporters === 1 ? '' : 's'}</span>
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {i.status !== 'OPEN' && <StatusChip status={i.status} />}
                        <ThreatBadge level={i.threat_level} score={i.priority} />
                      </div>
                    </button>
                  )))}
                </div>
              )}
            </div>
          )
        })}
      </section>

      {/* ── Flagged Photos ── */}
      {data.flagged.length > 0 && <Flagged reports={data.flagged} />}
    </div>
  )

  if (!wide) return <div className="h-full overflow-y-auto">{list}</div>
  return (
    <div className="grid h-full grid-cols-[minmax(400px,1fr)_minmax(440px,1.2fr)]">
      <div className="overflow-y-auto border-r border-slate-200/70 dark:border-slate-800/70">{list}</div>
      <div className="overflow-y-auto bg-slate-50/50 dark:bg-slate-950/50">
        {selected ? <IssueDetail id={selected} version={version} /> : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-8">
            <Layers size={40} className="text-slate-300 dark:text-slate-700" />
            <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Select an issue to view details</p>
          </div>
        )}
      </div>
    </div>
  )
}

function Flagged({ reports }) {
  const [jobs, setJobs] = useState({})  // report id -> grouping job id, once staff accept it as real
  const [errors, setErrors] = useState({})

  async function accept(id) {
    if (!window.confirm(`Accept ${id} as a real problem? Gemma will group and rank it like a normal report.`)) return
    try {
      const r = await api(`/api/admin/reports/${id}/accept`, { method: 'POST' })
      setJobs((j) => ({ ...j, [id]: r.job_id }))
    } catch (e) { setErrors((x) => ({ ...x, [id]: e.message })) }
  }

  return (
    <section className="card !p-5">
      <div className="mb-4 flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-red-500/10">
          <ShieldX size={16} className="text-red-500" />
        </div>
        <span className="text-sm font-bold text-slate-900 dark:text-white">Flagged Photos</span>
        <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-600 dark:bg-red-500/15 dark:text-red-400">
          {reports.length}
        </span>
      </div>
      <div className="space-y-3">
        {reports.map((r) => (
          <div key={r.id} className="rounded-xl border border-slate-100 bg-slate-50/50 p-3 dark:border-slate-800/80 dark:bg-slate-900/40">
            <div className="flex items-center gap-4">
              <Photo name={r.image_path} className="h-14 w-14 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-900 dark:text-white">
                  <span className="font-mono text-xs text-slate-500 dark:text-slate-400">{r.id}</span> · {r.name} · {r.building}
                </p>
                <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">{r.ai_description}</p>
                <div className="mt-1 text-[11px]"><GpsChip flag={r.gps_flag} /></div>
              </div>
              {!jobs[r.id] && (
                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  <button className="btn-ghost !min-h-[32px] px-2 text-xs text-emerald-700 dark:text-emerald-400" onClick={() => accept(r.id)}>
                    <CheckCircle2 size={14} /> Accept as real
                  </button>
                  <MarkFakeButton reportId={r.id} />
                </div>
              )}
            </div>
            {errors[r.id] && <p className="mt-2 text-xs text-red-600">{errors[r.id]}</p>}
            {jobs[r.id] && <div className="mt-3 border-t border-slate-200 pt-3 dark:border-slate-800"><AgentTrace jobId={jobs[r.id]} /></div>}
          </div>
        ))}
      </div>
    </section>
  )
}
