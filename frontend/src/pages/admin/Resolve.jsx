import { useEffect, useState } from 'react'
import { Camera, CheckCircle2, ShieldX, Wrench, ArrowLeft } from 'lucide-react'
import { api } from '../../api'
import CameraCapture from '../../components/CameraCapture'
import ThreatBadge, { StatusChip } from '../../components/ThreatBadge'
import { Photo, Skeleton } from '../../components/Bits'

export default function Resolve({ version }) {
  const [issues, setIssues] = useState(null)
  const [pick, setPick] = useState(null)
  const [camera, setCamera] = useState(false)
  const [shot, setShot] = useState(null)
  const [note, setNote] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api('/api/issues').then((r) => setIssues(r.issues.filter((i) => ['OPEN', 'REOPENED', 'AWAITING_STUDENT_CHECK'].includes(i.status)))).catch(() => setIssues([]))
  }, [version])

  async function choose(i) {
    setResult(null); setShot(null); setNote(''); setError('')
    setPick(await api(`/api/issues/${i.id}`))
  }

  async function submit() {
    setBusy(true); setError('')
    const form = new FormData()
    form.append('image', shot.blob, 'fix.jpg')
    form.append('capture_token', shot.token)
    if (note.trim()) form.append('note', note.trim())
    try {
      setResult(await api(`/api/admin/issues/${pick.id}/fix`, { form }))
      setShot(null)
      setPick(await api(`/api/issues/${pick.id}`))
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  if (!issues) return <div className="p-8"><Skeleton rows={5} /></div>
  return (
    <div className="grid h-full lg:grid-cols-[minmax(340px,1fr)_1.3fr]">
      {/* ── Issue List ── */}
      <div className={`overflow-y-auto border-r border-slate-200/70 p-5 dark:border-slate-800/70 lg:p-8 ${pick ? 'hidden lg:block' : ''}`}>
        <div className="mb-5">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Resolve</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {issues.length} issue{issues.length !== 1 ? 's' : ''} awaiting fix
          </p>
        </div>

        <div className="space-y-3">
          {issues.length === 0 && (
            <div className="card text-center py-12">
              <Wrench size={32} className="mx-auto mb-3 text-slate-400" />
              <p className="text-sm font-medium text-slate-600 dark:text-slate-300">Nothing to fix right now.</p>
              <p className="mt-1 text-xs text-slate-400">Great work keeping things in order.</p>
            </div>
          )}
          {issues.map((i) => (
            <button key={i.id} onClick={() => choose(i)}
              className={`card-hover !p-4 flex w-full items-center gap-4 text-left ${
                pick?.id === i.id ? '!border-accent ring-2 ring-accent/30' : ''
              }`}
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-slate-900 dark:text-white">{i.title}</p>
                <p className="mt-0.5 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <span className="font-mono">{i.id}</span>
                  <span className="h-1 w-1 rounded-full bg-slate-300 dark:bg-slate-600" />
                  <span>{i.building}</span>
                </p>
              </div>
              <div className="flex flex-col items-end gap-1.5 shrink-0">
                <ThreatBadge level={i.threat_level} score={i.priority} />
                {i.status !== 'OPEN' && <StatusChip status={i.status} />}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* ── Resolution Panel ── */}
      <div className={`overflow-y-auto bg-slate-50/50 p-5 dark:bg-slate-950/50 lg:p-8 ${pick ? '' : 'hidden lg:block'}`}>
        {!pick ? (
          <div className="flex h-full flex-col items-center justify-center gap-3">
            <Wrench size={40} className="text-slate-300 dark:text-slate-700" />
            <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Pick an issue to resolve</p>
          </div>
        ) : (
          <div className="mx-auto max-w-xl space-y-6">
            <button className="btn-ghost !min-h-[36px] px-3 text-sm lg:hidden" onClick={() => setPick(null)}>
              <ArrowLeft size={16} /> Back
            </button>

            <div>
              <p className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <span className="font-mono">{pick.id}</span>
                <span className="h-1 w-1 rounded-full bg-slate-300 dark:bg-slate-600" />
                <span>{pick.building}</span>
              </p>
              <h2 className="mt-1 text-xl font-bold tracking-tight text-slate-900 dark:text-white">{pick.title}</h2>
            </div>

            {/* Before / After Comparison */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Before</p>
                <Photo name={pick.reports[0]?.image_path} className="aspect-square w-full" />
              </div>
              <div>
                <p className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">After</p>
                {shot ? (
                  <img src={shot.url} alt="Repair" className="aspect-square w-full rounded-2xl object-cover shadow-sm ring-1 ring-black/5" />
                ) : (
                  <div className="flex aspect-square w-full items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 dark:border-slate-700 dark:bg-slate-900">
                    <div className="text-center">
                      <Camera size={24} className="mx-auto mb-1 text-slate-400" />
                      <p className="text-xs text-slate-400">No photo yet</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Result Banners */}
            {result && (result.passed ? (
              <div className="slide-in flex gap-4 rounded-2xl bg-gradient-to-r from-emerald-600 to-emerald-500 p-5 text-white shadow-lg shadow-emerald-600/20">
                <CheckCircle2 className="shrink-0 mt-0.5" size={22} />
                <div>
                  <p className="font-bold">Fix verified by Gemma 4</p>
                  <p className="mt-1 text-sm opacity-90">{result.reason} Students now have time to confirm or dispute.</p>
                </div>
              </div>
            ) : (
              <div className="slide-in flex gap-4 rounded-2xl bg-gradient-to-r from-red-600 to-rose-500 p-5 text-white shadow-lg shadow-red-600/20">
                <ShieldX className="shrink-0 mt-0.5" size={22} />
                <div>
                  <p className="font-bold">Closure blocked by Gemma 4</p>
                  <p className="mt-1 text-sm opacity-90">{result.reason}</p>
                </div>
              </div>
            ))}

            {/* Action Buttons */}
            {['OPEN', 'REOPENED'].includes(pick.status) ? (
              <div className="space-y-3">
                {shot && (
                  <textarea
                    className="input"
                    rows={2}
                    placeholder="Note for the record (optional)"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                )}
                {error && <p className="text-sm font-medium text-red-600">{error}</p>}
                {shot ? (
                  <div className="grid grid-cols-2 gap-3">
                    <button className="btn-ghost" onClick={() => setCamera(true)}>Retake</button>
                    <button className="btn-primary" onClick={submit} disabled={busy}>
                      {busy ? 'Gemma is checking…' : 'Submit fix'}
                    </button>
                  </div>
                ) : (
                  <button className="btn-primary w-full" onClick={() => setCamera(true)}>
                    <Camera size={18} /> Take repair photo
                  </button>
                )}
              </div>
            ) : (
              <div className="rounded-xl border border-slate-200 bg-white/80 p-4 text-center text-sm dark:border-slate-800 dark:bg-slate-900/80">
                Status: <StatusChip status={pick.status} />
              </div>
            )}
          </div>
        )}
      </div>
      {camera && <CameraCapture title="Photo of the repair" onClose={() => setCamera(false)} onCapture={(s) => { setShot(s); setCamera(false); setResult(null) }} />}
    </div>
  )
}
