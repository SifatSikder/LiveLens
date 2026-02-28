import { useState } from 'react'
import { Camera, Activity, FileText, Wifi, WifiOff } from 'lucide-react'

/**
 * LiveLens App — Initial shell.
 * Full UI built in Phase 3. This is the skeleton for Task 0.2 streaming testing.
 */
export default function App() {
  const [connected, setConnected] = useState(false)
  const [inspecting, setInspecting] = useState(false)

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-livelens-500 rounded-lg flex items-center justify-center">
            <Camera className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-lg font-semibold text-white">LiveLens</h1>
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">v0.1</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          {connected ? (
            <span className="flex items-center gap-1.5 text-green-400">
              <Wifi className="w-4 h-4" />
              Connected
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-gray-500">
              <WifiOff className="w-4 h-4" />
              Disconnected
            </span>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex">
        {/* Camera Feed Area */}
        <div className="flex-1 flex flex-col items-center justify-center bg-gray-950 p-8">
          <div className="w-full max-w-3xl aspect-video bg-gray-900 rounded-xl border border-gray-800 flex items-center justify-center">
            {/* Camera feed will be rendered here in Phase 3 */}
            <div className="text-center">
              <Camera className="w-16 h-16 text-gray-700 mx-auto mb-4" />
              <p className="text-gray-500 text-sm">Camera feed will appear here</p>
              <p className="text-gray-600 text-xs mt-1">Phase 0 — Scaffolding complete</p>
            </div>
          </div>

          {/* Controls */}
          <div className="mt-6 flex gap-4">
            <button
              onClick={() => setInspecting(!inspecting)}
              className={`px-6 py-3 rounded-lg font-medium flex items-center gap-2 transition-colors ${
                inspecting
                  ? 'bg-red-600 hover:bg-red-700 text-white'
                  : 'bg-livelens-600 hover:bg-livelens-700 text-white'
              }`}
            >
              <Activity className="w-5 h-5" />
              {inspecting ? 'End Inspection' : 'Start Inspection'}
            </button>
            <button
              className="px-6 py-3 rounded-lg font-medium flex items-center gap-2 bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
            >
              <FileText className="w-5 h-5" />
              Generate Report
            </button>
          </div>
        </div>

        {/* Findings Sidebar — Phase 3 */}
        <aside className="w-80 bg-gray-900 border-l border-gray-800 p-4 hidden lg:block">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
            Findings
          </h2>
          <div className="text-gray-600 text-sm text-center mt-12">
            <p>No findings yet.</p>
            <p className="text-xs mt-1">Start an inspection to begin.</p>
          </div>
        </aside>
      </main>
    </div>
  )
}
