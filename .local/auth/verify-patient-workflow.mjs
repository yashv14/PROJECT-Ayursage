import assert from 'node:assert/strict';
import { randomBytes, randomUUID } from 'node:crypto';
import { createApiClient } from '../../frontend/src/services/api.js';
import { createAuthService } from '../../frontend/src/services/auth.js';
import { createSession } from '../../frontend/src/auth/session.js';
import { createPatientService } from '../../frontend/src/services/patients.js';
import { createPatientWorkspace } from '../../frontend/src/patient/workspace.js';
import { categoricalInputs, numericInputs, prepareAssessment } from '../../frontend/src/patient/assessmentFields.js';
import { resolveRoute } from '../../frontend/src/routing/routes.js';
import { writeFileSync } from 'node:fs';

const origin = 'http://localhost:5174';
const evidence = { browserVerified: false, requests: [] };
const request = async (url, options = {}) => {
  const response = await fetch(url, { ...options, signal: AbortSignal.timeout(5000) });
  evidence.requests.push({ method: options.method || 'GET', path: new URL(url).pathname, status: response.status });
  return response;
};
const api = createApiClient({ baseUrl: origin + '/api', fetchImpl: request });
const auth = createAuthService(api);
const session = createSession(api, auth);
const disconnect = session.connect();
const email = `patient-check-${randomUUID()}@example.invalid`;
const password = randomBytes(24).toString('base64url');
try {
  const user = await session.register(email, password);
  assert.equal(session.getSnapshot().user, null);
  await session.login(email, password);
  assert.equal((await api.request('/auth/me', { authenticated: true })).user.id, user.id);
  const service = createPatientService(api);
  const workspace = createPatientWorkspace(service);
  await workspace.loadProfile();
  const profile = workspace.getSnapshot().profile.data;
  assert.equal(profile.owner_user_id, user.id);
  const values = Object.fromEntries(categoricalInputs.map(name => [name, 'Synthetic test only']));
  numericInputs.forEach((name, index) => { values[name] = ['120', '80', '72', '65'][index]; });
  Object.entries(values).forEach(([name, value]) => workspace.changeField(name, value));
  const notes = 'Synthetic workflow verification; no clinical recommendation requested.';
  workspace.changeNotes(notes);
  await workspace.submit();
  const saved = workspace.getSnapshot().form.saved;
  assert.ok(saved, workspace.getSnapshot().form.error);
  assert.deepEqual(saved.inputs, prepareAssessment(values, notes).payload.inputs);
  assert.equal(saved.recorded_by_user_id, user.id);
  await workspace.loadHistory();
  assert.deepEqual(workspace.getSnapshot().history.items, [saved]);
  await workspace.loadDetail(saved.id);
  assert.deepEqual(workspace.getSnapshot().detail.data, saved);
  session.logout();
  for (const path of ['/patient', '/patient/profile', '/patient/assessments/new', '/patient/assessments', `/patient/assessments/${saved.id}`]) {
    assert.deepEqual(resolveRoute(path, session.getSnapshot().user), { redirect: '/login' });
  }
  for (const path of ['/api/auth/me', '/api/patients/me', `/api/patients/${profile.id}/assessments`, `/api/patients/${profile.id}/assessments/${saved.id}`]) {
    assert.equal((await request(origin + path)).status, 401);
  }
  await assert.rejects(session.login(email, 'incorrect-password'), error => error.status === 401);
  assert.equal(session.getSnapshot().user, null);
  // A fresh client must retrieve the persisted account and assessment.
  const freshApi = createApiClient({ baseUrl: origin + '/api', fetchImpl: request });
  const freshAuth = createAuthService(freshApi);
  assert.equal((await freshAuth.login(email, password)).user.id, user.id);
  assert.deepEqual(await createPatientService(freshApi).getAssessment(profile.id, saved.id), saved);
  // Create a second synthetic owner without granting staff access.
  const outsiderApi = createApiClient({ baseUrl: origin + '/api', fetchImpl: request });
  const outsiderAuth = createAuthService(outsiderApi);
  const outsiderEmail = `owner-check-${randomUUID()}@example.invalid`;
  await outsiderAuth.register(outsiderEmail, password);
  await outsiderAuth.login(outsiderEmail, password);
  const outsider = createPatientService(outsiderApi);
  await assert.rejects(outsiderApi.request(`/patients/${profile.id}`, { authenticated: true }), error => error.status === 404);
  await assert.rejects(outsider.getHistory(profile.id), error => error.status === 404);
  await assert.rejects(outsider.getAssessment(profile.id, saved.id), error => error.status === 404);
  await assert.rejects(outsider.createAssessment(profile.id, prepareAssessment(values, notes).payload), error => error.status === 404);
  freshApi.setToken(null);
  outsiderApi.setToken(null);
  evidence.userId = user.id;
  evidence.patientId = profile.id;
  evidence.assessmentId = saved.id;
  evidence.inputCount = Object.keys(saved.inputs).length;
  evidence.result = 'PASS: live HTTP, existing client/workspace/session and route resolver; no mounted browser';
  writeFileSync(new URL('./patient-workflow-evidence.json', import.meta.url), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence, null, 2));
} finally { session.logout(); disconnect(); }
