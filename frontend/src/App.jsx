import { lazy, Suspense, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { api, session } from './api'
import Login from './pages/Login'
import StudentShell from './components/layout/StudentShell'
import StudentMap from './pages/StudentMap'
import MyReports from './pages/MyReports'
import Me from './pages/Me'

// Admin code is lazy so students on mobile data only download the student view.
const AdminApp = lazy(() => import('./pages/admin/AdminApp'))

export default function App() {
  const [user, setUser] = useState(session.user)
  const staff = user && (user.role === 'staff' || user.role === 'admin')
  // End the session on the server first (so the token stops working), then forget it here.
  // If the server can't be reached, still sign out locally.
  const logout = async () => {
    try { await api('/api/auth/logout', { method: 'POST' }) } catch { /* offline or already expired */ }
    session.clear()
    setUser(null)
  }

  if (!user) return <Login onLogin={setUser} />

  return (
    <Suspense fallback={<div className="p-8 muted">Loading...</div>}>
      <Routes>
        {staff && <Route path="/admin/*" element={<AdminApp user={user} onLogout={logout} />} />}
        <Route element={<StudentShell user={user} />}>
          <Route path="/" element={staff ? <Navigate to="/admin" replace /> : <StudentMap />} />
          <Route path="/map" element={<StudentMap />} />
          <Route path="/reports" element={<MyReports />} />
          <Route path="/me" element={<Me user={user} onLogout={logout} />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
