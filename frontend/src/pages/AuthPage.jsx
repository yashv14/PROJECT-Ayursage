import { useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { validateCredentials } from '../auth/validation.js';
import { Loading } from '../components/Loading.jsx';

export function AuthPage({ registration = false }) {
  const auth = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [errors, setErrors] = useState({});
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const pending = submitting || auth.busy;
  async function submit(event) {
    event.preventDefault();
    if (pending) return;
    const nextErrors = validateCredentials(email, password, registration, confirmation);
    setErrors(nextErrors);
    setError('');
    if (Object.keys(nextErrors).length) {
      document.getElementById(Object.keys(nextErrors)[0])?.focus();
      return;
    }
    setSubmitting(true);
    try {
      if (registration) { await auth.register(email.trim().toLowerCase(), password); setSuccess(true); }
      else await auth.login(email.trim().toLowerCase(), password);
    } catch (failure) { setError(failure.message); }
    finally { setSubmitting(false); setPassword(''); setConfirmation(''); }
  }
  return <div className="row g-4 g-lg-5 align-items-start">
    <section className="col-lg-6 intro">
      <p className="eyebrow">AYURVEDIC CARE · AYUR-SAGE</p>
      <h1 className="display-5 fw-semibold">A considered approach<br className="d-none d-md-block" /> to your care.</h1>
      <p className="lead text-secondary mt-3">Begin with a secure account for your AYUR-SAGE journey.</p>
      <div className="border-start border-3 ps-3 mt-4 text-secondary">Clinical features and recommendations will become available in a later release.</div>
    </section>
    <section className="col-lg-6">
      <div className="card auth-card shadow-sm p-4 p-md-5">
        <h2 className="h3">{registration ? 'Create your patient account' : 'Welcome back'}</h2>
        <p className="text-secondary">{registration ? 'Public registration is available for patients. Doctor and administrator accounts are provisioned by an authorized operator.' : 'Sign in with your patient, doctor, or administrator account.'}</p>
        {auth.notice && <div className="alert alert-info" role="status">{auth.notice}</div>}
        {error && <div className="alert alert-danger" role="alert">{error}</div>}
        {success ? <div role="status"><p className="alert alert-success">Your patient account has been created.</p><a className="btn btn-primary" href="#/login">Continue to sign in</a></div> :
          <form onSubmit={submit} noValidate aria-busy={pending}>
            <fieldset disabled={pending}>
              <div className="mb-3">
                <label htmlFor="email" className="form-label">Email</label>
                <input id="email" name="email" type="email" autoComplete="username" required maxLength={254} value={email} onChange={event => setEmail(event.target.value)} className={`form-control ${errors.email ? 'is-invalid' : ''}`} aria-invalid={!!errors.email} aria-describedby={errors.email ? 'email-error' : undefined} />
                {errors.email && <div id="email-error" className="invalid-feedback">{errors.email}</div>}
              </div>
              <div className="mb-3">
                <label htmlFor="password" className="form-label">Password</label>
                <input id="password" name="password" type="password" autoComplete={registration ? 'new-password' : 'current-password'} required value={password} onChange={event => setPassword(event.target.value)} className={`form-control ${errors.password ? 'is-invalid' : ''}`} aria-invalid={!!errors.password} aria-describedby={errors.password ? 'password-error' : registration ? 'password-help' : undefined} />
                {errors.password ? <div id="password-error" className="invalid-feedback">{errors.password}</div> : registration && <div id="password-help" className="form-text">Use 12–128 characters.</div>}
              </div>
              {registration && <div className="mb-4">
                <label htmlFor="confirmation" className="form-label">Confirm password</label>
                <input id="confirmation" type="password" autoComplete="new-password" required value={confirmation} onChange={event => setConfirmation(event.target.value)} className={`form-control ${errors.confirmation ? 'is-invalid' : ''}`} aria-invalid={!!errors.confirmation} aria-describedby={errors.confirmation ? 'confirmation-error' : undefined} />
                {errors.confirmation && <div id="confirmation-error" className="invalid-feedback">{errors.confirmation}</div>}
              </div>}
              <button type="submit" className="btn btn-primary w-100">{pending ? <Loading label={registration ? 'Creating account…' : 'Signing in…'} /> : registration ? 'Create account' : 'Sign in'}</button>
            </fieldset>
          </form>}
        <p className="small text-secondary mt-4 mb-0">{registration ? <>Already registered? <a href="#/login">Sign in</a></> : <>New to AYUR-SAGE? <a href="#/register">Create a patient account</a></>}</p>
      </div>
    </section>
  </div>;
}
