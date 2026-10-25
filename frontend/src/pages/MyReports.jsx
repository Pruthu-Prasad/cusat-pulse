import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, XCircle, ClipboardList, ShieldAlert, Sparkles, Clock, AlertCircle } from 'lucide-react'
import { api } from '../api'
import CameraCapture from '../components/CameraCapture'
import ThreatBadge, { StatusChip } from '../components/ThreatBadge'
import { Countdown, Photo, Skeleton, timeAgo } from '../components/Bits'

export default function MyReports() {
  const [reports, setReports] = useState(null)
  const [checking, setChecking] = useState(null)  // { issueId, claim: 'resolved' | 'unresolved' } while the camera is open
  const [msg, setMsg] = useState({})
  const [busy, setBusy] = useState(null)

  const load = useCallback(() => api('/api/me').then((r) => setReports(r.reports)).catch(() => setReports([])), [])
  useEffect(() => { load(); const t = setInterval(load, 10000); return () => clearInterval(t) }, [load])

  // Both answers need a current photo; Gemma's verdict decides whether the issue closes or is reopened.
  async function verify(shot) {
    const { issueId, claim } = checking
    setChecking(null)
    setBusy(issueId)
    setMsg((m) => ({ ...m, [issueId]: { ok: true, text: 'Comparing your photo with the original report and the repair photo...' } }))
    const form = new FormData()
    form.append('image', shot.blob, `${claim}.jpg`)
    form.append('capture_token', shot.token)
    try {
      const r = await api(`/api/issues/${issueId}/${claim === 'resolved' ? 'confirm' : 'dispute'}`, { form })
      setMsg((m) => ({ ...m, [issueId]: { ok: r.accepted || r.outcome === 'unresolved', text: r.message } }))
      load()
    } catch (e) {
      setMsg((m) => ({ ...m, [issueId]: { ok: false, text: e.message } }))
    } finally {
      setBusy(null)
    }
  }

  if (!reports) {
    return (
      <div className="mx-auto max-w-2xl space-y-4 p-5 lg:p-8">
        <Skeleton rows={4} />
      </div>
    )
  }

  const awaitingCount = reports.filter((r) => r.status === 'AWAITING_STUDENT_CHECK').length

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-5 lg:p-8">
      {/* ── Header ── */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">My Reports</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Track the status of your campus submissions and audit repair quality
        </p>
      </div>

      {/* ── Notice Banner if there are fixes to verify ── */}
      {awaitingCount > 0 && (
        <div className="flex items-center gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-900 backdrop-blur-sm dark:text-amber-200">
          <AlertCircle size={20} className="shrink-0 text-amber-600 dark:text-amber-400" />
          <div className="text-xs">
            <p className="font-bold">{awaitingCount} repair{awaitingCount !== 1 ? 's' : ''} awaiting your verification!</p>
            <p className="mt-0.5 opacity-90">Confirm whether the work was completed properly or dispute with a photo.</p>
          </div>
        </div>
      )}

      {/* ── Empty State ── */}
      {reports.length === 0 && (
        <div className="card py-16 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-500/10 text-teal-600 dark:bg-teal-500/15 dark:text-teal-400">
            <ClipboardList size={26} />
          </div>
          <h3 className="text-base font-bold text-slate-900 dark:text-white">No reports submitted yet</h3>
          <p className="mx-auto mt-1 max-w-xs text-xs text-slate-500 dark:text-slate-400">
            Spot a maintenance issue on campus? Tap the camera on the map to file a report.
          </p>
        </div>
      )}

      {/* ── Report Cards ── */}
      <div className="space-y-4">
        {reports.map((r) => (
          <div key={r.id} className="card space-y-4">
            <div className="flex items-start gap-4">
              <Photo name={r.image_path} alt="" className="h-20 w-20 shrink-0 rounded-xl" />
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-slate-400">
                    {r.id}{r.issue_id && ` → ${r.issue_id}`}
                  </span>
                  {r.report_status === 'FLAGGED' ? (
                    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-700 dark:bg-slate-700 dark:text-slate-300">
                      Photo not verified
                    </span>
                  ) : (
                    <StatusChip status={r.status} />
                  )}
                  {!!r.fix_disputed && (
                    <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700 dark:bg-red-500/15 dark:text-red-300">
                      Fix disputed
                    </span>
                  )}
                </div>

                <p className="font-bold text-slate-900 dark:text-white leading-snug">
                  {r.title || r.ai_description}
                </p>

                <div className="flex flex-wrap items-center gap-2 pt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  {r.threat_level && <ThreatBadge level={r.threat_level} />}
                  <span>opened {timeAgo(r.created_at)}</span>
                  {r.unique_reporters > 1 && (
                    <span>· {r.unique_reporters} student{r.unique_reporters === 1 ? '' : 's'} reported</span>
                  )}
                </div>
              </div>
            </div>

            {/* Awaiting Student Verification Box */}
            {r.status === 'AWAITING_STUDENT_CHECK' && (
              <div className="space-y-3.5 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 backdrop-blur-sm dark:border-amber-500/20 dark:bg-amber-500/5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-900 dark:text-white">
                    Maintenance marked this as fixed. Please verify.
                  </span>
                  <Countdown deadline={r.verify_deadline} />
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <p className="mb-1 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Before</p>
                    <Photo name={r.image_path} className="aspect-square w-full rounded-xl" />
                  </div>
                  <div>
                    <p className="mb-1 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Repair Proof</p>
                    <Photo name={r.after_photo} className="aspect-square w-full rounded-xl" />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2.5 pt-1">
                  <button
                    className="btn-primary !min-h-[40px] text-xs"
                    disabled={busy === r.issue_id}
                    onClick={() => setChecking({ issueId: r.issue_id, claim: 'resolved' })}
                  >
                    <CheckCircle2 size={16} /> Confirm resolved
                  </button>
                  <button
                    className="btn-danger !min-h-[40px] text-xs"
                    disabled={busy === r.issue_id}
                    onClick={() => setChecking({ issueId: r.issue_id, claim: 'unresolved' })}
                  >
                    <XCircle size={16} /> Report unresolved
                  </button>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  Both options need a current photo of the location. A verified repair closes the issue; if the problem is still visible it is reopened and escalated.
                </p>
              </div>
            )}

            {msg[r.issue_id] && (
              <p className={`text-xs font-medium ${msg[r.issue_id].ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600'}`}>
                {msg[r.issue_id].text}
              </p>
            )}
          </div>
        ))}
      </div>

      {checking && (
        <CameraCapture
          title={checking.claim === 'resolved' ? 'Photo of the repaired location' : 'Photo of the problem now'}
          onClose={() => setChecking(null)}
          onCapture={verify}
        />
      )}
    </div>
  )
}
