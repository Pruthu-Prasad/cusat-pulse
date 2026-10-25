import { useEffect, useState } from 'react'
import { ShieldCheck, ShieldAlert, Loader2, Hash } from 'lucide-react'
import { api } from '../../api'
import { CopyButton, Skeleton } from '../../components/Bits'

export default function Ledger({ version }) {
  const [data, setData] = useState(null)
  const [filter, setFilter] = useState('')
  const [check, setCheck] = useState(null)
  const [checking, setChecking] = useState(false)

  useEffect(() => {
    const q = filter.trim() ? `?issue_id=${encodeURIComponent(filter.trim().toUpperCase())}` : ''
    api(`/api/ledger${q}`).then(setData).catch(() => {})
  }, [version, filter])

  async function verify() {
    setChecking(true)
    try { setCheck(await api('/api/ledger/verify')) } finally { setChecking(false) }
  }

  if (!data) return <div className="p-8"><Skeleton rows={6} /></div>
  return (
    <div className="flex h-full flex-col gap-5 overflow-hidden p-5 lg:p-8">
      {/* ── Page Header ── */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Ledger</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {data.total} blocks · Tamper-proof chain of custody
        </p>
      </div>

      {/* ── Toolbar ── */}
      <div className="flex flex-wrap items-center gap-3">
        <button className="btn-primary" onClick={verify} disabled={checking}>
          {checking ? <Loader2 size={18} className="animate-spin" /> : <ShieldCheck size={18} />}
          Verify chain
        </button>

        {check && (check.intact ? (
          <span className="slide-in flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-500 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-emerald-600/20">
            <ShieldCheck size={18} /> Chain intact ({check.blocks} blocks)
          </span>
        ) : (
          <span className="slide-in flex items-center gap-2 rounded-xl bg-gradient-to-r from-red-600 to-rose-500 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-red-600/20">
            <ShieldAlert size={18} /> Broken at block #{check.broken_at}{check.issue_id && ` · ${check.issue_id}`} · {check.reason}
          </span>
        ))}

        <div className="relative ml-auto">
          <Hash size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className="input !pl-8 !py-2 !text-sm max-w-[200px] font-mono"
            placeholder="Filter: CL-0007"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
      </div>

      {/* ── Latest Hash ── */}
      {data.latest_hash && (
        <div className="card flex flex-wrap items-center gap-3 !p-4">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Latest Hash</span>
          <code className="min-w-0 flex-1 truncate rounded-lg bg-slate-100 px-2.5 py-1 font-mono text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
            {data.latest_hash}
          </code>
          <CopyButton text={data.latest_hash} />
        </div>
      )}

      {/* ── Block Table ── */}
      <div className="card min-h-0 flex-1 overflow-auto !p-0">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="sticky top-0 border-b border-slate-200/80 bg-slate-50 dark:border-slate-800 dark:bg-slate-900">
            <tr>
              {['#', 'Time', 'Event', 'Issue', 'Report', 'Actor', 'Hash'].map((h) => (
                <th key={h} className="px-4 py-3 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="font-mono text-xs">
            {data.blocks.map((b) => (
              <tr key={b.block_no}
                className={`border-t border-slate-100 transition-colors hover:bg-slate-50/80 dark:border-slate-800 dark:hover:bg-slate-800/40 ${
                  check && !check.intact && check.broken_at === b.block_no ? 'bg-red-50 dark:bg-red-500/15' : ''
                }`}
              >
                <td className="px-4 py-3 font-semibold text-slate-600 dark:text-slate-300">{b.block_no}</td>
                <td className="px-4 py-3 text-slate-400">{new Date(b.created_at).toLocaleTimeString()}</td>
                <td className="px-4 py-3 font-sans font-semibold text-slate-800 dark:text-slate-200">{b.event}</td>
                <td className="px-4 py-3">{b.issue_id || '—'}</td>
                <td className="px-4 py-3">{b.report_id || '—'}</td>
                <td className="px-4 py-3 text-slate-400">{b.actor}</td>
                <td className="px-4 py-3 text-slate-400">{b.block_hash.slice(0, 12)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-400 dark:text-slate-500">
        Every block carries the hash of the one before it — editing any old record breaks the chain.
      </p>
    </div>
  )
}
