import { useEffect, useState } from 'react'

export function useDarkMode(defaultDark) {
  const [dark, setDark] = useState(() => {
    try {
      const saved = localStorage.getItem('cp_dark')
      if (saved !== null) return saved === '1'
    } catch { /* ignore */ }
    return defaultDark ?? window.matchMedia('(prefers-color-scheme: dark)').matches
  })
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])
  const toggle = () => setDark((d) => {
    try { localStorage.setItem('cp_dark', d ? '0' : '1') } catch { /* ignore */ }
    return !d
  })
  return [dark, toggle]
}
