// Explicit opt-in check of the running app, not a configured test fixture.
// Creates one synthetic patient account per successful run; no assessments.
import assert from 'node:assert/strict';
import test from 'node:test';
import { randomBytes, randomUUID } from 'node:crypto';
import { createApiClient } from '../../src/services/api.js';
import { createAuthService } from '../../src/services/auth.js';
import { createSession } from '../../src/auth/session.js';
import { resolveRoute } from '../../src/routing/routes.js';

const origin = 'http://localhost:5174';
const request = (url, options) => fetch(url, { ...options, signal: AbortSignal.timeout(5000) });

test('running port 5174: auth readiness, registration, persisted login, JWT, errors and logout', { timeout: 30000 }, async t => {
  const health = await request(origin + '/api/health');
  assert.equal(health.status, 200, 'Vite must proxy Flask health');
  const readiness = await request(origin + '/api/auth/me');
  assert.equal(readiness.status, 401,
    'Auth readiness failed: /me without a token must return 401. Health 200 plus auth 503 indicates an unconfigured backend. Start backend.local, not an unconfigured flask --app backend.app run.');

  const api = createApiClient({ baseUrl: origin + '/api', fetchImpl: async (url, options) => {
    const response = await request(url, options);
    // Only method, path and status; never request/response bodies or headers.
    t.diagnostic(`${options.method} ${new URL(url).pathname} -> ${response.status}`);
    return response;
  } });
  const session = createSession(api, createAuthService(api));
  const disconnect = session.connect();
  t.after(disconnect);
  const email = `auth-check-${randomUUID()}@example.invalid`;
  const password = randomBytes(24).toString('base64url');
  const patient = await session.register(email, password);
  assert.ok(patient.id > 0 && patient.email === email && patient.role === 'patient', 'Registration must return the synthetic patient');
  assert.equal(session.getSnapshot().user, null, 'Registration must not sign in automatically');
  await assert.rejects(session.register(email, password), error => error.status === 409);
  await session.login(email, password);
  const identity = await api.request('/auth/me', { authenticated: true });
  assert.ok(identity.user.id === patient.id && session.getSnapshot().user.id === patient.id, 'JWT and session must resolve the newly persisted account');
  assert.deepEqual(resolveRoute('/login', session.getSnapshot().user), { redirect: '/patient' });
  assert.deepEqual(resolveRoute('/patient', session.getSnapshot().user), { page: 'home' });
  assert.deepEqual(resolveRoute('/doctor', session.getSnapshot().user), { page: 'forbidden' });

  session.logout();
  assert.equal(session.getSnapshot().user, null);
  assert.deepEqual(resolveRoute('/patient', session.getSnapshot().user), { redirect: '/login' });
  await assert.rejects(api.request('/auth/me', { authenticated: true }), error => error.status === 401);
  await assert.rejects(session.login(email, 'incorrect-password'), error =>
    error.status === 401 && error.message === 'Email or password is incorrect.');
  assert.equal(session.getSnapshot().user, null);
  assert.equal(session.getSnapshot().busy, false);
  // Sign in again as an existing account, using a fresh session/API instance.
  const existingApi = createApiClient({ baseUrl: origin + '/api', fetchImpl: request });
  const existing = await createAuthService(existingApi).login(email, password);
  assert.ok(existing.user.id === patient.id, 'Existing account login must survive session logout');
  existingApi.setToken(null);
  t.diagnostic('Synthetic registration, duplicate 409, new and existing account login, JWT /me, invalid credentials, session logout and route guards passed. No browser UI was operated.');
});
