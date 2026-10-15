import assert from 'node:assert/strict';
import test from 'node:test';
import { createApiClient, ApiError } from '../src/services/api.js';
import { createAuthService } from '../src/services/auth.js';
import { validateCredentials } from '../src/auth/validation.js';
import { resolveRoute } from '../src/routing/routes.js';

const response = (body, status = 200) => new Response(JSON.stringify(body), { status });
const user = { id: 1, email: 'patient@example.invalid', role: 'patient' };

test('registration validates backend boundaries and does not require long login passwords', () => {
  assert.deepEqual(validateCredentials(' Patient@Example.invalid ', 'long-password', true, 'long-password'), {});
  assert.deepEqual(validateCredentials('p@example.invalid', 'short'), {});
  for (const email of ['invalid', '.p@example.invalid', 'p..q@example.invalid', 'p.@example.invalid', 'é@example.invalid', 'x'.repeat(65) + '@example.invalid']) {
    assert.ok(validateCredentials(email, 'long-password').email);
  }
  for (const password of ['short', ' '.repeat(12), 'x'.repeat(129), 'long-password\0']) {
    assert.ok(validateCredentials('p@example.invalid', password, true, password).password);
  }
  assert.deepEqual(validateCredentials('p@example.invalid', '😀'.repeat(128), true, '😀'.repeat(128)), {});
  assert.ok(validateCredentials('p@example.invalid', 'long-password', true, 'different').confirmation);
});

test('anonymous users and every role are guarded on every role route', () => {
  const roles = ['patient', 'doctor', 'admin', 'receptionist'];
  for (const role of roles) {
    assert.deepEqual(resolveRoute('/' + role, null), { redirect: '/login' });
    for (const actor of roles) {
      assert.deepEqual(resolveRoute('/' + role, { ...user, role: actor }), { page: actor === role ? 'home' : 'forbidden' });
    }
    assert.deepEqual(resolveRoute('/login', { ...user, role }), { redirect: '/' + role });
    assert.deepEqual(resolveRoute('/register', { ...user, role }), { redirect: '/' + role });
  }
  assert.deepEqual(resolveRoute('/register', null), { page: 'register' });
  assert.deepEqual(resolveRoute('/missing', user), { page: 'notFound' });
});

test('API base URL and public credentials use exact Flask contract', async () => {
  const calls = [];
  const api = createApiClient({ baseUrl: 'http://127.0.0.1:5100/api/', fetchImpl: async (...args) => {
    calls.push(args);
    return response({ user }, 201);
  } });
  api.setToken('test-only-token');
  assert.deepEqual(await createAuthService(api).register(user.email, 'long-password'), user);
  assert.equal(calls[0][0], 'http://127.0.0.1:5100/api/auth/register');
  const options = calls[0][1];
  assert.equal(options.method, 'POST');
  assert.deepEqual(JSON.parse(options.body), { email: user.email, password: 'long-password' });
  assert.equal(options.headers.Authorization, undefined);
  assert.equal(options.credentials, 'omit');
  assert.equal(options.cache, 'no-store');
  assert.equal(options.redirect, 'error');
  for (const baseUrl of ['', '//example.invalid/api', 'file:///api']) assert.throws(() => createApiClient({ baseUrl }));
});

test('login gets current role from /me rather than decoding JWT', async () => {
  const calls = [];
  const api = createApiClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return response(url.endsWith('/login') ? { access_token: 'opaque-test-token', token_type: 'Bearer', expires_in: 900 } : { user: { ...user, role: 'doctor' } });
  } });
  const session = await createAuthService(api).login(user.email, 'long-password');
  assert.equal(session.user.role, 'doctor');
  assert.equal(session.expiresIn, 900);
  assert.equal(calls[0].url, '/api/auth/login');
  assert.equal(calls[1].url, '/api/auth/me');
  assert.equal(calls[1].options.headers.Authorization, 'Bearer opaque-test-token');
});

test('bad credentials do not trigger session expiry; authenticated 401 does', async () => {
  let expirations = 0;
  const api = createApiClient({ fetchImpl: async () => response({ error: { code: 401, message: 'Unauthorized' } }, 401) });
  api.setUnauthorizedHandler(() => { expirations++; api.setToken(null); });
  await assert.rejects(api.request('/auth/login', { method: 'POST' }), /Email or password is incorrect/);
  assert.equal(expirations, 0);
  api.setToken('test-token');
  await assert.rejects(api.request('/auth/me', { authenticated: true }), error => error.status === 401);
  assert.equal(expirations, 1);
  await assert.rejects(api.request('/auth/me', { authenticated: true }), error => error.status === 401);
});

test('stale request cannot expire a newer session', async () => {
  let finish;
  let expired = false;
  const api = createApiClient({ fetchImpl: () => new Promise(resolve => { finish = resolve; }) });
  api.setUnauthorizedHandler(() => { expired = true; });
  api.setToken('old');
  const pending = api.request('/auth/me', { authenticated: true });
  api.setToken('new');
  finish(response({}, 401));
  await assert.rejects(pending, ApiError);
  assert.equal(expired, false);
});

test('errors are consistent for Flask errors, non-JSON proxies, malformed success and network failure', async () => {
  for (const status of [400, 403, 409, 413, 429, 500, 503]) {
    const api = createApiClient({ fetchImpl: async () => response({ error: { code: status, message: 'sensitive-unexpected-content' } }, status) });
    await assert.rejects(api.request('/auth/register'), error => error instanceof ApiError && error.status === status && !error.message.includes('sensitive'));
  }
  const html = createApiClient({ fetchImpl: async () => new Response('<html>proxy</html>', { status: 502 }) });
  await assert.rejects(html.request('/auth/login'), error => error.status === 502);
  const malformed = createApiClient({ fetchImpl: async () => new Response('not JSON') });
  await assert.rejects(malformed.request('/auth/me'), /unexpected response/);
  const network = createApiClient({ fetchImpl: async () => { throw new Error('private transport details'); } });
  await assert.rejects(network.request('/auth/me'), /Unable to connect/);
  const aborted = createApiClient({ fetchImpl: async () => { throw new DOMException('Aborted', 'AbortError'); } });
  await assert.rejects(aborted.request('/auth/me'), error => error.name === 'AbortError');
});

test('failed identity and unknown roles discard login token; malformed login never establishes a session', async () => {
  for (const identity of [{ user: { ...user, role: 'superuser' } }, { user: { ...user, id: 0 } }, {}]) {
    const api = createApiClient({ fetchImpl: async url => response(url.endsWith('/login') ? { access_token: 'test-token', token_type: 'Bearer', expires_in: 900 } : identity) });
    await assert.rejects(createAuthService(api).login(user.email, 'long-password'), /unexpected account/);
    await assert.rejects(api.request('/auth/me', { authenticated: true }), error => error.status === 401);
  }
  const api = createApiClient({ fetchImpl: async () => response({ access_token: 'test-token', token_type: 'Basic', expires_in: 900 }) });
  await assert.rejects(createAuthService(api).login(user.email, 'long-password'), /unexpected sign-in/);
  await assert.rejects(api.request('/auth/me', { authenticated: true }), error => error.status === 401);
});
