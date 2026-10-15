import assert from 'node:assert/strict';
import test from 'node:test';
import { createSession } from '../src/auth/session.js';

function fixture(login) {
  let token = null;
  let unauthorized;
  let expire;
  let delay;
  let cancelled = false;
  const api = { setToken: value => { token = value; }, setUnauthorizedHandler: handler => { unauthorized = handler; } };
  const service = { register: async () => {}, login: login || (async () => {
    token = 'test-token';
    return { user: { id: 1, email: 'p@example.invalid', role: 'patient' }, expiresIn: 60 };
  }) };
  const session = createSession(api, service, { schedule: (callback, ms) => { expire = callback; delay = ms; return 1; }, cancel: id => { if (id === 1) cancelled = true; } });
  session.connect();
  return { session, expire: () => expire(), unauthorized: () => unauthorized(), token: () => token, delay: () => delay, cancelled: () => cancelled };
}

test('session expiry clears identity and token and notifies the UI', async () => {
  const f = fixture();
  let changes = 0;
  const unsubscribe = f.session.subscribe(() => { changes++; });
  await f.session.login('p@example.invalid', 'test-password');
  assert.equal(f.session.getSnapshot().user.role, 'patient');
  assert.equal(f.delay(), 60000);
  assert.equal(f.session.getSnapshot().busy, false);
  f.expire();
  assert.equal(f.session.getSnapshot().user, null);
  assert.equal(f.token(), null);
  assert.match(f.session.getSnapshot().notice, /expired/);
  assert.ok(changes >= 3);
  unsubscribe();
});

test('logout, authenticated failure and provider cleanup clear session material', async () => {
  const f = fixture();
  await f.session.login('p@example.invalid', 'test-password');
  f.session.logout('You have signed out.');
  assert.equal(f.token(), null);
  assert.equal(f.session.getSnapshot().user, null);
  assert.equal(f.cancelled(), true);
  assert.equal(f.session.getSnapshot().notice, 'You have signed out.');
  await f.session.login('p@example.invalid', 'test-password');
  f.unauthorized();
  assert.equal(f.session.getSnapshot().user, null);
  await f.session.login('p@example.invalid', 'test-password');
  f.session.connect()();
  assert.equal(f.token(), null);
});

test('failed login exits loading state, and logout while login is pending cannot resurrect identity', async () => {
  const failed = fixture(async () => { throw new Error('Login failed'); });
  await assert.rejects(failed.session.login('p@example.invalid', 'bad'), /Login failed/);
  assert.equal(failed.session.getSnapshot().busy, false);
  assert.equal(failed.session.getSnapshot().user, null);
  let complete;
  let attempts = 0;
  const pending = fixture(() => { attempts++; return new Promise(resolve => { complete = resolve; }); });
  const result = pending.session.login('p@example.invalid', 'test-password');
  assert.equal(pending.session.getSnapshot().busy, true);
  await pending.session.login('p@example.invalid', 'test-password');
  assert.equal(attempts, 1);
  pending.session.logout();
  complete({ user: { role: 'doctor' }, expiresIn: 60 });
  await result;
  assert.equal(pending.session.getSnapshot().user, null);
  assert.equal(pending.session.getSnapshot().busy, false);
});
