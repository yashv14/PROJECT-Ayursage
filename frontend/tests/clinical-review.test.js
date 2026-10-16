import assert from 'node:assert/strict';
import test from 'node:test';
import { createReviewService, createReviewStore } from '../src/doctor/review.js';
import { createApiClient, ApiError } from '../src/services/api.js';
import { outputTargets } from '../src/patient/assessmentFields.js';

const initial = () => ({ assessment_id: 2, state: 'pending_review', version: 0, can_review: true, reviews: [] });
const payload = () => ({ decision: 'approved', clinical_notes: 'SYNTHETIC doctor notes',
  recommendations: Object.fromEntries(outputTargets.map(name => [name, 'SYNTHETIC human-authored recommendation'])),
  prescriptions: [{ medication: 'SYNTHETIC medication', dose: 'SYNTHETIC dose', route: 'SYNTHETIC route',
    frequency: 'SYNTHETIC frequency', duration: 'SYNTHETIC duration', instructions: '' }] });
function saved() { return { ...initial(), state: 'approved', version: 1,
  reviews: [{ id: 3, sequence: 1, actor_user_id: 7, from_state: 'pending_review', decided_at: '2026-10-16T10:00:00Z', origin: 'doctor_entered', ...payload() }] }; }

test('review client uses existing JWT GET/POST and validates persisted doctor content', async () => {
  let record = initial(); const calls = [];
  const api = createApiClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    if (options.method === 'POST') record = saved();
    return new Response(JSON.stringify(record));
  } });
  api.setToken('synthetic-doctor-token');
  const service = createReviewService(api);
  assert.equal((await service.get(1, 2)).version, 0);
  assert.deepEqual(await service.save(1, 2, { ...payload(), expected_version: 0 }), saved());
  const reloaded = createReviewStore(service, 1, 2); await reloaded.load();
  assert.deepEqual(reloaded.getSnapshot().data, saved());
  assert.ok(calls.every(({ url, options }) => url === '/api/patients/1/assessments/2/reviews'
    && options.headers.Authorization === 'Bearer synthetic-doctor-token' && options.cache === 'no-store'));
  assert.deepEqual(JSON.parse(calls[1].options.body), { ...payload(), expected_version: 0 });
});

test('review save uses server version, suppresses duplicates and has no optimistic success', async () => {
  let finish, calls = 0, submitted;
  const store = createReviewStore({ get: async () => initial(), save: async (_p, _a, body) => {
    calls++; submitted = body; return new Promise(resolve => { finish = resolve; });
  } }, 1, 2);
  await store.load(); const pending = store.save({ ...payload(), expected_version: 999 });
  assert.equal(store.getSnapshot().status, 'saving'); assert.equal(store.getSnapshot().data.version, 0);
  await store.save(payload()); assert.equal(calls, 1); assert.equal(submitted.expected_version, 0);
  finish(saved()); await pending;
  assert.equal(store.getSnapshot().data.state, 'approved'); assert.match(store.getSnapshot().notice, /saved/);
  await store.save(payload()); assert.equal(calls, 1);
});

test('read-only permission cannot invoke save', async () => {
  let calls = 0;
  const store = createReviewStore({ get: async () => ({ ...initial(), can_review: false }), save: () => { calls++; } }, 1, 2);
  await store.load(); await store.save(payload()); assert.equal(calls, 0);
});

test('failed writes clear clinical review data and denial triggers assessment recheck', async () => {
  for (const status of [400, 401, 403, 409, 503]) {
    let rechecks = 0;
    const store = createReviewStore({ get: async () => initial(), save: async () => { throw new ApiError('Rejected', status); } }, 1, 2,
      { onAccessDenied: () => { rechecks++; } });
    await store.load(); await store.save(payload());
    assert.equal(store.getSnapshot().data, null); assert.equal(store.getSnapshot().status, 'error');
    assert.equal(rechecks, [401, 403].includes(status) ? 1 : 0);
    await store.load(); assert.equal(store.getSnapshot().data.version, 0);
  }
});

test('unmount discards late clinical data and reconnect can reload', async () => {
  let finish;
  const store = createReviewStore({ get: () => new Promise(resolve => { finish = resolve; }) }, 1, 2);
  const disconnect = store.connect(); const pending = store.load(); disconnect(); finish(saved()); await pending;
  assert.equal(store.getSnapshot().data, null);
  store.connect(); const reload = store.load(); finish(initial()); await reload;
  assert.equal(store.getSnapshot().data.version, 0);
});

test('malformed review response and model-origin content are rejected', async () => {
  const corruptions = [data => { data.assessment_id = 9; }, data => { data.version = 0; },
    data => { data.reviews[0].origin = 'V17'; }, data => { data.reviews[0].recommendations = {}; },
    data => { data.reviews[0].prescriptions[0].dose = false; }, data => { data.reviews[0].actor_user_id = null; },
    data => { data.reviews[0].decided_at = 'bad'; }, data => { data.reviews[0].from_state = 'approved'; }];
  for (const corrupt of corruptions) {
    const data = saved(); corrupt(data);
    const service = createReviewService({ request: async () => data });
    await assert.rejects(service.get(1, 2), /invalid response/);
  }
});
