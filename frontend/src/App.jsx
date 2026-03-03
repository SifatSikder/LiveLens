import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import InspectionView from './components/InspectionView'
import Dashboard from './components/Dashboard'

/**
 * LiveLens App — v0.3
 * Routes:
 *   /            → InspectionView (live audio+video inspection)
 *   /dashboard   → Dashboard (session history + report downloads)
 *   *            → redirect to /
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<InspectionView />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}