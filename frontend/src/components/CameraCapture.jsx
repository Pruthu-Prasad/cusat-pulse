import { useEffect, useRef, useState } from 'react'
import { Camera, RotateCcw, Check, X, ShieldCheck, Sparkles, Crosshair } from 'lucide-react'
import { api } from '../api'

const MAX_WIDTH = 1280
const QUALITY = 0.7

// In-app camera only: there is deliberately no file picker.
export default function CameraCapture({ onCapture, onClose, title = 'Capture Campus Issue' }) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [error, setError] = useState('')
  const [shot, setShot] = useState(null)
  const [busy, setBusy] = useState(false)
  const [flashing, setFlashing] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError('This browser cannot open the camera. Open the app over https (the tunnel link) and try again.')
        return
      }
      try {
        const s = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 1920 } },
          audio: false,
        })
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = s
        if (videoRef.current) videoRef.current.srcObject = s
      } catch {
        setError('Camera permission was denied. Allow camera access in your browser settings, then try again.')
      }
    }
    start()
    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  async function snap() {
    const v = videoRef.current
    if (!v || !v.videoWidth || busy) return
    setBusy(true)

    // Trigger haptic vibration on mobile
    try { navigator.vibrate?.([30, 45]) } catch { /* ignore */ }

    // Shutter flash animation
    setFlashing(true)
    setTimeout(() => setFlashing(false), 300)

    try {
      const scale = Math.min(1, MAX_WIDTH / v.videoWidth)
      const canvas = document.createElement('canvas')
      canvas.width = Math.round(v.videoWidth * scale)
      canvas.height = Math.round(v.videoHeight * scale)
      canvas.getContext('2d').drawImage(v, 0, 0, canvas.width, canvas.height)
      const blob = await new Promise((r) => canvas.toBlob(r, 'image/jpeg', QUALITY))

      // The 2-minute one-time token is minted while the camera is live.
      const { token } = await api('/api/capture-token', { method: 'POST' })
      setShot({ blob, token, url: URL.createObjectURL(blob) })
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[1000] flex flex-col bg-slate-950 text-white select-none">
      {/* Top Bar with Security Badge */}
      <div className="safe-top relative z-20 flex items-center justify-between border-b border-white/10 bg-slate-950/80 px-4 py-3 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm tracking-tight">{title}</span>
          <span className="hidden sm:inline-flex items-center gap-1 rounded-full border border-teal-500/30 bg-teal-500/10 px-2 py-0.5 text-[10px] font-semibold text-teal-300">
            <ShieldCheck size={12} /> Signed Live Token
          </span>
        </div>
        <button
          className="btn h-9 w-9 rounded-full bg-white/10 p-0 text-white transition-colors hover:bg-white/20 active:scale-95"
          onClick={onClose}
          aria-label="Close camera"
        >
          <X size={18} />
        </button>
      </div>

      {/* Main Viewfinder Area */}
      <div className="relative flex-1 overflow-hidden bg-black flex items-center justify-center">
        {/* Shutter flash overlay */}
        {flashing && <div className="absolute inset-0 z-50 bg-white pointer-events-none shutter-flash" />}

        {error ? (
          <div className="flex h-full items-center justify-center p-6 text-center text-slate-300">
            <div className="max-w-sm rounded-2xl border border-red-500/30 bg-red-950/40 p-4">
              <p className="text-sm font-medium">{error}</p>
            </div>
          </div>
        ) : shot ? (
          <div className="relative h-full w-full flex items-center justify-center">
            <img src={shot.url} alt="Captured preview" className="h-full w-full object-contain" />
            <div className="absolute top-4 left-4 z-10 flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-black/70 px-3 py-1 text-xs font-semibold text-emerald-400 backdrop-blur-md">
              <ShieldCheck size={14} /> Capture Authenticated
            </div>
          </div>
        ) : (
          <div className="relative h-full w-full flex items-center justify-center">
            <video ref={videoRef} autoPlay playsInline muted className="h-full w-full object-cover" />

            {/* Anti-spoof scanline sweep */}
            <div className="camera-scanline" />

            {/* Viewfinder HUD Overlays */}
            <div className="pointer-events-none absolute inset-8 sm:inset-16 flex flex-col justify-between">
              {/* Top Corners */}
              <div className="flex justify-between">
                <div className="h-8 w-8 border-l-2 border-t-2 border-teal-400/80 shadow-[0_0_8px_rgba(45,212,191,0.5)]" />
                <div className="h-8 w-8 border-r-2 border-t-2 border-teal-400/80 shadow-[0_0_8px_rgba(45,212,191,0.5)]" />
              </div>

              {/* Center Crosshair & Level Meter */}
              <div className="flex items-center justify-center">
                <div className="relative flex items-center justify-center">
                  <div className="h-8 w-8 rounded-full border border-white/20" />
                  <Crosshair size={18} className="absolute text-teal-400/80" />
                  <div className="absolute -left-12 h-px w-8 bg-teal-400/40" />
                  <div className="absolute -right-12 h-px w-8 bg-teal-400/40" />
                </div>
              </div>

              {/* Bottom Corners */}
              <div className="flex justify-between">
                <div className="h-8 w-8 border-b-2 border-l-2 border-teal-400/80 shadow-[0_0_8px_rgba(45,212,191,0.5)]" />
                <div className="h-8 w-8 border-b-2 border-r-2 border-teal-400/80 shadow-[0_0_8px_rgba(45,212,191,0.5)]" />
              </div>
            </div>

            {/* HUD Status Text */}
            <div className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-black/60 px-3 py-1 font-mono text-[10px] tracking-wider text-teal-300 backdrop-blur-md">
              AI VISION AUDIT READY
            </div>
          </div>
        )}
      </div>

      {/* Camera Controls Bottom Bar */}
      <div className="safe-bottom relative z-20 flex items-center justify-center gap-6 border-t border-white/10 bg-slate-950/80 p-5 backdrop-blur-md">
        {shot ? (
          <div className="flex w-full max-w-sm items-center justify-center gap-4">
            <button
              className="btn flex-1 bg-white/10 px-5 text-sm font-semibold text-white transition-all hover:bg-white/20 active:scale-95"
              onClick={() => setShot(null)}
            >
              <RotateCcw size={16} /> Retake
            </button>
            <button
              className="btn-primary flex-1 px-5 text-sm font-semibold shadow-glow-emerald active:scale-95"
              onClick={() => onCapture(shot)}
            >
              <Check size={16} /> Use Photo
            </button>
          </div>
        ) : (
          !error && (
            <div className="relative flex items-center justify-center">
              {/* Outer pulse ring for shutter */}
              <div className="absolute h-24 w-24 rounded-full border border-teal-500/30 animate-pulse pointer-events-none" />
              <button
                onClick={snap}
                disabled={busy}
                aria-label="Take photo"
                className="group relative flex h-20 w-20 items-center justify-center rounded-full border-4 border-white bg-white/20 shadow-2xl transition-all duration-150 active:scale-90 hover:scale-105 disabled:opacity-50"
              >
                <div className="h-14 w-14 rounded-full bg-white transition-transform group-active:scale-90 shadow-inner flex items-center justify-center">
                  <Camera size={26} className="text-slate-900" />
                </div>
              </button>
            </div>
          )
        )}
      </div>
    </div>
  )
}

