import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Camera, Wifi, WifiOff, Mic, MicOff, Send, AlertTriangle,
  FileText, LayoutDashboard, Loader2, Download,
} from 'lucide-react';
import { useInspection } from '../hooks/useInspection';
import AudioIndicator from './AudioIndicator';
import CameraStream from './CameraStream';
import FindingsSidebar from './FindingsSidebar';

function MessageText({ text }) {
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  const parts = text.split(urlRegex);
  return (
    <>
      {parts.map((part, i) =>
        urlRegex.test(part) ? (
          <a key={i} href={part} target="_blank" rel="noopener noreferrer"
            className="text-blue-400 underline underline-offset-2 hover:text-blue-300 break-all transition-colors"
            onClick={(e) => e.stopPropagation()}>{part}</a>
        ) : <span key={i}>{part}</span>
      )}
    </>
  );
}

export default function InspectionView() {
  const {
    connected, inspecting, events, findings, transcript, searchResults,
    sessionError, reportUrl, generating, agentSpeaking, sessionId,
    connect, reconnect, sendText, startInspection, stopInspection, triggerReport,
  } = useInspection();

  const [textInput, setTextInput] = useState('');
  const [activeTab, setActiveTab] = useState('conversation');
  const [connecting, setConnecting] = useState(false);
  const videoRef = useRef(null);
  const transcriptEndRef = useRef(null);

  // Clear connecting state once WebSocket connects
  useEffect(() => {
    if (connected) setConnecting(false);
  }, [connected]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  const handleStartInspection = async () => { await startInspection(videoRef.current); };
  const handleStopInspection = () => { stopInspection(); };
  const handleSendText = (e) => {
    e.preventDefault();
    if (textInput.trim()) { sendText(textInput.trim()); setTextInput(''); }
  };
  const handleConnect = () => { setConnecting(true); connect(); };

  return (
    <div className="min-h-[100dvh] lg:h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-4 py-2.5 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <Camera className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-lg font-semibold text-white">LiveLens</h1>
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded hidden sm:inline">v0.3</span>
        </div>
        <nav className="flex items-center gap-3 sm:gap-4 text-sm">
          <span className="text-blue-400 font-medium flex items-center gap-1.5">
            <Mic className="w-4 h-4" />
            <span className="hidden sm:inline">Inspection</span>
          </span>
          <Link to="/dashboard" className="text-gray-400 hover:text-white transition-colors duration-200 flex items-center gap-1.5">
            <LayoutDashboard className="w-4 h-4" />
            <span className="hidden sm:inline">Dashboard</span>
          </Link>
          {connected ? (
            <span className="flex items-center gap-1.5 text-green-400">
              <Wifi className="w-4 h-4" /> <span className="hidden sm:inline">Live</span>
            </span>
          ) : (
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors duration-200 disabled:opacity-60"
            >
              {connecting
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <WifiOff className="w-4 h-4" />}
              <span className="hidden sm:inline">{connecting ? 'Connecting…' : 'Connect'}</span>
            </button>
          )}
        </nav>
      </header>

      {/* Error Banner */}
      {sessionError && (
        <div className="bg-red-900/80 border-b border-red-700 px-4 py-2.5 flex items-center justify-between animate-fadeIn transition-all duration-200 flex-shrink-0">
          <div className="flex items-center gap-2 text-red-200 text-sm">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span><span className="font-semibold text-red-100">Session ended: </span>{sessionError.message}</span>
          </div>
          <button onClick={reconnect} className="ml-4 px-3 py-1.5 min-h-[36px] rounded bg-red-700 hover:bg-red-600 text-white text-xs font-medium transition-colors duration-200 flex-shrink-0">
            New Session
          </button>
        </div>
      )}

      {/* Main */}
      <main className="flex-1 flex flex-col lg:flex-row overflow-auto lg:overflow-hidden">
        {/* Left: Camera + controls */}
        <div className="flex flex-col p-3 gap-3 lg:flex-1 lg:min-w-0">
          <div className="aspect-video w-full lg:flex-1 lg:aspect-auto lg:min-h-0">
            <CameraStream videoRef={videoRef} inspecting={inspecting} connected={connected} />
          </div>

          {/* Audio indicator row */}
          <div className="flex items-center gap-3 px-1">
            <AudioIndicator active={inspecting} speaking={agentSpeaking} />
            <span className="text-xs text-gray-500">
              {agentSpeaking ? 'Agent speaking…' : inspecting ? 'Listening…' : 'Idle'}
            </span>
            {sessionId && (
              <span className="ml-auto text-[10px] text-gray-600 font-mono truncate max-w-[180px]">
                {sessionId}
              </span>
            )}
          </div>

          {/* Report ready banner */}
          {reportUrl && (
            <a href={reportUrl} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-blue-600/20 border border-blue-500/40 text-blue-300 text-sm hover:bg-blue-600/30 transition-colors duration-200 animate-fadeIn">
              <Download className="w-4 h-4 flex-shrink-0" />
              <span className="font-medium">Inspection Report Ready</span>
              <span className="text-xs opacity-70 ml-auto">Click to download PDF</span>
            </a>
          )}

          {/* Controls */}
          <div className="flex flex-wrap gap-2 items-center">
            <button
              onClick={inspecting ? handleStopInspection : handleStartInspection}
              className={`min-h-[44px] px-4 py-2.5 rounded-lg font-medium flex items-center gap-2 transition-colors duration-200 text-sm ${
                inspecting ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {inspecting ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              {inspecting ? 'End Inspection' : 'Start Inspection'}
            </button>

            <button
              onClick={triggerReport}
              disabled={!connected || generating || !inspecting}
              className="min-h-[44px] px-4 py-2.5 rounded-lg font-medium flex items-center gap-2 transition-colors duration-200 text-sm bg-gray-700 hover:bg-gray-600 text-white disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
              {generating ? 'Generating…' : 'Generate Report'}
            </button>

            <form onSubmit={handleSendText} className="flex-1 flex gap-2 min-w-[200px]">
              <input type="text" value={textInput} onChange={(e) => setTextInput(e.target.value)}
                placeholder={connected ? 'Type a message…' : 'Connect first…'}
                disabled={!connected}
                className="flex-1 min-h-[44px] bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors duration-200 disabled:opacity-50"
              />
              <button type="submit" disabled={!connected || !textInput.trim()}
                className="min-h-[44px] p-2.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-400 hover:text-white hover:border-gray-600 transition-colors duration-200 disabled:opacity-30">
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>

        {/* Right sidebar */}
        <aside className="w-full lg:w-96 bg-gray-900 border-t lg:border-t-0 lg:border-l border-gray-800 flex flex-col max-h-[45vh] lg:max-h-none">
          {/* Tab bar */}
          <div className="flex border-b border-gray-800">
            {['conversation', 'findings'].map((tab) => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`flex-1 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors ${
                  activeTab === tab ? 'text-blue-400 border-b-2 border-blue-500' : 'text-gray-500 hover:text-gray-300'
                }`}>
                {tab === 'conversation' ? `Conversation (${transcript.length})` : `Findings (${findings.length})`}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto p-4">
            {activeTab === 'conversation' ? (
              transcript.length === 0 ? (
                <p className="text-gray-600 text-sm text-center mt-8">Start an inspection to begin.</p>
              ) : (
                <div className="space-y-3">
                  {transcript.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[85%] px-3 py-2 rounded-lg text-sm break-all ${
                        msg.role === 'user' ? 'bg-blue-600/30 text-blue-100' : 'bg-gray-800 text-gray-200'
                      } ${msg.isTranscription ? 'italic opacity-80' : ''}`}>
                        <MessageText text={msg.text} />
                      </div>
                    </div>
                  ))}
                  <div ref={transcriptEndRef} />
                </div>
              )
            ) : (
              <FindingsSidebar findings={findings} />
            )}
          </div>

          {/* Search results */}
          {searchResults.length > 0 && (
            <div className="border-t border-gray-800 p-4 max-h-48 overflow-y-auto">
              <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                References ({searchResults.length})
              </h2>
              <div className="space-y-2">
                {searchResults.map((r, i) => (
                  <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
                    className="block p-2.5 rounded-lg border border-blue-500/20 bg-blue-500/10 hover:bg-blue-500/20 transition-colors group">
                    <p className="text-xs font-medium text-blue-300 group-hover:text-blue-200 leading-snug mb-1">{r.title}</p>
                    <p className="text-[10px] text-blue-500/70 break-all">{r.url}</p>
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Raw events */}
          <details className="border-t border-gray-800">
            <summary className="px-4 py-2 text-xs text-gray-500 cursor-pointer hover:text-gray-400">
              Raw Events ({events.length})
            </summary>
            <div className="max-h-36 overflow-y-auto px-4 pb-2">
              {events.slice(-20).map((evt, i) => (
                <pre key={i} className="text-[10px] text-gray-600 font-mono truncate">
                  {JSON.stringify(evt).substring(0, 120)}…
                </pre>
              ))}
            </div>
          </details>
        </aside>
      </main>
    </div>
  );
}

