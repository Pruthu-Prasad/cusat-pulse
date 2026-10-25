import { useState } from 'react'
import { Activity, ArrowRight, ShieldCheck, Sparkles, UserCheck } from 'lucide-react'
import { api, session } from '../api'

export default function Login({ onLogin }) {
  const [step, setStep] = useState('email')
  const [form, setForm] = useState({ email: '', name: '', cusat_id: '', code: '' })
  const [needsProfile, setNeedsProfile] = useState(false)
  const [hint, setHint] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function requestCode(e) {
    e.preventDefault()
    setError(''); setBusy(true)
    try {
      const r = await api('/api/auth/request-otp', { body: { email: form.email, name: form.name || null, cusat_id: form.cusat_id || null } })
      setHint(r.demo_hint); setStep('code')
    } catch (err) {
      if (err.message.startsWith('First time')) setNeedsProfile(true)
      setError(err.message)
    } finally { setBusy(false) }
  }

  async function verify(e) {
    e.preventDefault()
    setError(''); setBusy(true)
    try {
      const r = await api('/api/auth/verify-otp', { body: { email: form.email, code: form.code } })
      session.save(r.token, r.user)
      onLogin(r.user)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  function setDemoAccount(email) {
    setForm((f) => ({ ...f, email }))
    setError('')
  }

  return (
    <div className="relative flex min-h-full items-center justify-center overflow-hidden bg-slate-900 p-4 antialiased">
      {/* Ambient background glow orbs */}
      <div className="pointer-events-none absolute -left-20 -top-20 h-96 w-96 rounded-full bg-teal-500/20 blur-[100px]" />
      <div className="pointer-events-none absolute -bottom-20 -right-20 h-96 w-96 rounded-full bg-emerald-500/20 blur-[100px]" />
      <div className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-[500px] w-[500px] rounded-full bg-indigo-500/10 blur-[120px]" />

      <div className="relative w-full max-w-sm rounded-3xl border border-white/20 bg-white/90 p-6 shadow-2xl backdrop-blur-2xl transition-all dark:border-slate-800/80 dark:bg-slate-950/80 sm:p-8">
        <div className="mb-6 flex items-center gap-3.5">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 to-emerald-600 text-white shadow-lg shadow-teal-500/30">
            <Activity size={26} className="animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold tracking-tight text-slate-900 dark:text-white">CUSAT-Pulse</h1>
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Campus issue tracker & audit network</p>
          </div>
        </div>

        {step === 'email' ? (
          <form onSubmit={requestCode} className="space-y-4">
            <div>
              <label className="label" htmlFor="email">CUSAT Email Address</label>
              <input
                id="email"
                className="input"
                type="email"
                required
                autoComplete="email"
                placeholder="you@cusat.ac.in"
                value={form.email}
                onChange={set('email')}
              />
            </div>

            {needsProfile && (
              <div className="space-y-3 rounded-2xl border border-teal-500/20 bg-teal-50/50 p-3.5 dark:bg-teal-950/20">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-teal-700 dark:text-teal-300">
                  <UserCheck size={14} /> First time signing in · Complete profile
                </div>
                <div>
                  <label className="label" htmlFor="name">Full Name</label>
                  <input id="name" className="input" required value={form.name} onChange={set('name')} placeholder="e.g. Rahul Nair" />
                </div>
                <div>
                  <label className="label" htmlFor="cid">CUSAT ID / Register Number</label>
                  <input id="cid" className="input font-mono" required value={form.cusat_id} onChange={set('cusat_id')} placeholder="e.g. 2102001" />
                </div>
              </div>
            )}

            {error && <p className="rounded-xl bg-red-500/10 p-2.5 text-xs font-medium text-red-600 dark:text-red-400">{error}</p>}

            <button className="btn-primary w-full shadow-md" disabled={busy}>
              {busy ? 'Requesting OTP...' : 'Send Access Code'} <ArrowRight size={16} />
            </button>

            {/* Quick Demo Credentials helper chips */}
            <div className="pt-2">
              <p className="mb-2 text-center text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Quick Demo Logins
              </p>
              <div className="flex flex-wrap justify-center gap-1.5">
                {[
                  { label: 'Student', email: 'demo1@cusat.ac.in' },
                  { label: 'Admin', email: 'estate@cusat.ac.in' },
                  { label: 'Staff', email: 'itsupport@cusat.ac.in' },
                ].map((demo) => (
                  <button
                    type="button"
                    key={demo.label}
                    onClick={() => setDemoAccount(demo.email)}
                    className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-all active:scale-95 ${
                      form.email === demo.email
                        ? 'border-accent bg-accent/15 text-accent font-semibold'
                        : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-slate-800'
                    }`}
                  >
                    {demo.label}
                  </button>
                ))}
              </div>
            </div>
          </form>
        ) : (
          <form onSubmit={verify} className="space-y-4">
            <div className="text-center">
              <p className="text-sm text-slate-600 dark:text-slate-300">
                Enter the 6-digit code sent to
              </p>
              <p className="font-semibold text-slate-900 dark:text-white">{form.email}</p>
            </div>

            <div>
              <input
                className="input text-center font-mono text-3xl font-bold tracking-[0.4em] text-accent"
                inputMode="numeric"
                maxLength={6}
                required
                autoFocus
                value={form.code}
                onChange={set('code')}
                placeholder="000000"
              />
            </div>

            {hint && (
              <div className="flex items-center justify-center gap-1.5 rounded-xl bg-amber-500/10 p-2 text-xs font-medium text-amber-800 dark:text-amber-300">
                <Sparkles size={13} /> Demo account code is <span className="font-mono font-bold tracking-wider">{hint}</span>
              </div>
            )}

            {error && <p className="rounded-xl bg-red-500/10 p-2.5 text-xs font-medium text-red-600 dark:text-red-400">{error}</p>}

            <button className="btn-primary w-full" disabled={busy}>
              {busy ? 'Verifying...' : 'Sign in to CUSAT-Pulse'}
            </button>
            <button
              type="button"
              className="btn-ghost w-full text-xs"
              onClick={() => { setStep('email'); setError('') }}
            >
              Use another email address
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

