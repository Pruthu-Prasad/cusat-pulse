import { useEffect, useState } from 'react'
import { Copy, Check, Clock, Sparkles } from 'lucide-react'
import { photo } from '../api'

export function PriorityBreakdown({ b }) {
  if (!b) return null
  const { S, E, C, R } = b.inputs
  const metrics = [
    { label: 'Severity', formula: '0.40 × S', val: b.parts.severity, max: 4.0, color: 'bg-red-500' },
    { label: 'Emergency', formula: '0.25 × E', val: b.parts.emergency, max: 2.5, color: 'bg-amber-500' },
    { label: 'Complexity', formula: '0.20 × C', val: b.parts.complexity, max: 2.0, color: 'bg-blue-500' },
    { label: 'Student Reporters', formula: '0.15 × min(10, 2.5R)', val: b.parts.reporters, max: 1.5, color: 'bg-teal-500' },
  ]

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-slate-50/70 p-3.5 backdrop-blur-sm dark:border-slate-800/80 dark:bg-slate-900/60">
      <div className="mb-2.5 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          <Sparkles size={13} className="text-accent" /> Priority Breakdown
        </span>
        <span className="rounded-lg bg-accent/10 px-2 py-0.5 font-mono text-xs font-bold text-accent dark:bg-accent/20">
          Total {b.priority.toFixed(2)}
        </span>
      </div>

      <div className="space-y-2">
        {metrics.map((m) => {
          const pct = Math.min(100, Math.round((m.val / m.max) * 100))
          return (
            <div key={m.label} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-slate-600 dark:text-slate-300">
                  {m.label} <span className="font-mono text-[11px] text-slate-400">({m.formula})</span>
                </span>
                <span className="font-mono font-semibold text-slate-700 dark:text-slate-200">{m.val.toFixed(2)}</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200/70 dark:bg-slate-800">
                <div className={`h-full rounded-full transition-all duration-500 ${m.color}`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          )
        })}

        {b.parts.age > 0 && (
          <div className="flex justify-between pt-1 text-xs text-slate-500 dark:text-slate-400">
            <span>Age bonus</span>
            <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">+{b.parts.age.toFixed(2)}</span>
          </div>
        )}
      </div>
    </div>
  )
}

export function Countdown({ deadline }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  const ms = new Date(deadline).getTime() - now
  if (!deadline || ms <= 0) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-200/80 px-2.5 py-0.5 font-mono text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
        <Clock size={12} /> Time is up
      </span>
    )
  }

  const h = Math.floor(ms / 3.6e6)
  const m = Math.floor((ms % 3.6e6) / 6e4)
  const s = Math.floor((ms % 6e4) / 1000)
  const urgent = ms < 60000

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-xs font-semibold backdrop-blur-sm transition-all ${
      urgent
        ? 'border-red-500/40 bg-red-500/10 text-red-700 animate-pulse dark:text-red-300'
        : 'border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-300'
    }`}>
      <Clock size={12} className={urgent ? 'animate-spin' : ''} />
      <span>{h ? `${h}h ` : ''}{m}m {String(s).padStart(2, '0')}s left</span>
    </span>
  )
}

export function CopyButton({ text, label = 'Copy' }) {
  const [done, setDone] = useState(false)
  return (
    <button
      className="btn-ghost !min-h-[30px] rounded-lg px-2.5 text-xs transition-transform active:scale-95"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
          setDone(true)
          setTimeout(() => setDone(false), 1500)
        } catch { /* ignore */ }
      }}
      aria-label="Copy to clipboard"
    >
      {done ? <Check size={13} className="text-emerald-500" /> : <Copy size={13} />}
      <span className={done ? 'text-emerald-600 font-semibold dark:text-emerald-400' : ''}>{done ? 'Copied' : label}</span>
    </button>
  )
}

export function Photo({ name, alt = '', className = '' }) {
  const [loaded, setLoaded] = useState(false)
  if (!name) return <div className={`shimmer ${className}`} />

  return (
    <div className={`relative overflow-hidden rounded-2xl bg-slate-100 shadow-sm ring-1 ring-black/5 dark:bg-slate-800 dark:ring-white/10 ${className}`}>
      {!loaded && <div className="absolute inset-0 shimmer" />}
      <img
        src={photo(name)}
        alt={alt}
        loading="lazy"
        onLoad={() => setLoaded(true)}
        className={`h-full w-full object-cover transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
      />
    </div>
  )
}

export function timeAgo(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

const GPS = {
  far_from_pin: { text: 'GPS far from pin', cls: 'bg-amber-500/15 text-amber-700 dark:text-amber-300' },
  outside_campus: { text: 'GPS outside campus', cls: 'bg-red-500/15 text-red-700 dark:text-red-300' },
  no_gps: { text: 'no GPS', cls: 'bg-slate-200/70 text-slate-500 dark:bg-slate-800 dark:text-slate-400' },
}

// The GPS check only flags, never blocks (indoor GPS is weak), so staff see it here.
export function GpsChip({ flag }) {
  if (flag === undefined) return null
  if (!flag) return <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-emerald-700 dark:text-emerald-400">GPS ok</span>
  const g = GPS[flag] || GPS.no_gps
  return <span className={`rounded px-1.5 py-0.5 font-semibold ${g.cls}`}>{g.text}</span>
}

export function Skeleton({ rows = 3 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="shimmer h-16 w-full" />
      ))}
    </div>
  )
}

