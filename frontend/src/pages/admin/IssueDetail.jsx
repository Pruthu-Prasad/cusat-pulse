import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowLeft, Link2, FileText, Users, History, Sparkles, Camera, ShieldCheck } from 'lucide-react'
import { api } from '../../api'
import MarkFakeButton from '../../components/MarkFakeButton'
import ThreatBadge, { CategoryDot, StatusChip } from '../../components/ThreatBadge'
import { CopyButton, GpsChip, Photo, PriorityBreakdown, Skeleton, timeAgo } from '../../components/Bits'

export default function IssueDetail({ id, version, onBack }) {
  const [issue, setIssue] = useState(null)
  const [lang, setLang] = useState('en')
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    api(`/api/issues/${id}`).then((r) => alive && setIssue(r)).catch((e) => alive && setError(e.message))
    return () => { alive = false }
  }, [id, version])

  const reload = () => api(`/api/issues/${id}`).then(setIssue).catch(() => {})
  const AUDIT_LABEL = { staff_fix: 'fix', student_dispute: 'dispute', staff_fake_check: 'fake check' }

  if (error) return <div className="p-8 text-red-600">{error}</div>
  if (!issue || issue.id !== id) return <div className="p-8"><Skeleton rows={5} /></div>
  const workOrder = lang === 'en' ? issue.work_order_en : issue.work_order_ml

  return (
    <div className="space-y-6 p-5 lg:p-8">
      {/* ── Back Button ── */}
      {onBack && (
        <button className="btn-ghost !min-h-[36px] px-3 text-sm" onClick={onBack}>
          <ArrowLeft size={16} /> Back
        </button>
      )}

      {/* ── Issue Header ── */}
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-lg bg-slate-100 px-2.5 py-1 font-mono text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
            {issue.id}
          </span>
          <StatusChip status={issue.status} />
          <ThreatBadge level={issue.threat_level} score={issue.priority} />
          {!!issue.fix_disputed && (
            <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-700 dark:bg-red-500/15 dark:text-red-300">
              Fix disputed
            </span>
          )}
          {issue.escalation > 0 && !['RESOLVED', 'DISMISSED'].includes(issue.status) && (
            <span className="flex items-center gap-1 rounded-full bg-red-600 px-2.5 py-1 text-xs font-bold text-white animate-pulse">
              <AlertTriangle size={12} /> Escalated · immediate action
            </span>
          )}
          {issue.failed_fix_attempts >= 2 && (
            <span className="flex items-center gap-1 rounded-full bg-orange-100 px-2.5 py-1 text-xs font-semibold text-orange-800 dark:bg-orange-500/15 dark:text-orange-300">
              <AlertTriangle size={12} /> {issue.failed_fix_attempts} failed fixes
            </span>
          )}
          {!!issue.needs_human_check && (
            <span className="rounded-full bg-slate-200 px-2.5 py-1 text-xs font-medium dark:bg-slate-700">
              Needs human check
            </span>
          )}
        </div>

        <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">{issue.title}</h2>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500 dark:text-slate-400">
          <span className="flex items-center gap-1.5"><CategoryDot category={issue.category} /> {issue.category}</span>
          <span className="h-1 w-1 rounded-full bg-slate-300 dark:bg-slate-600" />
          <span>{issue.building || 'Free pin'}{issue.floor && `, floor ${issue.floor}`}</span>
          <span className="h-1 w-1 rounded-full bg-slate-300 dark:bg-slate-600" />
          <span>{issue.unique_reporters} student{issue.unique_reporters === 1 ? '' : 's'}</span>
          <span className="h-1 w-1 rounded-full bg-slate-300 dark:bg-slate-600" />
          <span>opened {timeAgo(issue.created_at)}</span>
        </div>
      </header>

      {/* ── Photo Gallery ── */}
      <section>
        <div className="flex gap-3 overflow-x-auto pb-2 snap-x">
          {issue.reports.map((r) => (
            <Photo key={r.id} name={r.image_path} alt={r.id} className="h-32 w-32 shrink-0 snap-start" />
          ))}
          {issue.audits.filter((a) => a.image_path).map((a, n) => (
            <div key={n} className="relative shrink-0 snap-start">
              <Photo name={a.image_path} className={`h-32 w-32 ring-4 ${a.passed ? 'ring-emerald-500' : 'ring-red-500'}`} />
              <span className="absolute bottom-1.5 left-1.5 rounded-lg bg-black/70 px-2 py-0.5 text-[10px] font-semibold text-white backdrop-blur-sm">
                {AUDIT_LABEL[a.kind] || a.kind}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ── AI Summary & Breakdown ── */}
      <section className="card !p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Sparkles size={15} className="text-accent" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">AI Analysis</span>
        </div>
        <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">{issue.summary}</p>
        {issue.rank_reason && (
          <p className="text-sm font-semibold text-accent">{issue.rank_reason}</p>
        )}
        <PriorityBreakdown b={issue.breakdown} />
      </section>

      {/* ── Work Order ── */}
      {workOrder && (
        <section className="card !p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText size={15} className="text-accent" />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Work Order</span>
              {issue.trade_needed && (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                  {issue.trade_needed}
                </span>
              )}
            </div>
            <div className="flex gap-1.5">
              {['en', 'ml'].map((l) => (
                <button key={l} onClick={() => setLang(l)}
                  className={`chip !min-h-[30px] text-xs ${lang === l ? 'border-accent bg-accent text-white' : 'border-slate-300 dark:border-slate-700'}`}>
                  {l === 'en' ? 'English' : 'മലയാളം'}
                </button>
              ))}
              <CopyButton text={workOrder} />
            </div>
          </div>
          <pre className="whitespace-pre-wrap rounded-xl bg-slate-50 p-4 font-sans text-sm leading-relaxed text-slate-700 dark:bg-slate-800/50 dark:text-slate-300">
            {workOrder}
          </pre>
        </section>
      )}

      {/* ── Linked Issues ── */}
      {issue.links.length > 0 && (
        <section className="card !p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Link2 size={15} className="text-accent" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Possibly Linked</span>
          </div>
          <div className="space-y-2">
            {issue.links.map((l, n) => (
              <p key={n} className="text-sm text-slate-700 dark:text-slate-300">
                <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs dark:bg-slate-800">
                  {l.issue_a === issue.id ? l.issue_b : l.issue_a}
                </span>{' '}
                {l.note}
              </p>
            ))}
          </div>
        </section>
      )}

      {/* ── Reports ── */}
      <section className="card !p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Users size={15} className="text-accent" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Reports</span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            {issue.reports.length}
          </span>
        </div>
        <div className="space-y-3">
          {issue.reports.map((r) => (
            <div key={r.id} className="flex items-start gap-4 rounded-xl border border-slate-100 bg-slate-50/50 p-3.5 dark:border-slate-800/80 dark:bg-slate-900/40">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-900 dark:text-white">
                  {r.name}
                  <span className="ml-2 font-mono text-xs font-normal text-slate-400">{r.cusat_id}</span>
                </p>
                <p className="mt-1 text-xs leading-relaxed text-slate-500 dark:text-slate-400">{r.ai_description}</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono dark:bg-slate-800">{r.id}</span>
                  <span>trust {r.trust_score}</span>
                  <GpsChip flag={r.gps_flag} />
                  <span>{r.merge_type}{r.merge_reason && `: ${r.merge_reason}`}</span>
                  {!r.counts_toward_total && <span className="text-amber-600 dark:text-amber-400">not counted</span>}
                </div>
              </div>
              {r.status === 'ACTIVE' ? (
                <MarkFakeButton reportId={r.id} onDone={reload} />
              ) : <span className="shrink-0 text-xs font-semibold text-red-600">{r.status}</span>}
            </div>
          ))}
        </div>
      </section>

      {/* ── Fix Checks ── */}
      {issue.audits.length > 0 && (
        <section className="card !p-5 space-y-4">
          <div className="flex items-center gap-2">
            <ShieldCheck size={15} className="text-accent" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Fix Checks</span>
          </div>
          <div className="space-y-2">
            {issue.audits.map((a, n) => (
              <div key={n} className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50/50 px-3.5 py-2.5 text-sm dark:border-slate-800/80 dark:bg-slate-900/40">
                <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold text-white ${a.passed ? 'bg-emerald-500' : 'bg-red-500'}`}>
                  {a.passed ? '✓' : '✗'}
                </span>
                <span className="flex-1 text-slate-700 dark:text-slate-300">
                  {AUDIT_LABEL[a.kind] || a.kind.replace(/_/g, ' ')} · {a.reason}
                </span>
                <span className="text-xs text-slate-400">{timeAgo(a.created_at)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Ledger History ── */}
      {issue.ledger && (
        <section className="card !p-5 space-y-4">
          <div className="flex items-center gap-2">
            <History size={15} className="text-accent" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Ledger History</span>
          </div>
          <div className="space-y-1.5 font-mono text-xs">
            {issue.ledger.map((b) => (
              <div key={b.block_no} className="flex items-center gap-4 rounded-lg px-2 py-1.5 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40">
                <span className="w-8 shrink-0 text-slate-400">#{b.block_no}</span>
                <span className="w-44 shrink-0 font-sans font-medium text-slate-700 dark:text-slate-300">{b.event}</span>
                <span className="min-w-0 flex-1 truncate text-slate-400">{b.actor}</span>
                <span className="shrink-0 text-slate-400">{b.block_hash.slice(0, 10)}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
