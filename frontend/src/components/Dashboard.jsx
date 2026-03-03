import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Camera, LayoutDashboard, Mic, ChevronDown, ChevronUp,
  Loader2, AlertCircle, ClipboardList,
} from 'lucide-react';
import { listInspections, getSessionFindings } from '../utils/api';
import ReportViewer from './ReportViewer';

const SEV_LABEL = { 1: 'Low', 2: 'Med', 3: 'Mod', 4: 'High', 5: 'Crit' };

function StatusBadge({ status }) {
  const styles = {
    active:    'bg-green-500/20 text-green-400 border-green-500/30',
    completed: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    error:     'bg-red-500/20 text-red-400 border-red-500/30',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${styles[status] ?? styles.completed}`}>
      {status ?? 'unknown'}
    </span>
  );
}

function SessionRow({ session }) {
  const [expanded, setExpanded] = useState(false);
  const [findings, setFindings] = useState(null);
  const [loadingF, setLoadingF] = useState(false);

  const toggle = async () => {
    if (!expanded && findings === null) {
      setLoadingF(true);
      try {
        const data = await getSessionFindings(session.session_id);
        setFindings(data?.findings ?? []);
      } catch { setFindings([]); }
      finally { setLoadingF(false); }
    }
    setExpanded((p) => !p);
  };

  const startedAt = session.started_at
    ? new Date(session.started_at).toLocaleString()
    : '—';

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 overflow-hidden">
      <button onClick={toggle} className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-800/50 transition-colors text-left">
        <div className="flex items-center gap-3 min-w-0">
          <ClipboardList className="w-4 h-4 text-gray-500 flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-sm text-white font-medium truncate">{session.session_id}</p>
            <p className="text-[11px] text-gray-500">{startedAt}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0 ml-3">
          <StatusBadge status={session.status} />
          <span className="text-xs text-gray-400">{session.finding_count ?? 0} findings</span>
          {expanded ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-gray-800 px-4 py-3 space-y-3">
          <ReportViewer sessionId={session.session_id} />
          {loadingF && (
            <div className="flex items-center gap-2 text-gray-500 text-xs">
              <Loader2 className="w-3 h-3 animate-spin" /> Loading findings…
            </div>
          )}
          {findings && findings.length === 0 && (
            <p className="text-gray-600 text-xs">No findings recorded.</p>
          )}
          {findings && findings.length > 0 && (
            <div className="space-y-2">
              {findings.map((f, i) => {
                const sev = f.severity ?? 1;
                return (
                  <div key={f.id ?? i} className={`p-2.5 rounded-lg border text-xs severity-${sev}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold truncate max-w-[70%]">
                        {f.finding_type || f.type || 'Finding'}
                      </span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border severity-${sev}`}>
                        {SEV_LABEL[sev] ?? `Sev ${sev}`}
                      </span>
                    </div>
                    <p className="opacity-90 leading-snug line-clamp-2">{f.description}</p>
                    {f.location_note && <p className="opacity-60 mt-1 truncate">📍 {f.location_note}</p>}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    listInspections()
      .then((data) => { setSessions(data?.sessions ?? []); setLoading(false); })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, []);

  const totalFindings = sessions.reduce((s, x) => s + (x.finding_count ?? 0), 0);
  const completed = sessions.filter((x) => x.status === 'completed').length;

  return (
    <div className="min-h-[100dvh] lg:h-screen flex flex-col overflow-hidden">
      <header className="bg-gray-900 border-b border-gray-800 px-4 py-2.5 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <Camera className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-lg font-semibold text-white">LiveLens</h1>
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded hidden sm:inline">v0.3</span>
        </div>
        <nav className="flex items-center gap-3 sm:gap-4 text-sm">
          <Link to="/" className="text-gray-400 hover:text-white transition-colors duration-200 flex items-center gap-1.5">
            <Mic className="w-4 h-4" /> <span className="hidden sm:inline">Inspection</span>
          </Link>
          <span className="text-blue-400 font-medium flex items-center gap-1.5">
            <LayoutDashboard className="w-4 h-4" /> <span className="hidden sm:inline">Dashboard</span>
          </span>
        </nav>
      </header>
      <main className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          {[
            { label: 'Total Sessions', value: sessions.length },
            { label: 'Completed', value: completed },
            { label: 'Total Findings', value: totalFindings },
          ].map(({ label, value }) => (
            <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
              <p className="text-2xl font-bold text-white">{value}</p>
              <p className="text-xs text-gray-500 mt-1">{label}</p>
            </div>
          ))}
        </div>
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Inspection History</h2>
        {loading && (
          <div className="flex items-center justify-center gap-2 text-gray-500 py-12">
            <Loader2 className="w-5 h-5 animate-spin" /> Loading sessions…
          </div>
        )}
        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm py-8">
            <AlertCircle className="w-4 h-4" /> {error}
          </div>
        )}
        {!loading && !error && sessions.length === 0 && (
          <p className="text-gray-600 text-sm text-center py-12">
            No inspection sessions yet.{' '}
            <Link to="/" className="text-blue-400 hover:text-blue-300 underline">Start one →</Link>
          </p>
        )}
        <div className="space-y-3">
          {sessions.map((s) => <SessionRow key={s.session_id} session={s} />)}
        </div>
      </main>
    </div>
  );
}
