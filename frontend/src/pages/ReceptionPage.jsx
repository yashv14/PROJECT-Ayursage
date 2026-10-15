import { useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { transitions } from '../services/reception.js';

export function ReceptionScreen({ patient, doctors, rows, next, busy, error, notice, email, setEmail,
  doctor, setDoctor, start, setStart, end, setEnd, editing, onLookup, onSave, onEdit, onStatus, onMore, onReload }) {
  return <section>
    <h1 className="h2">Reception desk</h1>
    <p className="text-secondary">Manage patient registration status, appointments and attendance.</p>
    {error && <div role="alert" className="alert alert-danger">{error}</div>}
    {notice && <div role="status" className="alert alert-success">{notice}</div>}
    {busy && <p role="status">Working…</p>}
    <div className="row g-4">
      <div className="col-lg-4"><div className="card p-4">
        <h2 className="h5">Find a patient</h2>
        <form onSubmit={event => { event.preventDefault(); onLookup(); }}>
          <label htmlFor="lookup-email" className="form-label">Exact email</label>
          <input id="lookup-email" type="email" required maxLength={254} className="form-control" value={email} onChange={event => setEmail(event.target.value)} disabled={busy} />
          <button className="btn btn-primary mt-3" disabled={busy}>Find patient</button>
        </form>
        {patient && <dl className="mt-3"><dt>Patient ID</dt><dd>{patient.id}</dd><dt>Email</dt><dd className="text-break">{patient.email}</dd><dt>Registration status</dt><dd>{patient.administrative_status.replaceAll('_', ' ')}</dd></dl>}
        <h3 className="h6 mt-3">Registration invitations</h3>
        <p className="small text-secondary mb-0">Invitations are unavailable until secure email delivery is configured. Patients can create their own account.</p>
      </div></div>
      <div className="col-lg-8"><div className="card p-4">
        <h2 className="h5">{editing ? `Reschedule appointment ${editing.id}` : 'Create appointment'}</h2>
        <p className="small text-secondary">Confirm doctor availability manually. Default duration is 30 minutes. Times below use your device timezone.</p>
        <form onSubmit={event => { event.preventDefault(); onSave(); }}>
          <fieldset disabled={busy}>
            <label htmlFor="booking-doctor" className="form-label">Doctor</label>
            <select id="booking-doctor" required className="form-select mb-3" value={doctor} onChange={event => setDoctor(event.target.value)} disabled={!!editing || busy}>
              <option value="">Select doctor</option>{doctors.map(row => <option key={row.id} value={row.id}>{row.email}</option>)}
            </select>
            <div className="row g-3"><div className="col-md-6"><label htmlFor="booking-start" className="form-label">Start</label><input id="booking-start" type="datetime-local" required className="form-control" value={start} onChange={event => setStart(event.target.value)} /></div>
              <div className="col-md-6"><label htmlFor="booking-end" className="form-label">End (optional)</label><input id="booking-end" type="datetime-local" className="form-control" value={end} onChange={event => setEnd(event.target.value)} /></div></div>
            <p className="small mt-3">{editing ? `Patient ID: ${editing.patient_id}` : patient ? `Selected patient: ${patient.email}` : 'Find the patient before creating an appointment.'}</p>
            <button className="btn btn-primary" disabled={!editing && !patient}>Save appointment</button>
            {editing && <button type="button" className="btn btn-outline-secondary ms-2" onClick={() => onEdit(null)}>Cancel editing</button>}
          </fieldset>
        </form>
      </div></div>
    </div>
    <div className="d-flex align-items-center gap-3 mt-4"><h2 className="h4 mb-0">Appointments</h2><button className="btn btn-outline-secondary btn-sm" disabled={busy} onClick={onReload}>Refresh</button></div>
    {!rows.length && !busy && <p className="mt-3">No appointments.</p>}
    <div className="table-responsive mt-3"><table className="table align-middle"><thead><tr><th>ID</th><th>Patient</th><th>Doctor</th><th>Start / End</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody>{rows.map(row => <tr key={row.id}><td>{row.id}</td><td>{row.patient_id}</td><td>{doctors.find(d => d.id === row.doctor_user_id)?.email || row.doctor_user_id}</td><td>{new Date(row.starts_at).toLocaleString()}<br />{new Date(row.ends_at).toLocaleString()}</td><td>{row.status.replaceAll('_', ' ')}</td><td>
        {row.status === 'scheduled' && <button className="btn btn-outline-primary btn-sm m-1" disabled={busy} onClick={() => onEdit(row)}>Reschedule</button>}
        {transitions[row.status].map(status => <button key={status} className="btn btn-outline-secondary btn-sm m-1" disabled={busy} onClick={() => onStatus(row.id, status)}>{({ checked_in: 'Check in', cancelled: 'Cancel', no_show: 'No show', completed: 'Complete' })[status]}</button>)}
      </td></tr>)}</tbody></table></div>
    {next !== null && <button className="btn btn-outline-primary" disabled={busy} onClick={onMore}>Load more</button>}
  </section>;
}

export function ReceptionPage() {
  const { reception } = useAuth();
  const [state, setState] = useState({ patient: null, doctors: [], rows: [], next: null, busy: true, error: '', notice: '' });
  const [email, setEmail] = useState(''); const [doctor, setDoctor] = useState('');
  const [start, setStart] = useState(''); const [end, setEnd] = useState(''); const [editing, setEditing] = useState(null);
  async function reload(more = false) {
    const result = await reception.list(more ? state.next : 0);
    setState(old => ({ ...old, rows: more ? [...old.rows, ...result.appointments] : result.appointments, next: result.next_after_id }));
  }
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [result, first] = await Promise.all([reception.list(), reception.doctors()]);
        let doctors = first.doctors; let after = first.next_after_id;
        while (after !== null) { const page = await reception.doctors(after); doctors = [...doctors, ...page.doctors]; after = page.next_after_id; }
        if (active) setState(old => ({ ...old, doctors, rows: result.appointments, next: result.next_after_id, busy: false }));
      } catch (error) { if (active) setState(old => ({ ...old, busy: false, error: error.message })); }
    })();
    return () => { active = false; };
  }, [reception]);
  async function run(operation) {
    if (state.busy) return;
    setState(old => ({ ...old, busy: true, error: '', notice: '' }));
    try { await operation(); } catch (error) { setState(old => ({ ...old, error: error.message })); }
    finally { setState(old => ({ ...old, busy: false })); }
  }
  function edit(row) {
    setEditing(row); setDoctor(row ? String(row.doctor_user_id) : '');
    const local = iso => { const date = new Date(iso); return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0,16); };
    setStart(row ? local(row.starts_at) : ''); setEnd(row ? local(row.ends_at) : '');
  }
  return <ReceptionScreen {...state} email={email} setEmail={value => { setEmail(value); setState(old => ({ ...old, patient: null })); }} doctor={doctor} setDoctor={setDoctor} start={start} setStart={setStart} end={end} setEnd={setEnd} editing={editing}
    onLookup={() => run(async () => { const patient = await reception.lookup(email); setState(old => ({ ...old, patient })); })}
    onSave={() => run(async () => {
      if (!start || !Number.isFinite(new Date(start).getTime())) throw new Error('Enter a valid start time.');
      const body = { starts_at: new Date(start).toISOString(), ...(end ? { ends_at: new Date(end).toISOString() } : {}) };
      if (editing) await reception.reschedule(editing.id, body);
      else await reception.create({ ...body, patient_id: state.patient.id, doctor_user_id: Number(doctor) });
      edit(null); await reload(); setState(old => ({ ...old, notice: 'Appointment saved.' }));
    })}
    onEdit={edit} onStatus={(id, status) => run(async () => { await reception.status(id, status); await reload(); setState(old => ({ ...old, notice: 'Attendance status updated.' })); })}
    onMore={() => run(() => reload(true))} onReload={() => run(() => reload())} />;
}
