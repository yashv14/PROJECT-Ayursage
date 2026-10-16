export const roleRoutes = {
  patient: { path: '/patient', label: 'Patient home' },
  doctor: { path: '/doctor', label: 'Doctor home' },
  admin: { path: '/admin', label: 'Administrator home' },
  receptionist: { path: '/receptionist', label: 'Reception desk' },
};

export function resolveRoute(path, user) {
  if (path === '/admin/grants') {
    if (!user) return { redirect: '/login' };
    return { page: user.role === 'admin' ? 'adminGrants' : 'forbidden' };
  }
  if (path === '/' || path === '/login' || path === '/register') {
    return user ? { redirect: roleRoutes[user.role]?.path || '/login' } : { page: path === '/register' ? 'register' : 'login' };
  }
  const doctorMatch = path.match(/^\/doctor\/patients\/([1-9]\d*)\/assessments(?:\/([1-9]\d*))?$/);
  if (path === '/doctor/assessments' || doctorMatch) {
    const patientId = doctorMatch ? Number(doctorMatch[1]) : null;
    const assessmentId = doctorMatch?.[2] ? Number(doctorMatch[2]) : null;
    if ((patientId !== null && patientId > 2147483647) || (assessmentId !== null && assessmentId > 2147483647)) return { page: 'notFound' };
    if (!user) return { redirect: '/login' };
    if (user.role !== 'doctor') return { page: 'forbidden' };
    return { page: 'doctorViewer', patientId, assessmentId };
  }
  const patientPages = { '/patient/profile': 'profile', '/patient/assessments/new': 'newAssessment', '/patient/assessments': 'history' };
  const detailMatch = path.match(/^\/patient\/assessments\/([1-9]\d*)$/);
  const assessmentId = detailMatch ? Number(detailMatch[1]) : null;
  const patientPage = patientPages[path] || (assessmentId > 0 && assessmentId <= 2147483647 ? 'detail' : null);
  if (patientPage) {
    if (!user) return { redirect: '/login' };
    if (user.role !== 'patient') return { page: 'forbidden' };
    return { page: patientPage, ...(patientPage === 'detail' ? { assessmentId } : {}) };
  }
  const role = Object.keys(roleRoutes).find(key => roleRoutes[key].path === path);
  if (!role) return { page: 'notFound' };
  if (!user) return { redirect: '/login' };
  return { page: user.role === role ? 'home' : 'forbidden' };
}
