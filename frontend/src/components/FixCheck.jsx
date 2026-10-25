import { useState } from 'react'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { api } from '../api'
import CameraCapture from './CameraCapture'
import { Countdown, Photo } from './Bits'

const CAMERA_TITLE = { resolved: 'Photo of the repaired location', unresolved: 'Photo of the problem now' }

// Verification window after a repair. Any student can respond, always with a current photo:
// Gemma's verdict on the photo decides whether the issue closes or is reopened and escalated.
export default function FixCheck({ issue, onChanged }) {
  const [mode, setMode] = useState(null)  // which claim the camera is open for
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const id = issue.id

  async function submit(shot) {
    const claim = mode
    setMode(null); setBusy(true)
    setMsg({ tone: 'info', text: 'Comparing your photo with the original report and the repair photo...' })
    const form = new FormData()
    form.append('image', shot.blob, `${claim}.jpg`)
    form.append('capture_token', shot.token)
    try {
      const r = await api(`/api/issues/${id}/${claim === 'resolved' ? 'confirm' : 'dispute'}`, { form })
      setMsg({ tone: r.outcome === 'resolved' && r.accepted ? 'ok' : r.outcome === 'unresolved' ? 'warn' : 'error', text: r.message })
      onChanged?.()
    } catch (e) { setMsg({ tone: 'error', text: e.message }) } finally { setBusy(false) }
  }

  const open = issue.status === 'AWAITING_STUDENT_CHECK'
  const tone = { ok: 'text-emerald-700 dark:text-emerald-300', warn: 'text-amber-700 dark:text-amber-300', error: 'text-red-600', info: 'muted' }

  return (
    <section className="space-y-3 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Verify the repair</h3>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">Maintenance has marked this issue as fixed. Verification window:</p>
        </div>
        {open && <Countdown deadline={issue.verify_deadline} />}
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <figure><figcaption className="mb-1 muted">Reported</figcaption><Photo name={issue.reports?.[0]?.image_path} className="aspect-square w-full" /></figure>
        <figure><figcaption className="mb-1 muted">After repair</figcaption><Photo name={issue.after_photo} className="aspect-square w-full" /></figure>
      </div>
      {open && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <button className="btn-primary text-sm" disabled={busy} onClick={() => setMode('resolved')}>
              {busy ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />} Confirm resolved
            </button>
            <button className="btn-ghost text-sm text-red-700 dark:text-red-400" disabled={busy} onClick={() => setMode('unresolved')}>
              <XCircle size={16} /> Report unresolved
            </button>
          </div>
          <p className="text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
            Both options need a current photo of the location, verified by Gemma. A verified repair closes the issue;
            if the problem is still visible, the issue is reopened and escalated. A false "unresolved" claim lowers your trust score.
            With no response, the issue closes automatically when the window ends.
          </p>
        </>
      )}
      {msg && <p className={`text-sm ${tone[msg.tone]}`}>{msg.text}</p>}
      {mode && <CameraCapture title={CAMERA_TITLE[mode]} onClose={() => setMode(null)} onCapture={submit} />}
    </section>
  )
}
