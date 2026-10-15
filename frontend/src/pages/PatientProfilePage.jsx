import { Loading } from '../components/Loading.jsx';

export function PatientError({ message, onRetry }) {
  if (!message) return null;
  return <div className="alert alert-danger" role="alert"><p className="mb-0">{message}</p>
    {onRetry && <button className="btn btn-outline-danger btn-sm mt-2" onClick={onRetry}>Try again</button>}
  </div>;
}

export function AccessGrantsScreen({ grants, onReload, onMore, onConfirm, onCancel, onRevoke }) {
  const busy = ['loading', 'revoking'].includes(grants.status);
  return <section className="card p-4 mt-4" aria-labelledby="doctor-access-title" aria-busy={busy}>
    <h2 id="doctor-access-title" className="h5">Doctor access to my assessments</h2>
    <p className="text-secondary">These grants let a doctor read your saved assessments. Revoking a grant stops future reads through that grant. New access requires a new grant from an authorized administrator.</p>
    <PatientError message={grants.error} />
    {grants.notice && <p className="alert alert-success" role="status">{grants.notice}</p>}
    {busy && <Loading label={grants.status === 'revoking' ? 'Revoking doctor access...' : 'Loading doctor access...'} />}
    {grants.status === 'ready' && !grants.items.length && <p>No doctor-access grants have been recorded.</p>}
    {grants.items.length > 0 && <div className="table-responsive"><table className="table align-middle">
      <caption>Current and previous assessment-read grants. Times are shown in your device timezone.</caption>
      <thead><tr><th scope="col">Grant / Doctor</th><th scope="col">Status</th><th scope="col">Expires</th><th scope="col">Actions</th></tr></thead>
      <tbody>{grants.items.map(row => <tr key={row.id}>
        <th scope="row">Grant #{row.id}<br />Doctor #{row.doctor_user_id}</th>
        <td>{({ issued: 'Active', expired: 'Expired', revoked: 'Revoked' })[row.status]}</td>
        <td><time dateTime={row.expires_at}>{new Date(row.expires_at).toLocaleString()}</time></td>
        <td>{row.status === 'issued' && (grants.confirmingId === row.id
          ? <><p className="mb-2">Revoke grant #{row.id} for doctor #{row.doctor_user_id}?</p>
            <button className="btn btn-danger btn-sm me-2" disabled={busy} onClick={() => onRevoke(row.id)}>Confirm revocation</button>
            <button className="btn btn-outline-secondary btn-sm" disabled={busy} onClick={onCancel}>Cancel</button></>
          : <button className="btn btn-outline-danger btn-sm" disabled={busy} onClick={() => onConfirm(row.id)} aria-label={`Revoke grant ${row.id} for doctor ${row.doctor_user_id}`}>Revoke access</button>)}</td>
      </tr>)}</tbody>
    </table></div>}
    <div className="d-flex flex-wrap gap-2">
      {grants.nextAfterId !== null && <button className="btn btn-outline-primary" disabled={busy} onClick={onMore}>Load more grants</button>}
      <button className="btn btn-outline-secondary" disabled={busy} onClick={onReload}>Refresh doctor access</button>
    </div>
  </section>;
}

export function ProfileScreen({ profile, onCreate, onReload, grants, onReloadGrants, onMoreGrants, onConfirmRevoke, onCancelRevoke, onRevoke }) {
  const busy = profile.status === 'loading' || profile.status === 'creating';
  return <section className="patient-page">
    <h1 className="h2">Patient profile</h1>
    <p className="text-secondary">Your profile is linked to your signed-in patient account.</p>
    {busy && <Loading label={profile.status === 'creating' ? 'Creating your profile...' : 'Loading your profile...'} />}
    <PatientError message={profile.error} onRetry={onReload} />
    {profile.notice && <div className="alert alert-success" role="status">{profile.notice}</div>}
    {profile.data ? <div className="card p-4">
      <h2 className="h5">Profile details</h2>
      <dl className="row mb-0"><dt className="col-sm-4">Patient profile ID</dt><dd className="col-sm-8">{profile.data.id}</dd>
        <dt className="col-sm-4">Owner account ID</dt><dd className="col-sm-8">{profile.data.owner_user_id}</dd></dl>
      <div className="d-flex flex-wrap gap-2 mt-3"><a className="btn btn-primary" href="#/patient/assessments/new">New assessment</a><a className="btn btn-outline-primary" href="#/patient/assessments">Assessment history</a></div>
    </div> : !busy && !profile.error && <div className="card p-4">
      <h2 className="h5">Create your patient profile</h2>
      <p>No profile exists for your account yet. Create one to connect your assessment records to your account.</p>
      <button className="btn btn-primary align-self-start" onClick={onCreate}>Create my profile</button>
    </div>}
    {profile.data && grants && <AccessGrantsScreen grants={grants} onReload={onReloadGrants} onMore={onMoreGrants}
      onConfirm={onConfirmRevoke} onCancel={onCancelRevoke} onRevoke={onRevoke} />}
  </section>;
}
