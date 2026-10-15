import assert from 'node:assert/strict';
import test from 'node:test';
import { createDoctorViewer } from '../src/doctor/workspace.js';
import { createApiClient, ApiError } from '../src/services/api.js';
import { createPatientService } from '../src/services/patients.js';
import { resolveRoute } from '../src/routing/routes.js';

const row = { id: 2, patient_id: 1, recorded_by_user_id: 7, created_at: '2026-10-15T10:00:00', inputs: null, notes: 'Synthetic patient notes' };
const response = (data, status = 200) => new Response(JSON.stringify(data), { status });
const fixture = overrides => ({ getHistory: async () => ({ assessments: [row], nextAfterId: null }),
  getAssessment: async () => row, ...overrides });

test('doctor viewer routes require the doctor role and bounded nested IDs', () => {
  for (const path of ['/doctor/assessments', '/doctor/patients/1/assessments', '/doctor/patients/1/assessments/2']) {
    assert.deepEqual(resolveRoute(path, null), { redirect: '/login' });
    for (const role of ['patient', 'admin', 'receptionist']) assert.deepEqual(resolveRoute(path, { role }), { page: 'forbidden' });
    assert.equal(resolveRoute(path, { role: 'doctor' }).page, 'doctorViewer');
  }
  assert.deepEqual(resolveRoute('/doctor/patients/1/assessments/2', { role: 'doctor' }), { page: 'doctorViewer', patientId: 1, assessmentId: 2 });
  for (const path of ['/doctor/patients/0/assessments', '/doctor/patients/2147483648/assessments',
    '/doctor/patients/1/assessments/2147483648', '/doctor/patients/1/assessments/2/extra']) {
    assert.deepEqual(resolveRoute(path, { role: 'doctor' }), { page: 'notFound' });
  }
});

test('doctor viewer reuses only authenticated GET history/detail endpoints, with no profile or grant calls', async () => {
  const calls = [];
  const api = createApiClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return response(url.includes('?') ? { assessments: [row], next_after_id: null } : { assessment: row });
  } });
  api.setToken('doctor-fixture-token');
  const store = createDoctorViewer(createPatientService(api), 1);
  await store.loadHistory();
  assert.deepEqual(store.getSnapshot().items, [row]);
  await store.loadDetail(2);
  assert.deepEqual(store.getSnapshot().detail, row);
  assert.deepEqual(calls.map(call => call.url), ['/api/patients/1/assessments?limit=20&after_id=0', '/api/patients/1/assessments/2']);
  assert.ok(calls.every(call => call.options.method === 'GET' && call.options.headers.Authorization === 'Bearer doctor-fixture-token'
    && call.options.cache === 'no-store' && call.options.body === undefined));
});

test('history handles loading, duplicate refresh, pagination, empty results and fresh refresh', async () => {
  const cursors = [];
  let finish;
  const store = createDoctorViewer(fixture({ getHistory: (_id, cursor) => {
    cursors.push(cursor); return new Promise(resolve => { finish = resolve; });
  } }), 1);
  const first = store.loadHistory();
  assert.equal(store.getSnapshot().status, 'loading');
  await store.loadHistory();
  assert.deepEqual(cursors, [0]);
  finish({ assessments: [row], nextAfterId: 2 }); await first;
  const more = store.loadHistory(true);
  assert.deepEqual(store.getSnapshot().items, []);
  finish({ assessments: [{ ...row, id: 3 }], nextAfterId: null }); await more;
  assert.deepEqual(store.getSnapshot().items.map(item => item.id), [2, 3]);
  await store.loadHistory(true);
  const refresh = store.loadHistory();
  assert.deepEqual(store.getSnapshot().items, []);
  finish({ assessments: [], nextAfterId: null }); await refresh;
  assert.equal(store.getSnapshot().status, 'ready');
  assert.deepEqual(store.getSnapshot().items, []);
  assert.deepEqual(cursors, [0, 2, 0]);
});

test('a revoked/expired grant or session failure clears all previously displayed clinical data, including failed load-more', async () => {
  for (const status of [401, 403, 404, 503]) {
    let fail = false;
    let expired = false;
    const api = createApiClient({ fetchImpl: async url => fail
      ? response({ error: { code: status, message: 'private error' } }, status)
      : response(url.includes('?') ? { assessments: [row], next_after_id: 2 } : { assessment: row }) });
    api.setToken('doctor-fixture-token');
    api.setUnauthorizedHandler(() => { expired = true; });
    const store = createDoctorViewer(createPatientService(api), 1);
    await store.loadHistory();
    fail = true;
    await store.loadHistory(true);
    assert.equal(store.getSnapshot().status, 'error');
    assert.equal(store.getSnapshot().errorStatus, status);
    assert.deepEqual(store.getSnapshot().items, []);
    assert.equal(store.getSnapshot().detail, null);
    assert.equal(store.getSnapshot().nextAfterId, null);
    assert.equal(expired, status === 401);
    assert.ok(!store.getSnapshot().error.includes('private error'));
    if (status === 403) assert.match(store.getSnapshot().error, /Access denied.*expired or revoked/);
    fail = false; await store.loadDetail(2);
    fail = true; await store.loadDetail(2);
    assert.equal(store.getSnapshot().detail, null);
    assert.deepEqual(store.getSnapshot().items, []);
  }
});

test('network failure retries from a fresh history request without restoring stale results', async () => {
  let fail = true;
  const store = createDoctorViewer(fixture({ getHistory: async () => {
    if (fail) throw new ApiError('Unable to connect.');
    return { assessments: [row], nextAfterId: null };
  } }), 1);
  await store.loadHistory();
  assert.equal(store.getSnapshot().status, 'error');
  fail = false; await store.loadHistory();
  assert.deepEqual(store.getSnapshot().items, [row]);
});

test('malformed or mismatched assessment responses never become visible', async () => {
  for (const value of [{ ...row, patient_id: 9 }, { ...row, id: 3 }, { ...row, inputs: {} }]) {
    const api = createApiClient({ fetchImpl: async () => response({ assessment: value }) });
    api.setToken('fixture');
    const store = createDoctorViewer(createPatientService(api), 1);
    await store.loadDetail(2);
    assert.equal(store.getSnapshot().status, 'error');
    assert.equal(store.getSnapshot().detail, null);
  }
});

test('superseded, hidden and unmounted requests cannot repopulate clinical state', async () => {
  const resolvers = {};
  const store = createDoctorViewer(fixture({ getAssessment: (_id, id) => new Promise(resolve => { resolvers[id] = resolve; }) }), 1);
  const disconnect = store.connect();
  const first = store.loadDetail(2); const second = store.loadDetail(3);
  resolvers[3]({ ...row, id: 3 }); await second;
  resolvers[2](row); await first;
  assert.equal(store.getSnapshot().detail.id, 3);
  const hidden = store.loadDetail(4);
  store.clear(); resolvers[4]({ ...row, id: 4 }); await hidden;
  assert.equal(store.getSnapshot().detail, null);
  const pending = store.loadDetail(2);
  disconnect(); resolvers[2](row); await pending;
  assert.equal(store.getSnapshot().detail, null);
  assert.deepEqual(store.getSnapshot().items, []);
  await store.loadHistory();
  assert.equal(store.getSnapshot().status, 'idle');
});

test('directory client uses the authenticated endpoint and rejects extra fields, invalid IDs and cursors', async () => {
  const calls = [];
  let data = { patients: [{ id: 1 }], next_after_id: 1 };
  const api = createApiClient({ fetchImpl: async (url, options) => { calls.push({ url, options }); return response(data); } });
  api.setToken('doctor-token');
  const service = createPatientService(api);
  assert.deepEqual(await service.getAuthorizedPatients(), { patients: [{ id: 1 }], nextAfterId: 1 });
  assert.equal(calls[0].url, '/api/patients/authorized?after_id=0');
  assert.equal(calls[0].options.method, 'GET');
  assert.equal(calls[0].options.headers.Authorization, 'Bearer doctor-token');
  assert.equal(calls[0].options.cache, 'no-store');
  for (const invalid of [{ patients: [{ id: 0 }], next_after_id: null },
    { patients: [{ id: 1, email: 'unexpected@example.invalid' }], next_after_id: null },
    { patients: [{ id: 1 }, { id: 1 }], next_after_id: null },
    { patients: [], next_after_id: 2 }, { patients: [{ id: 1 }], next_after_id: 2 }]) {
    data = invalid;
    await assert.rejects(service.getAuthorizedPatients(), /unexpected response/);
  }
  await assert.rejects(service.getAuthorizedPatients(-1));
});

test('directory loading suppresses duplicates, pages replace stale IDs, refresh resets to first page and empty state works', async () => {
  let finish;
  const cursors = [];
  const store = createDoctorViewer({ getAuthorizedPatients: cursor => {
    cursors.push(cursor); return new Promise(resolve => { finish = resolve; });
  } });
  const first = store.loadDirectory();
  assert.equal(store.getSnapshot().status, 'loading');
  await store.loadDirectory();
  finish({ patients: [{ id: 1 }], nextAfterId: 1 }); await first;
  const second = store.loadDirectory(true);
  assert.deepEqual(store.getSnapshot().items, []);
  finish({ patients: [{ id: 2 }], nextAfterId: null }); await second;
  assert.deepEqual(store.getSnapshot().items, [{ id: 2 }]);
  await store.loadDirectory(true);
  const refresh = store.loadDirectory();
  finish({ patients: [], nextAfterId: null }); await refresh;
  assert.equal(store.getSnapshot().status, 'ready');
  assert.deepEqual(store.getSnapshot().items, []);
  assert.deepEqual(cursors, [0, 1, 0]);
});

test('directory failures and revoked grants leave no stale patients, retry rechecks scope, and 401 uses session expiry', async () => {
  for (const status of [401, 403, 503]) {
    let fail = false;
    let expired = false;
    let patients = [{ id: 1 }];
    const api = createApiClient({ fetchImpl: async () => fail
      ? response({ error: { code: status, message: 'private' } }, status)
      : response({ patients, next_after_id: null }) });
    api.setToken('fixture');
    api.setUnauthorizedHandler(() => { expired = true; });
    const store = createDoctorViewer(createPatientService(api));
    await store.loadDirectory();
    fail = true; await store.loadDirectory();
    assert.equal(store.getSnapshot().status, 'error');
    assert.deepEqual(store.getSnapshot().items, []);
    assert.equal(store.getSnapshot().detail, null);
    assert.equal(expired, status === 401);
    fail = false; patients = []; await store.loadDirectory();
    assert.deepEqual(store.getSnapshot().items, []);
  }
});

test('late directory results are discarded after hide or unmount', async () => {
  let finish;
  const store = createDoctorViewer({ getAuthorizedPatients: () => new Promise(resolve => { finish = resolve; }) });
  const disconnect = store.connect();
  const hidden = store.loadDirectory();
  store.clear(); finish({ patients: [{ id: 1 }], nextAfterId: null }); await hidden;
  assert.deepEqual(store.getSnapshot().items, []);
  const pending = store.loadDirectory();
  disconnect(); finish({ patients: [{ id: 1 }], nextAfterId: null }); await pending;
  assert.deepEqual(store.getSnapshot().items, []);
});
