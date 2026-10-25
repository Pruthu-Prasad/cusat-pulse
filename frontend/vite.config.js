import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The backend is reached through this proxy, so the app only ever calls relative /api and /uploads paths.
const proxy = {
  '/api': 'http://localhost:8000',
  '/uploads': 'http://localhost:8000',
}
// Cloudflare quick-tunnel hostnames (phones / judges).
const allowedHosts = ['.trycloudflare.com']

export default defineConfig({
  plugins: [react()],
  // npm run dev: live-reloading development server
  server: { host: true, allowedHosts, proxy },
  // npm run demo (build + preview): optimised bundle for the presentation; loads fast over the tunnel
  preview: { host: true, port: 5173, strictPort: true, allowedHosts, proxy },
})
