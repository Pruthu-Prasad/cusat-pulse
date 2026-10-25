import { AlertOctagon, AlertTriangle, Info, ShieldAlert, CheckCircle, Clock } from 'lucide-react'
import { CATEGORY_COLORS, STATUS_LABEL } from '../api'

const THREAT = {
  Low: {
    cls: 'bg-slate-100/90 text-slate-700 border-slate-200 dark:bg-slate-800/80 dark:text-slate-300 dark:border-slate-700/80',
    Icon: Info,
    dot: 'bg-slate-400',
  },
  Medium: {
    cls: 'bg-amber-500/10 text-amber-800 border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-300 dark:border-amber-500/30',
    Icon: AlertTriangle,
    dot: 'bg-amber-500',
  },
  High: {
    cls: 'bg-orange-500/10 text-orange-800 border-orange-500/30 dark:bg-orange-500/15 dark:text-orange-300 dark:border-orange-500/30',
    Icon: ShieldAlert,
    dot: 'bg-orange-500',
  },
  Critical: {
    cls: 'bg-red-500/15 text-red-700 border-red-500/40 shadow-glow-red animate-pulse dark:bg-red-500/20 dark:text-red-300 dark:border-red-500/40',
    Icon: AlertOctagon,
    dot: 'bg-red-500',
  },
}

export default function ThreatBadge({ level, score }) {
  const t = THREAT[level] || THREAT.Low
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold backdrop-blur-sm transition-all ${t.cls}`}>
      <t.Icon size={12} className="shrink-0" />
      <span>{level}</span>
      {score != null && (
        <span className="ml-0.5 rounded-full bg-black/5 px-1.5 py-0.2 font-mono text-[11px] font-bold dark:bg-white/10">
          {Number(score).toFixed(1)}
        </span>
      )}
    </span>
  )
}

export function CategoryDot({ category }) {
  const color = CATEGORY_COLORS[category] || '#6b7280'
  return (
    <span className="relative inline-flex items-center justify-center">
      <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full shadow-sm" style={{ background: color }} />
    </span>
  )
}

const STATUS_CONFIG = {
  OPEN: {
    cls: 'bg-sky-500/10 text-sky-800 border-sky-500/30 dark:bg-sky-500/15 dark:text-sky-300 dark:border-sky-500/30',
    dot: 'bg-sky-500 animate-pulse',
  },
  REOPENED: {
    cls: 'bg-rose-500/10 text-rose-800 border-rose-500/30 dark:bg-rose-500/15 dark:text-rose-300 dark:border-rose-500/30',
    dot: 'bg-rose-500 animate-ping',
  },
  FIX_SUBMITTED: {
    cls: 'bg-purple-500/10 text-purple-800 border-purple-500/30 dark:bg-purple-500/15 dark:text-purple-300 dark:border-purple-500/30',
    dot: 'bg-purple-500',
  },
  AWAITING_STUDENT_CHECK: {
    cls: 'bg-amber-500/10 text-amber-800 border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-300 dark:border-amber-500/30',
    dot: 'bg-amber-500 animate-pulse',
  },
  RESOLVED: {
    cls: 'bg-emerald-500/10 text-emerald-800 border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-300 dark:border-emerald-500/30',
    dot: 'bg-emerald-500',
  },
  DISMISSED: {
    cls: 'bg-slate-200/70 text-slate-600 border-slate-300 line-through decoration-slate-400/60 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700',
    dot: 'bg-slate-400',
  },
}

export function StatusChip({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.OPEN
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold backdrop-blur-sm transition-all ${cfg.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${cfg.dot}`} />
      <span>{STATUS_LABEL[status] || status}</span>
    </span>
  )
}

