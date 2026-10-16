import { useEffect, useState, useSyncExternalStore } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { createReviewStore, prescriptionFields } from '../doctor/review.js';
import { outputTargets } from '../patient/assessmentFields.js';
import { PatientError } from './PatientProfilePage.jsx';

const names = { pending_review: 'Pending review', approved: 'Approved', returned_for_changes: 'Returned for changes' };
export function DoctorReviewScreen({ state, onReload, onSave }) {
  const data = state.data;
  return <section className="card p-4 mt-4" aria-labelledby="clinical-review-title">
    <h2 id="clinical-review-title" className="h4">Doctor clinical review</h2>
    <p>Recommendations and prescriptions here are entered by a doctor. No V17 inference was run for this review.</p>
    <PatientError message={state.error} onRetry={onReload} />
    {state.notice && <p className="alert alert-success" role="status">{state.notice}</p>}
    {['loading', 'idle'].includes(state.status) && <p role="status">Loading clinical review...</p>}
    {data && <>
      <p>Review status: <strong>{names[data.state]}</strong>. Version: {data.version}.</p>
      {data.reviews.map(review => <article className="border rounded p-3 mb-3" key={review.sequence}>
        <h3 className="h6">Review #{review.sequence}: {names[review.decision]}</h3>
        <p>Doctor account #{review.actor_user_id} — <time dateTime={review.decided_at}>{review.decided_at}</time></p>
        <p className="text-break" style={{ whiteSpace: 'pre-wrap' }}>{review.clinical_notes}</p>
        {review.origin === 'doctor_entered' ? <>
          <dl>{outputTargets.map(name => <div key={name}><dt>{name} — doctor-entered</dt><dd style={{ whiteSpace: 'pre-wrap' }}>{review.recommendations[name]}</dd></div>)}</dl>
          <h4 className="h6">Doctor-entered prescriptions</h4>
          {!review.prescriptions.length && <p>No prescription recorded.</p>}
          {review.prescriptions.map((item, index) => <dl key={index}>{prescriptionFields.map(name => <div key={name}><dt>{name}</dt><dd>{item[name] || 'None'}</dd></div>)}</dl>)}
        </> : <p>Legacy review record; no recommendation or prescription provenance is asserted.</p>}
      </article>)}
      {!data.can_review && <p>Read-only access. An authorized administrator must issue explicit clinical-review permission with consent.</p>}
      {data.can_review && data.state === 'approved' && <p>This decision is final. Saved review history cannot be edited.</p>}
      {data.can_review && data.state !== 'approved' && data.version < 100 && <ReviewForm key={data.version} data={data} busy={state.status === 'saving'} onSave={onSave} />}
    </>}
    <button className="btn btn-outline-secondary align-self-start mt-2" disabled={['loading','saving'].includes(state.status)} onClick={onReload}>Refresh clinical review</button>
  </section>;
}

function ReviewForm({ data, busy, onSave }) {
  const latest = data.reviews.at(-1);
  const [notes, setNotes] = useState(latest?.clinical_notes ?? '');
  const [recommendations, setRecommendations] = useState(() => Object.fromEntries(outputTargets.map(name => [name, latest?.recommendations?.[name] ?? ''])));
  const [prescriptions, setPrescriptions] = useState(latest?.prescriptions ?? []);
  const [decision, setDecision] = useState(data.state === 'returned_for_changes' ? 'pending_review' : 'approved');
  return <form onSubmit={event => { event.preventDefault(); onSave({ decision, clinical_notes: notes, recommendations, prescriptions }); }}>
    <fieldset disabled={busy}>
      <legend className="h5">Record your clinical decision</legend>
      <label className="form-label" htmlFor="clinical-notes">Clinical notes (required)</label>
      <textarea className="form-control mb-3" id="clinical-notes" required maxLength={4096} value={notes} onChange={event => setNotes(event.target.value)} />
      {outputTargets.map((name, index) => <div key={name} className="mb-3">
        <label className="form-label" htmlFor={`manual-recommendation-${index}`}>{name} (doctor-entered, required)</label>
        <textarea className="form-control" id={`manual-recommendation-${index}`} required maxLength={2048} value={recommendations[name]}
          onChange={event => setRecommendations({ ...recommendations, [name]: event.target.value })} />
      </div>)}
      <h3 className="h6">Manual prescriptions (optional)</h3>
      {prescriptions.map((item, index) => <fieldset className="border p-3 mb-3" key={index}>
        <legend className="h6">Prescription {index + 1}</legend>
        {prescriptionFields.map(name => <div key={name} className="mb-2">
          <label className="form-label" htmlFor={`prescription-${index}-${name}`}>{name}</label>
          <input className="form-control" id={`prescription-${index}-${name}`} required={name !== 'instructions'} maxLength={256} value={item[name]}
            onChange={event => setPrescriptions(prescriptions.map((value, i) => i === index ? { ...value, [name]: event.target.value } : value))} />
        </div>)}
        <button type="button" className="btn btn-outline-danger" onClick={() => setPrescriptions(prescriptions.filter((_, i) => i !== index))}>Remove prescription {index + 1}</button>
      </fieldset>)}
      <button type="button" className="btn btn-outline-secondary mb-3" disabled={prescriptions.length >= 10}
        onClick={() => setPrescriptions([...prescriptions, Object.fromEntries(prescriptionFields.map(name => [name, '']))])}>Add prescription</button>
      <div className="mb-3"><label className="form-label" htmlFor="review-decision">Decision</label>
        <select className="form-select" id="review-decision" value={decision} onChange={event => setDecision(event.target.value)}>
          {data.state === 'returned_for_changes' ? <option value="pending_review">Resubmit revised review for approval</option> : <>
            <option value="approved">Approve doctor-entered recommendations</option>
            <option value="returned_for_changes">Return for changes</option>
          </>}
        </select>
      </div>
      <p>Saving appends an immutable decision to this assessment. Check all manually entered prescription details.</p>
      <button className="btn btn-primary" type="submit">{busy ? 'Saving clinical review...' : 'Save clinical review'}</button>
    </fieldset>
  </form>;
}

export function DoctorReviewPanel({ patientId, assessmentId, onAccessDenied }) {
  const { reviews } = useAuth();
  const [store] = useState(() => createReviewStore(reviews, patientId, assessmentId, { onAccessDenied }));
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  useEffect(() => { const disconnect = store.connect(); store.load(); return disconnect; }, [store]);
  return <DoctorReviewScreen state={state} onReload={() => store.load()} onSave={payload => store.save(payload)} />;
}
