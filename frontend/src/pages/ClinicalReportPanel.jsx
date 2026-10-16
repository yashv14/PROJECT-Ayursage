import { useEffect, useState, useSyncExternalStore } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { createReportStore } from '../services/reports.js';
import { PatientError } from './PatientProfilePage.jsx';

export function ClinicalReportScreen({ state, onRefresh, onIssue, onDownload }) {
  const busy = ['idle', 'loading', 'issuing', 'downloading'].includes(state.status);
  return <section className="card p-3 mt-3" aria-labelledby="clinical-report-title">
    <h2 className="h5" id="clinical-report-title">Approved clinical report</h2>
    <PatientError message={state.error} />
    {busy && <p role="status">Processing report request...</p>}
    {state.status === 'downloaded' && <p role="status">Report downloaded. Refresh to download again.</p>}
    {state.data?.status === 'awaiting_approval' && <p>Doctor approval is required before a report can be issued.</p>}
    {state.data?.status === 'not_issued' && <p>No report has been issued.</p>}
    {state.data?.status === 'available' && <p>Report version {state.data.report.version}, issued {state.data.report.issued_at}.</p>}
    <div className="d-flex gap-2">
      {state.data?.can_generate && <button className="btn btn-primary" disabled={busy} onClick={onIssue}>Issue approved PDF report</button>}
      {state.data?.status === 'available' && <button className="btn btn-primary" disabled={busy} onClick={onDownload}>Download approved PDF</button>}
      <button className="btn btn-outline-secondary" disabled={busy} onClick={onRefresh}>Refresh report</button>
    </div>
  </section>;
}

export function ClinicalReportPanel({ patientId, assessmentId, onAccessDenied }) {
  const { reports } = useAuth();
  const [store] = useState(() => createReportStore(reports, patientId, assessmentId, { onAccessDenied }));
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  useEffect(() => {
    const disconnect = store.connect(); store.load();
    const refresh = () => { disconnect(); store.connect(); if (document.visibilityState !== 'hidden') store.load(); };
    window.addEventListener('focus', refresh); document.addEventListener('visibilitychange', refresh);
    return () => { window.removeEventListener('focus', refresh); document.removeEventListener('visibilitychange', refresh); disconnect(); };
  }, [store]);
  async function download() {
    const blob = await store.download();
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'ayur-sage-clinical-report-v1.pdf';
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <ClinicalReportScreen state={state} onRefresh={store.load} onIssue={store.issue} onDownload={download} />;
}
