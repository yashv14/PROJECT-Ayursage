import { inputFeatures } from '../patient/assessmentFields.js';
import { Loading } from '../components/Loading.jsx';
import { PatientError } from './PatientProfilePage.jsx';

export function AssessmentDetailScreen({ detail, onRetry, backHref = '#/patient/assessments' }) {
  const row = detail.data;
  return <section className="patient-page">
    <a href={backHref}>Back to assessment history</a>
    <h1 className="h2 mt-3">Assessment details{row ? ` #${row.id}` : ''}</h1>
    {(detail.status === 'idle' || detail.status === 'loading') && <Loading label="Loading assessment details..." />}
    <PatientError message={detail.error} onRetry={onRetry} />
    {row && <>
      <p className="text-secondary">Recorded at (server time): <time dateTime={row.created_at}>{row.created_at.replace('T', ' ')}</time></p>
      <div className="card p-4"><h2 className="h5">Saved inputs</h2>
        {row.inputs === null ? <p>This older assessment has no saved input values.</p>
          : <dl className="row mb-0">{inputFeatures.map(name => <div className="row g-0" key={name}><dt className="col-md-5">{name}</dt><dd className="col-md-7 patient-text">{row.inputs[name]}</dd></div>)}</dl>}
        <h2 className="h5 mt-3">Patient-supplied notes</h2><p className="patient-text mb-0">{row.notes === null || row.notes === '' ? 'No notes were supplied.' : row.notes}</p>
      </div>
      <p className="alert alert-info mt-3">This page shows saved inputs and notes. Model predictions are response-only and are not stored with the assessment or available from assessment history.</p>
    </>}
  </section>;
}
