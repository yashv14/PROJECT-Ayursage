import { useAuth } from '../auth/AuthContext.jsx';
import { roleLabels } from '../services/auth.js';
import { roleRoutes } from '../routing/routes.js';

export function AppShell({ children }) {
  const { user, logout } = useAuth();
  return <div className="app-shell">
    <a className="visually-hidden-focusable skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content').focus(); }}>Skip to content</a>
    <header className="bg-white border-bottom">
      <nav className="container py-3 d-flex flex-wrap align-items-center gap-3" aria-label="Main navigation">
        <a className="brand me-auto" href={`#${user ? roleRoutes[user.role].path : '/login'}`}>AYUR<span>–SAGE</span></a>
        {user ? <>
          <a className="nav-link" href={`#${roleRoutes[user.role].path}`}>{roleRoutes[user.role].label}</a>
          {user.role === 'patient' && <><a className="nav-link" href="#/patient/profile">My profile</a><a className="nav-link" href="#/patient/assessments/new">New assessment</a><a className="nav-link" href="#/patient/assessments">History</a></>}
          <span className="badge role-badge">{roleLabels[user.role]}</span>
          <button className="btn btn-outline-secondary btn-sm" onClick={() => logout('You have signed out.')}>Log out</button>
        </> : <><a className="nav-link" href="#/login">Sign in</a><a className="btn btn-outline-primary btn-sm" href="#/register">Create account</a></>}
      </nav>
    </header>
    <main id="main-content" tabIndex={-1} className="container flex-grow-1 py-4 py-md-5">{children}</main>
    <footer className="container py-3 border-top text-secondary small">AYUR-SAGE · Patient assessment records</footer>
  </div>;
}
