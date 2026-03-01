import { useState, useRef, useEffect } from 'react'
import { Camera, Activity, FileText, Wifi, WifiOff, Mic, MicOff, Send, Video, VideoOff, AlertTriangle } from 'lucide-react'
import { useInspection } from './hooks/useInspection'

/**
 * LiveLens App — Task 0.2: Working bidi-streaming with audio + video.
 */
export default function App() {
  const {
    connected,
    inspecting,
    events,
    findings,
    transcript,
    sessionError,
    connect,
    disconnect,
    reconnect,
    sendText,
    startInspection,
    stopInspection,
  } = useInspection()

  const [textInput, setTextInput] = useState('')
  const [cameraActive, setCameraActive] = useState(false)
  const videoRef = useRef(null)
  const transcriptEndRef = useRef(null)

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  const handleStartInspection = async () => {
    await startInspection(videoRef.current)
    setCameraActive(true)
  }

  const handleStopInspection = () => {
    stopInspection()
    setCameraActive(false)
  }

  const handleSendText = (e) => {
    e.preventDefault()
    if (textInput.trim()) {
      sendText(textInput.trim())
      setTextInput('')
    }
  }

  const severityColor = (s) => {
    const colors = {
      1: 'bg-green-500/20 text-green-400 border-green-500/40',
      2: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40',
      3: 'bg-orange-500/20 text-orange-400 border-orange-500/40',
      4: 'bg-red-500/20 text-red-400 border-red-500/40',
      5: 'bg-red-700/30 text-red-300 border-red-600/50',
    }
    return colors[s] || colors[1]
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-4 py-2.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <Camera className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-lg font-semibold text-white">LiveLens</h1>
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">v0.2</span>
        </div>
        <div className="flex items-center gap-3 text-sm">
          {connected ? (
            <span className="flex items-center gap-1.5 text-green-400">
              <Wifi className="w-4 h-4" />
              Live
            </span>
          ) : (
            <button
              onClick={connect}
              className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors"
            >
              <WifiOff className="w-4 h-4" />
              Connect
            </button>
          )}
        </div>
      </header>

      {/* Error Banner */}
      {sessionError && (
        <div className="bg-red-900/80 border-b border-red-700 px-4 py-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2 text-red-200 text-sm">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span>
              <span className="font-semibold text-red-100">Session ended: </span>
              {sessionError.message}
            </span>
          </div>
          <button
            onClick={() => { reconnect(); }}
            className="ml-4 px-3 py-1 rounded bg-red-700 hover:bg-red-600 text-white text-xs font-medium transition-colors flex-shrink-0"
          >
            Start New Session
          </button>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 flex overflow-hidden">
        {/* Left: Camera + Controls */}
        <div className="flex-1 flex flex-col p-4 gap-4">
          {/* Camera Feed */}
          <div className="flex-1 bg-gray-900 rounded-xl border border-gray-800 overflow-hidden relative">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`w-full h-full object-cover ${cameraActive ? '' : 'hidden'}`}
            />
            {!cameraActive && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <Camera className="w-16 h-16 text-gray-700 mx-auto mb-4" />
                  <p className="text-gray-500 text-sm">Camera inactive</p>
                  <p className="text-gray-600 text-xs mt-1">Start inspection to activate camera + mic</p>
                </div>
              </div>
            )}
            {/* Status overlay */}
            {inspecting && (
              <div className="absolute top-3 left-3 flex items-center gap-2 bg-red-600/80 backdrop-blur px-3 py-1.5 rounded-full">
                <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
                <span className="text-white text-xs font-medium">INSPECTING</span>
              </div>
            )}
          </div>

          {/* Controls */}
          <div className="flex gap-3 items-center">
            <button
              onClick={inspecting ? handleStopInspection : handleStartInspection}
              className={`px-5 py-2.5 rounded-lg font-medium flex items-center gap-2 transition-colors text-sm ${
                inspecting
                  ? 'bg-red-600 hover:bg-red-700 text-white'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {inspecting ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              {inspecting ? 'End Inspection' : 'Start Inspection'}
            </button>

            {/* Text input for testing without mic */}
            <form onSubmit={handleSendText} className="flex-1 flex gap-2">
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder={connected ? "Type a message (or use voice)..." : "Connect first..."}
                disabled={!connected}
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!connected || !textInput.trim()}
                className="p-2.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-400 hover:text-white hover:border-gray-600 transition-colors disabled:opacity-30"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>

        {/* Right Sidebar: Transcript + Findings */}
        <aside className="w-96 bg-gray-900 border-l border-gray-800 flex flex-col">
          {/* Transcript */}
          <div className="flex-1 overflow-y-auto p-4">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Conversation
            </h2>
            {transcript.length === 0 ? (
              <p className="text-gray-600 text-sm text-center mt-8">
                Start an inspection to begin the conversation.
              </p>
            ) : (
              <div className="space-y-3">
                {transcript.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[85%] px-3 py-2 rounded-lg text-sm ${
                        msg.role === 'user'
                          ? 'bg-blue-600/30 text-blue-100'
                          : 'bg-gray-800 text-gray-200'
                      } ${msg.isTranscription ? 'italic opacity-80' : ''}`}
                    >
                      {msg.text}
                    </div>
                  </div>
                ))}
                <div ref={transcriptEndRef} />
              </div>
            )}
          </div>

          {/* Findings */}
          <div className="border-t border-gray-800 p-4 max-h-64 overflow-y-auto">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Findings ({findings.length})
            </h2>
            {findings.length === 0 ? (
              <p className="text-gray-600 text-xs text-center">No findings yet.</p>
            ) : (
              <div className="space-y-2">
                {findings.map((f, i) => (
                  <div
                    key={i}
                    className={`p-2.5 rounded-lg border text-xs ${severityColor(f.severity)}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold">{f.id}</span>
                      <span className="font-mono">Sev {f.severity}/5</span>
                    </div>
                    <p className="opacity-90">{f.finding_type || f.type}: {f.description}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Event log (collapsed) */}
          <details className="border-t border-gray-800">
            <summary className="px-4 py-2 text-xs text-gray-500 cursor-pointer hover:text-gray-400">
              Raw Events ({events.length})
            </summary>
            <div className="max-h-40 overflow-y-auto px-4 pb-2">
              {events.slice(-20).map((evt, i) => (
                <pre key={i} className="text-[10px] text-gray-600 font-mono truncate">
                  {JSON.stringify(evt).substring(0, 120)}...
                </pre>
              ))}
            </div>
          </details>
        </aside>
      </main>
    </div>
  )
}
