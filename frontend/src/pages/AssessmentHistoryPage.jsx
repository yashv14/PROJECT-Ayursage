import { Loading } from '../components/Loading.jsx';
import { PatientError } from './PatientProfilePage.jsx';

export function AssessmentHistoryScreen({ history, onReload, onMore, readOnly = false, detailHref = id => `#/patient/assessments/${id}` }) {
  const busy = history.status === 'idle' || history.status === 'loading';
  return <section className="patient-page">
    <div className="d-flex flex-wrap align-items-center gap-3 mb-3"><h1 className="h2 mb-0 me-auto">Assessment history</h1>{!readOnly && <a className="btn btn-primary" href="#/patient/assessments/new">New assessment</a>}</div>
    <p className="text-secondary">{readOnly ? 'Saved assessments available through your current read access, in record order.' : 'Saved assessments, in record order. Predictions are not generated yet.'}</p>
    <PatientError message={history.error} onRetry={history.items.length && history.nextAfterId !== null ? onMore : onReload} />
    {busy && <Loading label="Loading assessment history..." />}
    {history.status === 'ready' && history.items.length === 0 && <div className="card p-4"><p className="mb-0">No assessments have been saved yet.</p></div>}
    {history.items.length > 0 && <div className="card mt-3"><div className="table-responsive">
      <table className="table mb-0"><caption className="px-3">{readOnly ? 'Patient assessments.' : 'Your saved assessments.'} Recorded times are provided by the server without timezone conversion.</caption>
        <thead><tr><th scope="col">Assessment</th><th scope="col">Recorded at (server time)</th><th scope="col">Input record</th></tr></thead>
        <tbody>{history.items.map(row => <tr key={row.id}><th scope="row"><a href={detailHref(row.id)}>Assessment #{row.id}</a></th>
          <td><time dateTime={row.created_at}>{row.created_at.replace('T', ' ')}</time></td><td>{row.inputs === null ? 'Legacy record: no stored inputs' : '12 saved inputs'}</td></tr>)}</tbody>
      </table>
    </div></div>}
    <div className="d-flex gap-2 mt-3">{history.nextAfterId !== null && <button className="btn btn-outline-primary" onClick={onMore} disabled={busy}>Load more</button>}
      <button className="btn btn-outline-secondary" onClick={onReload} disabled={busy}>Refresh history</button></div>
  </section>;
}
