import { useEffect, useState, useSyncExternalStore } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { createDoctorViewer } from '../doctor/workspace.js';
import { AssessmentHistoryScreen } from './AssessmentHistoryPage.jsx';
import { AssessmentDetailScreen } from './AssessmentDetailPage.jsx';
import { Loading } from '../components/Loading.jsx';
import { PatientError } from './PatientProfilePage.jsx';

export function DoctorDirectoryScreen({ state, onReload, onMore }) {
  const busy = state.status === 'idle' || state.status === 'loading';
  return <section className="patient-page">
    <h1 className="h2">Patients with assessment access</h1>
    <p>Select a patient to read their saved assessments. This list includes only patients currently authorized for your doctor account.</p>
    <p className="text-secondary">Patients are identified by ID; names are not available.</p>
    <PatientError message={state.error} onRetry={onReload} />
    {busy && <Loading label="Loading authorized patients..." />}
    {state.status === 'ready' && !state.items.length && <p>No patients are currently authorized for assessment access.</p>}
    {state.items.length > 0 && <ul className="list-group mb-3">{state.items.map(patient => <li className="list-group-item" key={patient.id}>
      <a href={`#/doctor/patients/${patient.id}/assessments`}>Patient #{patient.id} — View assessment history</a>
    </li>)}</ul>}
    <div className="d-flex gap-2">
      {state.nextAfterId !== null && <button className="btn btn-outline-primary" disabled={busy} onClick={onMore}>Next patients</button>}
      <button className="btn btn-outline-secondary" disabled={busy} onClick={onReload}>Refresh patients</button>
    </div>
  </section>;
}

export function DoctorAssessmentScreen({ patientId, assessmentId, state, onReload, onMore }) {
  return <>
    <a href="#/doctor/assessments">Back to authorized patients</a>
    <p className="mt-3">Patient ID: {patientId}. Read-only assessment access.</p>
    {assessmentId ? <>
      <AssessmentDetailScreen detail={{ status: state.status, data: state.detail, error: state.error }} onRetry={onReload}
        backHref={`#/doctor/patients/${patientId}/assessments`} />
      <button className="btn btn-outline-secondary mt-3" disabled={state.status === 'loading'} onClick={onReload}>Refresh assessment</button>
    </> : <AssessmentHistoryScreen history={state} onReload={onReload} onMore={onMore} readOnly
      detailHref={id => `#/doctor/patients/${patientId}/assessments/${id}`} />}
  </>;
}

function DoctorRecordViewer({ patientId, assessmentId }) {
  const { patients } = useAuth();
  const [viewer] = useState(() => createDoctorViewer(patients, patientId));
  const state = useSyncExternalStore(viewer.subscribe, viewer.getSnapshot, viewer.getSnapshot);
  const reload = () => !patientId ? viewer.loadDirectory() : assessmentId ? viewer.loadDetail(assessmentId) : viewer.loadHistory();
  useEffect(() => {
    const disconnect = viewer.connect();
    const refresh = () => !patientId ? viewer.loadDirectory() : assessmentId ? viewer.loadDetail(assessmentId) : viewer.loadHistory();
    const visibility = () => { if (document.visibilityState === 'hidden') viewer.clear(); else refresh(); };
    refresh();
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', visibility);
    return () => {
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', visibility);
      disconnect();
    };
  }, [viewer, patientId, assessmentId]);
  if (!patientId) return <DoctorDirectoryScreen state={state} onReload={reload} onMore={() => viewer.loadDirectory(true)} />;
  return <DoctorAssessmentScreen patientId={patientId} assessmentId={assessmentId} state={state}
    onReload={reload} onMore={() => viewer.loadHistory(true)} />;
}

export function DoctorAssessmentsPage({ patientId, assessmentId }) {
  return <DoctorRecordViewer patientId={patientId} assessmentId={assessmentId} />;
}
