import { useEffect, useState, useSyncExternalStore } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { createGrantAdmin } from '../admin/grants.js';
import { AccessGrantsScreen, PatientError } from './PatientProfilePage.jsx';

export function AdminGrantsScreen({ state, onLoad, onMore, onPrepare, onIssue, onCancel, onConfirmRevoke, onRevoke }) {
  const [patientId, setPatientId] = useState('');
  const [doctorId, setDoctorId] = useState('');
  const [reference, setReference] = useState('');
  const [allowReview, setAllowReview] = useState(false);
  const [attested, setAttested] = useState(false);
  useEffect(() => {
    setDoctorId(''); setReference(''); setAllowReview(false); setAttested(false);
  }, [state.patientId]);
  useEffect(() => {
    if (state.notice) {
      setDoctorId(''); setReference(''); setAllowReview(false); setAttested(false);
    }
  }, [state.notice]);
  const busy = ['loading', 'issuing', 'revoking'].includes(state.status);
  const candidate = state.issueCandidate;
  const reload = () => onLoad(String(state.patientId));
  return <section className="patient-page">
    <h1 className="h2">Patient–doctor grants</h1>
    <p>Only explicitly authorized grant administrators can manage grants. Use verified patient and doctor IDs and retained patient-consent evidence.</p>
    <p>No clinical records are shown here. Appointments do not grant access.</p>
    <form className="card p-3" onSubmit={event => { event.preventDefault(); onLoad(patientId); }}>
      <label className="form-label" htmlFor="grant-patient-id">Patient profile ID</label>
      <input className="form-control mb-2" id="grant-patient-id" inputMode="numeric" pattern="[1-9][0-9]*" maxLength={10} required value={patientId} disabled={busy} onChange={event => setPatientId(event.target.value)} />
      <button className="btn btn-primary align-self-start" disabled={busy}>Load patient grants</button>
    </form>
    {state.patientId === null && <PatientError message={state.error} />}
    {state.patientId !== null && <>
      <p className="mt-3">Selected patient profile #{state.patientId}</p>
      <AccessGrantsScreen grants={state} administration onReload={reload} onMore={onMore}
        onConfirm={onConfirmRevoke} onCancel={onCancel} onRevoke={onRevoke} />
      {state.status === 'ready' && !candidate && <form className="card p-3 mt-3" onSubmit={event => {
        event.preventDefault(); onPrepare({ doctorId, reference, allowReview, attested });
      }}>
        <h2 className="h5">Issue a consent-attested grant</h2>
        <label className="form-label" htmlFor="grant-doctor-id">Doctor account ID</label>
        <input className="form-control mb-3" id="grant-doctor-id" inputMode="numeric" pattern="[1-9][0-9]*" maxLength={10} required value={doctorId} onChange={event => { setDoctorId(event.target.value); setAttested(false); }} />
        <label className="form-label" htmlFor="grant-consent-reference">Retained consent reference</label>
        <input className="form-control mb-3" id="grant-consent-reference" required maxLength={256} value={reference} onChange={event => { setReference(event.target.value); setAttested(false); }} />
        <label className="form-check mb-2"><input className="form-check-input" type="checkbox" checked={allowReview} onChange={event => { setAllowReview(event.target.checked); setAttested(false); }} />
          Permit doctor-authored clinical review and prescription recording</label>
        <label className="form-check mb-3"><input className="form-check-input" type="checkbox" checked={attested} required onChange={event => setAttested(event.target.checked)} />
          I verified retained consent for this patient, doctor, selected permissions and 30-day access.</label>
        <p>Read-only is the default. Review permission requires consent covering human clinical review and prescription recording. This form records your attestation; it does not verify the external document.</p>
        <button className="btn btn-primary">Review grant before issuing</button>
      </form>}
      {candidate && <div className="card border-warning p-3 mt-3" role="region" aria-label="Confirm grant issuance">
        <h2 className="h5">Confirm grant issuance</h2>
        <p>Patient #{state.patientId}; doctor #{candidate.doctor_user_id}; 30-day assessment access.</p>
        <p>Permission: {candidate.allow_review ? 'Read and clinical review, including manual prescriptions' : 'Read-only'}</p>
        <p>Consent reference: {candidate.consent_reference}</p>
        <div className="d-flex gap-2"><button className="btn btn-primary" disabled={busy} onClick={onIssue}>Confirm issue grant</button>
          <button className="btn btn-outline-secondary" disabled={busy} onClick={onCancel}>Cancel issuance</button></div>
      </div>}
    </>}
  </section>;
}

export function AdminGrantsPage() {
  const { patients } = useAuth();
  const [store] = useState(() => createGrantAdmin(patients));
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  useEffect(() => store.connect(), [store]);
  return <AdminGrantsScreen state={state} onLoad={id => store.load(id)}
    onMore={() => store.load(String(state.patientId), true)} onPrepare={store.prepareIssue}
    onIssue={store.issue} onCancel={store.cancel} onConfirmRevoke={store.confirmRevoke} onRevoke={store.revoke} />;
}
