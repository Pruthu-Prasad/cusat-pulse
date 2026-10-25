import { useState } from 'react'
import { Ban, Loader2 } from 'lucide-react'
import { api } from '../api'
import CameraCapture from './CameraCapture'

// Staff can only call a report fake with proof: a fresh photo of the reported spot showing no problem.
// Gemma compares it with the student's photo; the verdict is written to the ledger either way.
export default function MarkFakeButton({ reportId, onDone }) {
  const [camera, setCamera] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)

  function start() {
    if (!window.confirm(`To mark ${reportId} as fake, go to the reported spot and photograph it showing there is no problem. Gemma will compare it with the student's photo. Continue?`)) return
    setResult(null)
    setCamera(true)
  }

  async function submit(shot) {
    setCamera(false); setBusy(true)
    const form = new FormData()
    form.append('image', shot.blob, 'proof.jpg')
    form.append('capture_token', shot.token)
    try {
      const r = await api(`/api/admin/reports/${reportId}/mark-fake`, { form })
      setResult({ ok: r.marked_fake, text: r.reason })
      if (r.marked_fake) onDone?.()
    } catch (e) {
      setResult({ ok: false, text: e.message })
    } finally { setBusy(false) }
  }

  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      {result?.ok ? <span className="text-xs font-semibold text-red-600">Marked fake</span> : (
        <button className="btn-ghost !min-h-[32px] px-2 text-xs" onClick={start} disabled={busy}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Ban size={14} />} {busy ? 'Gemma is checking...' : 'Mark as fake'}
        </button>
      )}
      {result && <p className={`max-w-[260px] text-right text-xs ${result.ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>{result.text}</p>}
      {camera && <CameraCapture title="Proof: photo of the reported spot" onClose={() => setCamera(false)} onCapture={submit} />}
    </div>
  )
}
