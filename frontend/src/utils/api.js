/**
 * LiveLens REST API utility functions.
 *
 * All endpoints map to the FastAPI backend. The Vite dev proxy
 * forwards /inspection and /inspections to http://localhost:8000.
 */

export async function listInspections(limit = 50) {
  const res = await fetch(`/inspections?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to list inspections: ${res.status}`);
  return res.json(); // { count, sessions }
}

export async function getSessionMetadata(sessionId) {
  const res = await fetch(`/inspection/${sessionId}/session`);
  if (!res.ok) {
    if (res.status === 404) return null;
    throw new Error(`Failed to fetch session: ${res.status}`);
  }
  return res.json();
}

export async function getSessionFindings(sessionId) {
  const res = await fetch(`/inspection/${sessionId}/findings`);
  if (!res.ok) throw new Error(`Failed to fetch findings: ${res.status}`);
  return res.json(); // { session_id, count, findings }
}

export async function getSessionReport(sessionId) {
  const res = await fetch(`/inspection/${sessionId}/report`);
  if (!res.ok) {
    if (res.status === 404) return null;
    throw new Error(`Failed to fetch report: ${res.status}`);
  }
  return res.json();
}

export async function generateReport(sessionId) {
  const res = await fetch(`/inspection/${sessionId}/report`, { method: 'POST' });
  if (!res.ok) throw new Error(`Report generation failed: ${res.status}`);
  return res.json();
}

export async function getReportPdfUrl(sessionId) {
  const res = await fetch(`/inspection/${sessionId}/report/pdf`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 409) return null;
    throw new Error(`Failed to fetch PDF URL: ${res.status}`);
  }
  return res.json(); // { session_id, report_id, pdf_url, pdf_generated_at }
}

