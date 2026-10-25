import { useCallback, useEffect, useRef, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { Building2, Camera, ChevronDown, ChevronUp, Crosshair, List, MapPin, Navigation, Send, Sparkles } from 'lucide-react'
import CampusMap, { CAMPUS_CENTER } from '../components/CampusMap'
import CameraCapture from '../components/CameraCapture'
import AgentTrace from '../components/AgentTrace'
import BuildingPicker from '../components/BuildingPicker'
import IssuePanel from '../components/IssuePanel'
import { Photo } from '../components/Bits'
import { api } from '../api'
import { QUICK, nearestBuilding } from '../buildings'

const FLOORS = ['Ground', '1', '2', '3+']
const QUICK_TAGS = ['🚰 Water Leak', '💡 Broken Light', '❄️ AC Down', '🚪 Door/Lock', '⚡ Power Outage', '🧹 Waste/Sanitation']

export default function StudentMap() {
  const { dark } = useOutletContext()
  const [issues, setIssues] = useState([])
  const [pin, setPin] = useState(null)
  const [building, setBuilding] = useState(null)
  const [floor, setFloor] = useState(null)
  const [camera, setCamera] = useState(false)
  const [shot, setShot] = useState(null)
  const [note, setNote] = useState('')
  const [jobId, setJobId] = useState(null)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [locating, setLocating] = useState(false)
  const [expanded, setExpanded] = useState(true)
  const [picker, setPicker] = useState(false)
  const [flyTo, setFlyTo] = useState(null)
  const gps = useRef({})

  const load = useCallback(() => api('/api/issues').then((r) => setIssues(r.issues)).catch(() => {}), [])
  useEffect(() => { load() }, [load])

  function pickPoint(p) {
    if (jobId || shot) return
    setPin(p)
    const b = nearestBuilding(p)
    setBuilding(b?.name || null)
    setFloor(null)
    setSelected(null)
    setError('')
  }

  function pickBuilding(b) {
    if (jobId || shot) return
    const p = { lat: b.lat, lng: b.lng }
    setPin(p)
    setFlyTo(p)
    setBuilding(b.name)
    setFloor(null)
    setSelected(null)
    setError('')
    setPicker(false)
  }

  function locateMe() {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser.')
      return
    }
    setLocating(true)
    setError('')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const p = { lat: pos.coords.latitude, lng: pos.coords.longitude }
        gps.current = p
        setFlyTo(p)
        pickPoint(p)
        setLocating(false)
      },
      () => {
        setError('Could not retrieve GPS location.')
        setLocating(false)
      },
      { enableHighAccuracy: true, timeout: 8000 }
    )
  }

  function centerCampus() {
    setFlyTo({ lat: CAMPUS_CENTER[0], lng: CAMPUS_CENTER[1] })
  }

  function addTag(tag) {
    setNote((prev) => {
      const clean = tag.replace(/^[^\s]+\s*/, '') // strip emoji
      if (prev.includes(clean)) return prev
      return prev ? `${prev}, ${clean}` : clean
    })
  }

  const chips = building && !QUICK.some((b) => b.name === building) ? [{ name: building }, ...QUICK] : QUICK

  function openCamera() {
    if (!pin) { setError('Tap the map or pick a building first.'); return }
    if (building && !floor) { setError('Which floor is it on?'); return }
    navigator.geolocation?.getCurrentPosition(
      (p) => { gps.current = { lat: p.coords.latitude, lng: p.coords.longitude } },
      () => { gps.current = {} }, { enableHighAccuracy: true, timeout: 8000 })
    setError(''); setCamera(true)
  }

  // Report against an existing issue: take its location straight from the issue (setting state and then
  // validating it in the same click would read stale values), then go to the camera.
  function reportExisting(i) {
    const p = { lat: i.lat, lng: i.lng }
    setPin(p); setFlyTo(p); setBuilding(i.building || null); setFloor(i.floor || null)
    setSelected(null); setError('')
    navigator.geolocation?.getCurrentPosition(
      (pos) => { gps.current = { lat: pos.coords.latitude, lng: pos.coords.longitude } },
      () => { gps.current = {} }, { enableHighAccuracy: true, timeout: 8000 })
    setCamera(true)
  }

  async function submit() {
    setBusy(true); setError('')
    const form = new FormData()
    form.append('image', shot.blob, 'photo.jpg')
    form.append('capture_token', shot.token)
    form.append('lat', pin.lat); form.append('lng', pin.lng)
    if (gps.current.lat) { form.append('gps_lat', gps.current.lat); form.append('gps_lng', gps.current.lng) }
    if (building) form.append('building', building)
    if (floor) form.append('floor', floor)
    if (note.trim()) form.append('note', note.trim())
    try {
      const r = await api('/api/reports', { form })
      setJobId(r.job_id); setExpanded(true)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  function reset() {
    setShot(null); setNote(''); setJobId(null); setPin(null); setBuilding(null); setFloor(null); load()
  }

  function retake() { setShot(null); setJobId(null); setCamera(true) }

  const panel = jobId || shot || selected
  return (
    <div className="relative flex h-full flex-col lg:flex-row overflow-hidden">
      {/* Map View Area */}
      <div className="relative min-h-0 flex-1 lg:w-[60%]">
        <CampusMap
          issues={issues}
          pin={pin}
          onPick={pickPoint}
          onIssueClick={(i) => { if (!jobId && !shot) setSelected(i) }}
          dark={dark}
          flyTo={flyTo}
        />

        {/* Top Building Filter Chips Floating Bar */}
        <div className="absolute inset-x-0 top-0 z-[500] safe-top pointer-events-none">
          <div className="pointer-events-auto flex flex-col gap-2 p-3">
            <div className="flex gap-2 overflow-x-auto [scrollbar-width:none]">
              <button
                onClick={() => setPicker(true)}
                className="chip border-slate-900 bg-slate-900 text-white shadow-md transition-transform active:scale-95 dark:border-white/20 dark:bg-white dark:text-slate-900"
              >
                <List size={14} /> All buildings
              </button>
              {chips.map((b) => (
                <button
                  key={b.name}
                  onClick={() => b.lat && pickBuilding(b)}
                  className={`chip shadow-sm transition-all active:scale-95 ${
                    building === b.name
                      ? 'border-accent bg-gradient-to-r from-teal-600 to-emerald-600 text-white shadow-glow-accent'
                      : 'border-slate-200/90 bg-white/90 text-slate-800 backdrop-blur-md hover:bg-white dark:border-slate-800/90 dark:bg-slate-900/90 dark:text-slate-100 dark:hover:bg-slate-900'
                  }`}
                >
                  <Building2 size={14} /> {b.name}
                </button>
              ))}
            </div>

            {/* Floor Selection Chips */}
            {building && !shot && (
              <div className="flex gap-1.5 slide-in">
                <span className="hidden sm:inline-flex items-center text-xs font-semibold px-2 py-1 rounded-lg bg-black/60 text-white backdrop-blur-md">
                  Floor:
                </span>
                {FLOORS.map((f) => (
                  <button
                    key={f}
                    onClick={() => setFloor(f)}
                    className={`chip !min-h-[30px] text-xs font-semibold shadow-sm transition-all active:scale-95 ${
                      floor === f
                        ? 'border-accent bg-accent text-white shadow-sm'
                        : 'border-slate-200/90 bg-white/90 text-slate-800 backdrop-blur-md hover:bg-white dark:border-slate-800/90 dark:bg-slate-900/90 dark:text-slate-100'
                    }`}
                  >
                    {f === 'Ground' ? 'Ground' : `Floor ${f}`}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Floating Quick Map Controls (Locate & Center) */}
        <div className="absolute right-3 top-20 z-[500] flex flex-col gap-2">
          <button
            onClick={locateMe}
            disabled={locating}
            title="Locate my position"
            className="flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200/90 bg-white/90 text-slate-700 shadow-lg backdrop-blur-md transition-all hover:bg-white active:scale-95 dark:border-slate-800 dark:bg-slate-900/90 dark:text-slate-200"
          >
            <Crosshair size={18} className={locating ? 'animate-spin text-accent' : ''} />
          </button>
          <button
            onClick={centerCampus}
            title="Reset to campus center"
            className="flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200/90 bg-white/90 text-slate-700 shadow-lg backdrop-blur-md transition-all hover:bg-white active:scale-95 dark:border-slate-800 dark:bg-slate-900/90 dark:text-slate-200"
          >
            <Navigation size={17} />
          </button>
        </div>

        {/* Bottom Report CTA Button (When no panel is active) */}
        {!shot && !jobId && (
          <div className="absolute inset-x-0 bottom-4 z-[500] flex flex-col items-center gap-2 px-4 pointer-events-none">
            {error && (
              <div className="pointer-events-auto rounded-2xl bg-slate-900/95 px-4 py-2.5 text-xs font-medium text-white shadow-xl backdrop-blur-md border border-white/10 animate-fade-in">
                {error}
              </div>
            )}
            {!pin && !error && (
              <div className="pointer-events-auto flex items-center gap-1.5 rounded-full border border-slate-200/80 bg-white/90 px-3.5 py-1.5 text-xs font-semibold text-slate-700 shadow-lg backdrop-blur-md dark:border-slate-800 dark:bg-slate-900/90 dark:text-slate-300">
                <MapPin size={14} className="text-accent animate-bounce" /> Tap anywhere on campus to drop a pin
              </div>
            )}
            <button
              onClick={openCamera}
              className="pointer-events-auto btn-primary h-14 rounded-full px-8 text-base font-bold shadow-2xl shadow-teal-600/40 hover:scale-105 active:scale-95 transition-transform flex items-center gap-2.5"
            >
              <Camera size={20} />
              <span>{building ? `Report at ${building}` : 'Report Issue'}</span>
            </button>
          </div>
        )}
      </div>

      {/* Floating Bottom Sheet (Mobile) & Side Panel (Desktop) */}
      {panel && (
        <aside className="sheet-enter safe-bottom z-[600] max-h-[75%] overflow-y-auto rounded-t-3xl border-t border-slate-200/80 bg-white/95 p-5 shadow-2xl backdrop-blur-2xl dark:border-slate-800/80 dark:bg-slate-900/95 lg:max-h-none lg:w-[40%] lg:rounded-none lg:border-l lg:border-t-0 lg:p-6 lg:shadow-none">
          {/* Mobile Drag Pill */}
          <button
            className="mx-auto mb-3 flex h-5 w-16 items-center justify-center rounded-full text-slate-400 hover:text-slate-600 lg:hidden"
            onClick={() => setExpanded(!expanded)}
            aria-label="Toggle panel"
          >
            <div className="h-1.5 w-10 rounded-full bg-slate-300 dark:bg-slate-700" />
          </button>

          {expanded && (
            selected && !shot && !jobId ? (
              /* Selected issue: summary, lifecycle and the action that fits its status */
              <IssuePanel key={selected.id} issue={selected} onClose={() => setSelected(null)} onReport={reportExisting} onChanged={load} />
            ) : jobId ? (
              /* Live Agent Trace running */
              <div className="space-y-4">
                <AgentTrace jobId={jobId} onRetake={retake} onDone={() => load()} />
                <button className="btn-ghost w-full" onClick={reset}>Done</button>
              </div>
            ) : (
              /* Photo Submission Step */
              <div className="space-y-4">
                <div className="flex items-start gap-3 rounded-2xl border border-slate-200/80 bg-slate-50/70 p-3.5 dark:border-slate-800/80 dark:bg-slate-950/50">
                  <img src={shot.url} alt="Your captured photo" className="h-20 w-20 shrink-0 rounded-xl object-cover ring-1 ring-black/10" />
                  <div className="min-w-0 flex-1">
                    <p className="font-bold text-sm text-slate-900 dark:text-white truncate">
                      {building ? `${building}` : 'Custom pin location'}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {floor === 'Ground' ? 'Ground floor' : floor ? `Floor ${floor}` : 'Location verified'}
                    </p>
                    <button
                      className="mt-2 text-xs font-semibold text-accent hover:underline inline-flex items-center gap-1"
                      onClick={retake}
                    >
                      Retake photo
                    </button>
                  </div>
                </div>

                {/* Quick Issue Category Chips */}
                <div className="space-y-1.5">
                  <label className="label">Quick issue tags</label>
                  <div className="flex flex-wrap gap-1.5">
                    {QUICK_TAGS.map((tag) => (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => addTag(tag)}
                        className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700 transition-all hover:bg-teal-50 hover:border-teal-300 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-teal-950/40 active:scale-95"
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Optional Note Field */}
                <div>
                  <label className="label" htmlFor="note">Add details (optional)</label>
                  <textarea
                    id="note"
                    className="input text-sm"
                    rows={2}
                    maxLength={300}
                    placeholder="e.g. Water leaking near washroom entrance, 2nd floor"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                  <p className="mt-1 text-right text-[11px] muted">{note.length}/300</p>
                </div>

                {error && <p className="rounded-xl bg-red-500/10 p-2.5 text-xs font-medium text-red-600 dark:text-red-400">{error}</p>}

                <div className="space-y-2">
                  <button className="btn-primary w-full shadow-glow-accent" onClick={submit} disabled={busy}>
                    <Send size={16} /> {busy ? 'Streaming to Gemma AI...' : 'Submit Report'}
                  </button>
                  <button className="btn-ghost w-full text-xs" onClick={reset}>
                    Cancel
                  </button>
                </div>
              </div>
            )
          )}
        </aside>
      )}

      {/* Full Building Directory Picker Modal */}
      {picker && <BuildingPicker onPick={pickBuilding} onClose={() => setPicker(false)} />}

      {/* In-App Camera HUD Modal */}
      {camera && (
        <CameraCapture
          onClose={() => setCamera(false)}
          onCapture={(s) => {
            setShot(s)
            setCamera(false)
            setSelected(null)
          }}
        />
      )}
    </div>
  )
}

