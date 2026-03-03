import { useState, useEffect } from 'react';
import { FileText, Download, Loader2, AlertCircle } from 'lucide-react';
import { getReportPdfUrl } from '../utils/api';

/**
 * ReportViewer — fetches and displays the PDF download link for a session.
 * Props:
 *   sessionId (string) — the inspection session ID
 */
export default function ReportViewer({ sessionId }) {
  const [pdfData, setPdfData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!sessionId) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getReportPdfUrl(sessionId)
      .then((data) => { if (!cancelled) { setPdfData(data); setLoading(false); } })
      .catch((err) => { if (!cancelled) { setError(err.message); setLoading(false); } });
    return () => { cancelled = true; };
  }, [sessionId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-gray-500 text-xs">
        <Loader2 className="w-3 h-3 animate-spin" /> Checking for report…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 text-red-400 text-xs">
        <AlertCircle className="w-3 h-3" /> {error}
      </div>
    );
  }

  if (!pdfData?.pdf_url) {
    return (
      <div className="flex items-center gap-2 text-gray-600 text-xs">
        <FileText className="w-3 h-3" /> No report generated yet
      </div>
    );
  }

  return (
    <a
      href={pdfData.pdf_url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-600/20 border border-blue-500/40 text-blue-300 text-xs hover:bg-blue-600/30 transition-colors"
    >
      <Download className="w-3 h-3" />
      Download Report PDF
    </a>
  );
}

