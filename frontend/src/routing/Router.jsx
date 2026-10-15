import { useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { resolveRoute, roleRoutes } from './routes.js';
import { AuthPage } from '../pages/AuthPage.jsx';
import { HomePage } from '../pages/HomePage.jsx';
import { PatientWorkspacePage } from '../pages/PatientWorkspacePage.jsx';
import { Loading } from '../components/Loading.jsx';
import { ReceptionPage } from '../pages/ReceptionPage.jsx';
import { DoctorAssessmentsPage } from '../pages/DoctorAssessmentsPage.jsx';

function currentPath() { return window.location.hash.slice(1) || '/'; }
export function Router() {
  const { user } = useAuth();
  const [path, setPath] = useState(currentPath);
  const route = resolveRoute(path, user);
  useEffect(() => {
    const update = () => setPath(currentPath());
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  useEffect(() => {
    if (route.redirect) window.location.replace(`#${route.redirect}`);
  }, [route.redirect]);
  useEffect(() => {
    if (!route.redirect) document.getElementById('main-content')?.focus();
  }, [path, route.redirect]);
  if (route.redirect) return <Loading label="Opening your page…" />;
  if (route.page === 'login' || route.page === 'register') return <AuthPage key={route.page} registration={route.page === 'register'} />;
  if (route.page === 'home') return user.role === 'receptionist' ? <ReceptionPage key={user.id} /> : <HomePage />;
  if (route.page === 'doctorViewer') return <DoctorAssessmentsPage key={`${user.id}:${route.patientId}:${route.assessmentId}`}
    patientId={route.patientId} assessmentId={route.assessmentId} />;
  if (['profile', 'newAssessment', 'history', 'detail'].includes(route.page)) return <PatientWorkspacePage key={user.id} page={route.page} assessmentId={route.assessmentId} />;
  return <section className="card p-4"><h1 className="h3">{route.page === 'forbidden' ? 'Access restricted' : 'Page not found'}</h1>
    <p>{route.page === 'forbidden' ? 'This page is for a different account role.' : 'The requested page does not exist.'}</p>
    <a href={`#${user ? roleRoutes[user.role].path : '/login'}`}>Return to your home</a>
  </section>;
}
