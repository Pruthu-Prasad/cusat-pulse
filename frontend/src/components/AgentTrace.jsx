import { useEffect, useRef, useState } from 'react'
import { Eye, Wrench, Link2, Sparkles, AlertCircle, Loader2, FilePlus2, Megaphone } from 'lucide-react'
import { api, ordinal, stream } from '../api'
import ThreatBadge from './ThreatBadge'

function iconFor(e) {
  if (e.kind === 'error') return AlertCircle
  if (e.kind === 'thought') return e.text.startsWith('Looking') || e.step <= 2 ? Eye : Sparkles
  if (e.text.startsWith('merge_into_issue') || e.text.startsWith('link_related')) return Link2
  if (e.text.startsWith('create_issue')) return FilePlus2
  if (e.text.startsWith('notify_department')) return Megaphone
  return Wrench
}

export default function AgentTrace({ jobId, onDone, onRetake }) {
  const [job, setJob] = useState(jobId)
  const [events, setEvents] = useState([])
  const [final, setFinal] = useState(null)
  const bottom = useRef(null)

  useEffect(() => {
    if (!job) return
    setEvents([]); setFinal(null)
    const es = stream(`/api/stream/${job}`, (e) => {
      if (e.kind === 'final') {
        const f = JSON.parse(e.text)
        setFinal(f); es.close(); onDone?.(f)
      } else {
        setEvents((list) => [...list, e])
        if (e.kind === 'error') { setFinal({ outcome: 'error', message: e.text }); es.close() }
      }
    })
    es.onerror = () => { /* EventSource retries on its own */ }
    return () => es.close()
  }, [job]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [events, final])

  async function clarify(choice) {
    const r = await api(`/api/reports/${final.job_id}/clarify`, { body: { choice } })
    setJob(r.job_id)
  }

  const visible = events.filter((e, n) => !(e.text.startsWith('Gemma is deciding') && events[n + 1]))

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Sparkles size={16} className="text-accent" /> Agent Trace <span className="muted font-normal">· Gemma 4 working live</span>
      </div>
      <ol className="space-y-1.5 font-mono text-[13px]">
        {visible.map((e) => {
          const Icon = iconFor(e)
          return (
            <li key={e.id} className={`slide-in flex gap-2 rounded-lg px-2 py-1.5 ${e.kind === 'tool_call' ? 'bg-teal-50 text-teal-900 dark:bg-teal-500/10 dark:text-teal-200' : e.kind === 'error' ? 'bg-red-50 text-red-800 dark:bg-red-500/10 dark:text-red-300' : 'text-slate-700 dark:text-slate-300'}`}>
              <Icon size={15} className="mt-0.5 shrink-0" /> <span className="break-words">{e.text}</span>
            </li>
          )
        })}
        {!final && <li className="flex items-center gap-2 px-2 py-1.5 text-slate-400"><Loader2 size={15} className="animate-spin" /> working...</li>}
      </ol>
      <div ref={bottom}>{final && <Result f={final} onRetake={onRetake} onClarify={clarify} />}</div>
    </div>
  )
}

function Result({ f, onRetake, onClarify }) {
  if (f.outcome === 'saved') {
    const merged = f.merge_type !== 'new'
    return (
      <div className="slide-in card mt-3 space-y-3 !p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{f.category}</span>
          <ThreatBadge level={f.threat_level} />
          {f.needs_human_check && <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs dark:bg-slate-700">Needs human check</span>}
        </div>
        <p className="text-sm"><span className="muted">Gemma sees: </span>{f.what_i_see}</p>
        <div className="rounded-xl bg-amber-50 p-3 text-sm font-medium text-amber-900 dark:bg-amber-500/10 dark:text-amber-200">
          What to do now: {f.advice}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span>Your report: <b className="font-mono">{f.report_id}</b></span>
          <span className="font-semibold text-accent">
            {merged ? `You are the ${ordinal(f.unique_students)} student to report this (${f.issue_id})` : `New issue created: ${f.issue_id}`}
          </span>
        </div>
        {f.reopened && (
          <div className="rounded-xl bg-red-50 p-3 text-sm font-medium text-red-800 dark:bg-red-500/10 dark:text-red-300">
            {f.issue_id} had been marked as fixed. Your photo shows the problem is back, so it has been reopened and the fix is flagged for staff.
          </div>
        )}
      </div>
    )
  }
  if (f.outcome === 'clarify') {
    return (
      <div className="slide-in card mt-3 space-y-3 !p-4">
        <p className="text-sm">Your note says <i>&ldquo;{f.note}&rdquo;</i>, but the photo shows: {f.photo_shows}</p>
        <p className="text-sm font-semibold">Which one do you mean?</p>
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" onClick={() => onClarify('photo')}>Go with the photo</button>
          <button className="btn-ghost" onClick={onRetake}>Retake photo</button>
        </div>
      </div>
    )
  }
  const text = f.outcome === 'not_hazard' ? `${f.message} Could you take a closer photo of the problem?` : f.message
  return (
    <div className="slide-in card mt-3 space-y-3 !p-4">
      <p className="text-sm">{text}</p>
      <button className="btn-primary" onClick={onRetake}>Take another photo</button>
    </div>
  )
}
