import { useAuth } from '../auth/AuthContext.jsx';
import { roleLabels } from '../services/auth.js';

const descriptions = {
  patient: 'View your patient profile, save a clinical assessment, or browse your assessment history.',
  doctor: 'View authorized patient assessments. Clinical review and manual prescriptions require explicit review permission.',
  admin: 'Manage patient–doctor grants if your account has explicit grant-administrator permission.',
};
export function HomePage() {
  const { user } = useAuth();
  return <section className="home-page">
    <p className="eyebrow">YOUR AYUR-SAGE ACCOUNT</p>
    <h1 className="display-6 fw-semibold">{roleLabels[user.role]} home</h1>
    <p className="lead text-secondary">{descriptions[user.role]}</p>
    <div className="card p-4 mt-4">
      <h2 className="h5">Account details</h2>
      <dl className="row mb-0"><dt className="col-sm-3">Email</dt><dd className="col-sm-9 text-break">{user.email}</dd><dt className="col-sm-3">Account type</dt><dd className="col-sm-9 mb-0">{roleLabels[user.role]}</dd></dl>
    </div>
    {user.role === 'patient' && <div className="d-flex flex-wrap gap-2 mt-4"><a className="btn btn-primary" href="#/patient/profile">My profile</a><a className="btn btn-outline-primary" href="#/patient/assessments/new">New assessment</a><a className="btn btn-outline-primary" href="#/patient/assessments">Assessment history</a></div>}
    {user.role === 'doctor' && <a className="btn btn-primary mt-4" href="#/doctor/assessments">Open assessment viewer</a>}
    {user.role === 'admin' && <a className="btn btn-primary mt-4" href="#/admin/grants">Manage patient–doctor grants</a>}
    <p className="small text-secondary mt-3">Model inference remains unavailable. Clinical recommendations and prescriptions are entered by an authorized doctor.</p>
  </section>;
}
