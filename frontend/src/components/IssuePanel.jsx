import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Camera, Check, ClipboardList, History, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import ThreatBadge, { CategoryDot, StatusChip } from './ThreatBadge'
import { timeAgo } from './Bits'
import FixCheck from './FixCheck'

const STEPS = ['Reported', 'Repair submitted', 'Verification', 'Resolved']
const STEP_OF = { OPEN: 0, REOPENED: 0, FIX_SUBMITTED: 1, AWAITING_STUDENT_CHECK: 2, RESOLVED: 3 }

function Lifecycle({ status }) {
  const at = STEP_OF[status] ?? 0
  return (
    <ol className="flex items-center gap-1" aria-label="Issue progress">
      {STEPS.map((label, n) => {
        const done = n < at || status === 'RESOLVED'
        const current = n === at && status !== 'RESOLVED'
        return (
          <li key={label} className="flex min-w-0 flex-1 flex-col gap-1.5">
            <span className={`h-1.5 rounded-full ${done ? 'bg-accent' : current ? (status === 'REOPENED' ? 'bg-red-500' : 'bg-accent/50') : 'bg-slate-200 dark:bg-slate-800'}`} />
            <span className={`flex items-center gap-1 truncate text-[10px] font-semibold uppercase tracking-wide ${done || current ? 'text-slate-700 dark:text-slate-200' : 'text-slate-400'}`}>
              {done && <Check size={10} />}{n === 0 && status === 'REOPENED' ? 'Reopened' : label}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function Action({ title, body, children }) {
  return (
    <section className="space-y-3 rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
      <div>
        <h3 className="text-sm font-semibold text-slate-900 dark:text-white">{title}</h3>
        <p className="mt-0.5 text-xs leading-relaxed text-slate-500 dark:text-slate-400">{body}</p>
      </div>
      {children}
    </section>
  )
}

// Issue summary for students on the map, with the one action that fits the issue's current state.
export default function IssuePanel({ issue: summary, onClose, onReport, onChanged }) {
  const [issue, setIssue] = useState(null)

  const reload = useCallback(() => api(`/api/issues/${summary.id}`).then(setIssue).catch(() => {}), [summary.id])
  useEffect(() => { setIssue(null); reload() }, [reload])

  const i = issue || summary
  const where = [i.building || 'Campus grounds', i.floor && (i.floor === 'Ground' ? 'Ground floor' : `Floor ${i.floor}`)].filter(Boolean).join(' · ')
  const n = i.unique_reporters

  return (
    <div className="space-y-4">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold text-slate-500">{i.id}</span>
            <StatusChip status={i.status} />
          </div>
          <h2 className="mt-1.5 text-lg font-bold leading-snug text-slate-900 dark:text-white">{i.title}</h2>
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            <CategoryDot category={i.category} /> {i.category} · {where}
          </p>
        </div>
        <button onClick={onClose} aria-label="Close" className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800">
          <X size={18} />
        </button>
      </header>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
        <ThreatBadge level={i.threat_level} score={i.priority} />
        <span>{n} {n === 1 ? 'report' : 'reports'}</span>
        {i.created_at && <span>Opened {timeAgo(i.created_at)}</span>}
      </div>

      <Lifecycle status={i.status} />

      {!!i.fix_disputed && i.status !== 'RESOLVED' && (
        <p className="flex items-start gap-2 rounded-xl bg-red-500/10 p-3 text-xs text-red-700 dark:text-red-300">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" /> A previous repair was disputed with photo evidence and is under review.
        </p>
      )}

      {i.status === 'AWAITING_STUDENT_CHECK' ? (
        issue ? <FixCheck issue={issue} onChanged={() => { reload(); onChanged?.() }} /> : <div className="shimmer h-40 w-full" />
      ) : issue?.i_reported && i.status !== 'RESOLVED' ? (
        <Action title="You reported this issue" body="You'll be asked to verify the repair once maintenance marks it fixed.">
          <Link to="/reports" className="btn-ghost w-full text-sm"><ClipboardList size={16} /> View in My Reports</Link>
        </Action>
      ) : i.status === 'RESOLVED' ? (
        <Action title="Has this problem returned?"
          body={`Submit a current photo. If Gemma verifies it is the same problem, ${i.id} is reopened and the repair is flagged for review.`}>
          <button className="btn-ghost w-full text-sm" onClick={() => onReport(i)}><History size={16} /> Report recurrence</button>
        </Action>
      ) : (
        <Action title="Affected by this issue?"
          body={`Add your photo to ${i.id}. Each independent report raises its priority with the maintenance team.`}>
          <button className="btn-primary w-full text-sm" onClick={() => onReport(i)}><Camera size={16} /> Add your report</button>
        </Action>
      )}
    </div>
  )
}
