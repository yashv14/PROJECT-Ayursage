import { categoricalInputs, inputFeatures, outputTargets } from '../patient/assessmentFields.js';
import { Loading } from '../components/Loading.jsx';
import { PatientError } from './PatientProfilePage.jsx';

export function AssessmentFormScreen({ form, onField, onNotes, onPredict, onSubmit, onReset }) {
  const busy = form.status === 'saving';
  function submit(event) {
    event.preventDefault();
    return onSubmit();
  }
  if (form.saved) return <section className="patient-page">
    <h1 className="h2">Assessment saved</h1>
    <div className="alert alert-success" role="status">Assessment #{form.saved.id} was saved with its inputs and notes.</div>
    <PatientError message={form.error} />
    {form.prediction ? <>
      <div className="alert alert-warning" role="status"><strong>Doctor review required.</strong> These model outputs are pending clinical review and are not prescriptions.</div>
      <h2 className="h4">Generated prediction</h2>
      <p className="text-secondary">Model: {form.prediction.model_version}. This prediction was not saved. These results are available for this submission only and are not stored in assessment history.</p>
      <div className="row g-3 mb-4">{outputTargets.map(name => <div className="col-md-6" key={name}>
        <div className="card h-100 p-3"><h3 className="h5">{name}</h3><p className="patient-text mb-0">{form.prediction.outputs[name]}</p></div>
      </div>)}</div>
    </> : <p className="text-secondary">No prediction is available for this submission.</p>}
    <div className="d-flex flex-wrap gap-2"><a className="btn btn-primary" href={`#/patient/assessments/${form.saved.id}`}>View saved assessment</a>
      <a className="btn btn-outline-primary" href="#/patient/assessments">Assessment history</a><button className="btn btn-outline-secondary" onClick={onReset}>Start another assessment</button></div>
  </section>;
  return <section className="patient-page">
    <h1 className="h2">New clinical assessment</h1>
    <p className="text-secondary">All 12 inputs are required. Enter descriptions in the first eight fields and readings in the last four.</p>
    <p className="alert alert-info" id="assessment-save-note">Save the assessment alone, or explicitly request a model prediction. If a requested prediction fails, the current API does not save the assessment.</p>
    <PatientError message={form.error || form.errors.form} />
    {form.status === 'invalid' && <p className="text-danger" role="alert">Please correct the marked fields before saving.</p>}
    <form onSubmit={submit} noValidate aria-busy={busy} aria-describedby="assessment-save-note" className="card p-4">
      <fieldset disabled={busy}>
        <legend className="h5">Assessment inputs</legend>
        <div className="row g-3">
          {inputFeatures.map((name, index) => {
            const text = categoricalInputs.includes(name);
            const id = `assessment-field-${index}`;
            const error = form.errors[name];
            return <div className="col-md-6" key={name}>
              <label htmlFor={id} className="form-label">{name} <span className="text-secondary small">(required)</span></label>
              <input id={id} name={name} type={text ? 'text' : 'number'} {...(!text ? { step: 'any' } : {})}
                required value={form.values[name]} onChange={event => onField(name, event.target.value)}
                className={`form-control ${error ? 'is-invalid' : ''}`} aria-invalid={!!error} aria-describedby={`${id}-${error ? 'error' : 'help'}`} />
              {error ? <div id={`${id}-error`} className="invalid-feedback">{error}</div>
                : <div id={`${id}-help`} className="form-text">{text ? 'Nonblank text; up to 256 characters.' : 'A finite number is required; no automatic default.'}</div>}
            </div>;
          })}
        </div>
        <div className="mt-4 mb-3"><label htmlFor="assessment-notes" className="form-label">Notes (optional)</label>
          <textarea id="assessment-notes" name="notes" rows={4} value={form.notes} onChange={event => onNotes(event.target.value)}
            className={`form-control ${form.errors.notes ? 'is-invalid' : ''}`} aria-invalid={!!form.errors.notes} aria-describedby={form.errors.notes ? 'notes-error' : 'notes-help'} />
          {form.errors.notes ? <div id="notes-error" className="invalid-feedback">{form.errors.notes}</div> : <div id="notes-help" className="form-text">Patient-supplied notes, up to 4096 characters.</div>}
        </div>
        <div className="form-check mb-3">
          <input className="form-check-input" id="assessment-predict" type="checkbox" checked={form.predict === true}
            onChange={event => onPredict(event.target.checked)} aria-describedby="assessment-predict-help" />
          <label className="form-check-label" htmlFor="assessment-predict">Request a V17 prediction</label>
          <div id="assessment-predict-help" className="form-text">Requires exact fitted categorical values. Outputs require doctor review and are not saved with the assessment.</div>
        </div>
        <button type="submit" className="btn btn-primary">{busy
          ? <Loading label={form.predict ? 'Saving and requesting prediction...' : 'Saving assessment...'} />
          : form.predict ? 'Save and request prediction' : 'Save assessment'}</button>
      </fieldset>
    </form>
  </section>;
}
