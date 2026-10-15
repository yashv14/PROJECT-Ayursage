import assert from 'node:assert/strict';
import test from 'node:test';
import { prepareAssessment, inputFeatures, categoricalInputs, numericInputs, emptyInputs } from '../src/patient/assessmentFields.js';
import { createPatientWorkspace } from '../src/patient/workspace.js';
import { createPatientService } from '../src/services/patients.js';
import { createApiClient } from '../src/services/api.js';
import { resolveRoute } from '../src/routing/routes.js';

export const filledValues = () => Object.fromEntries(inputFeatures.map(name => [name, numericInputs.includes(name) ? '1.5' : ' entered text ']));
const row = { id: 2, patient_id: 1, recorded_by_user_id: 1, created_at: '2026-10-13T10:00:00', inputs: prepareAssessment(filledValues()).payload.inputs, notes: null };
const profile = { id: 1, owner_user_id: 1 };
const response = (data, status = 200) => new Response(JSON.stringify(data), { status });
function serviceFixture(overrides = {}) {
  return { getProfile: async () => profile, createProfile: async () => profile,
    createAssessment: async () => ({ assessment: row }), getHistory: async () => ({ assessments: [row], nextAfterId: null }),
    getAssessment: async () => row, ...overrides };
}

test('all twelve fields are required, exact types preserve explicit zero and supplied text', () => {
  assert.equal(inputFeatures.length, 12);
  assert.equal(Object.keys(prepareAssessment(emptyInputs()).errors).length, 12);
  const values = filledValues();
  values['BP Systolic'] = '0';
  const result = prepareAssessment(values, ' notes\n ');
  assert.deepEqual(result.errors, {});
  assert.deepEqual(Object.keys(result.payload.inputs), inputFeatures);
  assert.equal(result.payload.inputs.Disease, ' entered text ');
  assert.equal(result.payload.inputs['BP Systolic'], 0);
  assert.equal(result.payload.notes, ' notes\n ');
  for (const name of inputFeatures) {
    const incomplete = { ...values };
    delete incomplete[name];
    assert.ok(prepareAssessment(incomplete).errors[name]);
    assert.equal(prepareAssessment(incomplete).payload, null);
  }
  for (const raw of ['', ' ', 'NaN', 'Infinity', '1e999', '0x10', true, null]) {
    assert.ok(prepareAssessment({ ...values, 'Pulse Rate': raw }).errors['Pulse Rate']);
  }
  for (const raw of ['-1', '0', '1.25', '1e2']) {
    assert.equal(prepareAssessment({ ...values, 'Pulse Rate': raw }).payload.inputs['Pulse Rate'], Number(raw));
  }
  for (const raw of ['', ' ', 'x'.repeat(257), '\0', '\ud800', 1]) assert.ok(prepareAssessment({ ...values, Disease: raw }).errors.Disease);
  assert.equal(prepareAssessment({ ...values, Disease: '😀'.repeat(256) }).payload.inputs.Disease, '😀'.repeat(256));
  assert.ok(prepareAssessment(values, 'x'.repeat(4097)).errors.notes);
  assert.ok(prepareAssessment(values, '\ud800').errors.notes);
  assert.ok(prepareAssessment(values, '😀'.repeat(4096)).errors.form);
  assert.equal(Object.hasOwn(prepareAssessment(values).payload, 'notes'), false);
});

test('patient profile, assessment form, history and detail routes deny anonymous and privileged roles', () => {
  for (const path of ['/patient/profile', '/patient/assessments/new', '/patient/assessments', '/patient/assessments/2']) {
    assert.deepEqual(resolveRoute(path, null), { redirect: '/login' });
    for (const role of ['doctor', 'admin']) assert.deepEqual(resolveRoute(path, { role }), { page: 'forbidden' });
  }
  assert.deepEqual(resolveRoute('/patient/profile', { role: 'patient' }), { page: 'profile' });
  assert.deepEqual(resolveRoute('/patient/assessments/new', { role: 'patient' }), { page: 'newAssessment' });
  assert.deepEqual(resolveRoute('/patient/assessments', { role: 'patient' }), { page: 'history' });
  assert.deepEqual(resolveRoute('/patient/assessments/2', { role: 'patient' }), { page: 'detail', assessmentId: 2 });
  for (const id of ['0', '-1', '1e3', '999999999999999999', '2/extra']) assert.deepEqual(resolveRoute('/patient/assessments/' + id, { role: 'patient' }), { page: 'notFound' });
});

test('profile service sends only empty creation body and recovers a duplicate profile race', async () => {
  const calls = [];
  const api = createApiClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return url.endsWith('/me') ? response({ patient: profile }) : response({ error: { code: 409, message: 'Conflict' } }, 409);
  } });
  api.setToken('test-only-token');
  const service = createPatientService(api);
  assert.deepEqual(await service.getProfile(), profile);
  assert.deepEqual(await service.createProfile(), profile);
  assert.deepEqual(JSON.parse(calls[1].options.body), {});
  assert.equal(calls[1].url, '/api/patients');
  assert.equal(calls[1].options.headers.Authorization, 'Bearer test-only-token');
  assert.equal(calls[2].url, '/api/patients/me');
});

test('patient error copy handles missing profile, validation, 401, 403, unavailable service and network failures', async () => {
  for (const status of [400, 401, 403, 404, 413, 503]) {
    const api = createApiClient({ fetchImpl: async () => response({ error: { code: status, message: 'private-content' } }, status) });
    api.setToken('test-only-token');
    const service = createPatientService(api);
    if (status === 404) assert.equal(await service.getProfile(), null);
    else await assert.rejects(service.getProfile(), error => error.status === status && !/email and password|authentication service|private-content/.test(error.message));
    await assert.rejects(service.getAssessment(1, 2), error => error.status === status);
  }
  const api = createApiClient({ fetchImpl: async () => { throw new Error('private network info'); } });
  api.setToken('test-only-token');
  await assert.rejects(createPatientService(api).getHistory(1), /Unable to connect/);
});

test('malformed patient responses fail closed and null legacy inputs are preserved', async () => {
  for (const data of [{ patient: { id: 0, owner_user_id: 1 } }, { assessment: { ...row, patient_id: 2 } },
    { assessment: { ...row, inputs: {} } }, { assessments: [row], next_after_id: 1 }]) {
    const api = createApiClient({ fetchImpl: async () => response(data) });
    api.setToken('test-only-token');
    const service = createPatientService(api);
    const operation = data.patient ? service.getProfile() : data.assessment ? service.getAssessment(1, 2) : service.getHistory(1);
    await assert.rejects(operation, /unexpected response/);
  }
  const api = createApiClient({ fetchImpl: async () => response({ assessment: { ...row, inputs: null } }) });
  api.setToken('test-only-token');
  assert.equal((await createPatientService(api).getAssessment(1, 2)).inputs, null);
});

test('profile loading, missing state, creation success and retry after failed requests', async () => {
  let missing = true;
  let fail = false;
  const store = createPatientWorkspace(serviceFixture({ getProfile: async () => {
    if (fail) throw new Error('The patient service is unavailable.');
    return missing ? null : profile;
  }, createProfile: async () => { missing = false; return profile; } }));
  const loading = store.loadProfile();
  assert.equal(store.getSnapshot().profile.status, 'loading');
  await loading;
  assert.equal(store.getSnapshot().profile.data, null);
  const creating = store.createProfile();
  assert.equal(store.getSnapshot().profile.status, 'creating');
  await creating;
  assert.deepEqual(store.getSnapshot().profile.data, profile);
  assert.match(store.getSnapshot().profile.notice, /ready/);
  fail = true;
  await store.loadProfile();
  assert.equal(store.getSnapshot().profile.status, 'error');
  fail = false;
  await store.loadProfile();
  assert.equal(store.getSnapshot().profile.status, 'ready');
});

test('submission validates before requests, prevents duplicate writes, retains drafts after failure and records success', async () => {
  let complete;
  let writes = 0;
  const store = createPatientWorkspace(serviceFixture({ createAssessment: (_id, payload) => {
    writes++;
    assert.equal(payload.inputs['BP Systolic'], 0);
    return new Promise(resolve => { complete = resolve; });
  } }));
  await store.loadProfile();
  await store.submit();
  assert.equal(writes, 0);
  assert.equal(store.getSnapshot().form.status, 'invalid');
  for (const [name, value] of Object.entries(filledValues())) store.changeField(name, name === 'BP Systolic' ? '0' : value);
  const pending = store.submit();
  assert.equal(store.getSnapshot().form.status, 'saving');
  await store.submit();
  assert.equal(writes, 1);
  complete({ assessment: row });
  await pending;
  assert.equal(store.getSnapshot().form.saved.id, row.id);
  store.resetForm();
  assert.deepEqual(store.getSnapshot().form.values, emptyInputs());
  for (const message of ['Unable to connect to AYUR-SAGE.', 'You do not have permission.', 'The request was rejected.']) {
    const failed = createPatientWorkspace(serviceFixture({ createAssessment: async () => { throw new Error(message); } }));
    await failed.loadProfile();
    for (const [name, value] of Object.entries(filledValues())) failed.changeField(name, value);
    await failed.submit();
    assert.equal(failed.getSnapshot().form.error, message);
    assert.deepEqual(failed.getSnapshot().form.values, filledValues());
    assert.equal(failed.getSnapshot().form.saved, null);
  }
});

test('history handles empty state, pagination, failed load-more retry and detail errors', async () => {
  let fail = false;
  let empty = true;
  const cursors = [];
  const store = createPatientWorkspace(serviceFixture({ getHistory: async (_id, cursor) => {
    cursors.push(cursor);
    if (fail) throw new Error('Unable to connect.');
    if (empty) return { assessments: [], nextAfterId: null };
    return cursor === 0 ? { assessments: [row], nextAfterId: 2 } : { assessments: [{ ...row, id: 3 }], nextAfterId: null };
  }, getAssessment: async (_id, id) => { if (fail) throw new Error('The assessment is unavailable.'); return { ...row, id }; } }));
  await store.loadProfile();
  await store.loadHistory();
  assert.equal(store.getSnapshot().history.items.length, 0);
  assert.equal(store.getSnapshot().history.status, 'ready');
  empty = false;
  await store.loadHistory();
  fail = true;
  await store.loadHistory(true);
  assert.equal(store.getSnapshot().history.items.length, 1);
  assert.equal(store.getSnapshot().history.nextAfterId, 2);
  assert.equal(store.getSnapshot().history.status, 'error');
  fail = false;
  await store.loadHistory(true);
  assert.deepEqual(store.getSnapshot().history.items.map(item => item.id), [2, 3]);
  assert.deepEqual(cursors, [0, 0, 2, 2]);
  await store.loadDetail(2);
  assert.equal(store.getSnapshot().detail.data.id, 2);
  fail = true;
  await store.loadDetail(3);
  assert.equal(store.getSnapshot().detail.data, null);
  assert.match(store.getSnapshot().detail.error, /unavailable/);
});

test('unmounted patient workspace ignores late responses and stale detail loads cannot overwrite the newest request', async () => {
  let resolveProfile;
  const store = createPatientWorkspace(serviceFixture({ getProfile: () => new Promise(resolve => { resolveProfile = resolve; }) }));
  const disconnect = store.connect();
  const pending = store.loadProfile();
  disconnect();
  resolveProfile(profile);
  await pending;
  assert.equal(store.getSnapshot().profile.data, null);
  const resolvers = {};
  const detailStore = createPatientWorkspace(serviceFixture({ getAssessment: (_id, id) => new Promise(resolve => { resolvers[id] = resolve; }) }));
  await detailStore.loadProfile();
  const first = detailStore.loadDetail(2);
  const second = detailStore.loadDetail(3);
  resolvers[3]({ ...row, id: 3 });
  await second;
  resolvers[2](row);
  await first;
  assert.equal(detailStore.getSnapshot().detail.data.id, 3);
});

const accessGrant = (changes = {}) => ({ id: 4, patient_id: 1, doctor_user_id: 8,
  issuer_user_id: 9, consent_owner_user_id: 1, consent_reference: 'synthetic-consent',
  scope: 'assessment_read', status: 'issued', issued_at: '2026-10-14T10:00:00Z',
  expires_at: '2026-11-13T10:00:00Z', revoked_at: null, revoked_by_user_id: null, ...changes });
const revokedGrant = (changes = {}) => accessGrant({ status: 'revoked', revoked_at: '2026-10-15T10:00:00Z', revoked_by_user_id: 1, ...changes });

test('grant client lists and revokes only the selected patient/grant with bearer authentication and an empty body', async () => {
  const calls = [];
  const api = createApiClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return response(options.method === 'POST' ? { grant: revokedGrant() } : { grants: [accessGrant()], next_after_id: 4 });
  } });
  api.setToken('grant-test-token');
  const service = createPatientService(api);
  assert.deepEqual(await service.getAccessGrants(1), { grants: [accessGrant()], nextAfterId: 4 });
  assert.deepEqual(await service.revokeAccessGrant(1, 4), revokedGrant());
  assert.equal(calls[0].url, '/api/patients/1/doctor-access-grants?after_id=0');
  assert.equal(calls[1].url, '/api/patients/1/doctor-access-grants/4/revoke');
  assert.equal(calls[1].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls[1].options.body), {});
  assert.ok(calls.every(call => call.options.headers.Authorization === 'Bearer grant-test-token'));
  const count = calls.length;
  await assert.rejects(service.getAccessGrants(0));
  await assert.rejects(service.getAccessGrants(1, -1));
  await assert.rejects(service.revokeAccessGrant(1, 0));
  assert.equal(calls.length, count);
});

test('grant responses reject wrong patient, invalid state, inconsistent revocation and malformed pagination', async () => {
  const invalidRows = [accessGrant({ patient_id: 2 }), accessGrant({ scope: 'assessment_write' }),
    accessGrant({ status: 'approved' }), accessGrant({ expires_at: 'not-a-date' }),
    accessGrant({ revoked_at: '2026-10-15T10:00:00Z' }), revokedGrant({ revoked_by_user_id: null }),
    accessGrant({ consent_reference: '' })];
  for (const grant of invalidRows) {
    const api = createApiClient({ fetchImpl: async () => response({ grants: [grant], next_after_id: null }) });
    api.setToken('fixture');
    await assert.rejects(createPatientService(api).getAccessGrants(1), /unexpected response/);
  }
  for (const data of [{ grants: [], next_after_id: 4 }, { grants: [accessGrant()], next_after_id: 3 },
    { grants: [accessGrant(), accessGrant()], next_after_id: null }, { grants: null, next_after_id: null }]) {
    const api = createApiClient({ fetchImpl: async () => response(data) });
    api.setToken('fixture');
    await assert.rejects(createPatientService(api).getAccessGrants(1), /unexpected response/);
  }
  for (const grant of [accessGrant(), revokedGrant({ id: 5 }), revokedGrant({ patient_id: 2 })]) {
    const api = createApiClient({ fetchImpl: async () => response({ grant }) });
    api.setToken('fixture');
    await assert.rejects(createPatientService(api).revokeAccessGrant(1, 4), /unexpected response/);
  }
});

test('grant authentication and server failures preserve safe existing session/error handling', async () => {
  for (const status of [401, 403, 404, 503]) {
    let expired = false;
    const api = createApiClient({ fetchImpl: async () => response({ error: { code: status, message: 'private-server-content' } }, status) });
    api.setToken('fixture');
    api.setUnauthorizedHandler(() => { expired = true; });
    const service = createPatientService(api);
    await assert.rejects(service.getAccessGrants(1), error => error.status === status && !error.message.includes('private-server-content'));
    await assert.rejects(service.revokeAccessGrant(1, 4), error => error.status === status);
    assert.equal(expired, status === 401);
  }
});

test('grant history paginates, retains rows on failed load-more and retries the same cursor', async () => {
  let fail = false;
  const cursors = [];
  const store = createPatientWorkspace(serviceFixture({ getAccessGrants: async (_id, cursor) => {
    cursors.push(cursor);
    if (fail) throw new Error('Unable to connect.');
    return cursor === 0 ? { grants: [accessGrant()], nextAfterId: 4 }
      : { grants: [accessGrant({ id: 5, status: 'expired' })], nextAfterId: null };
  } }));
  await store.loadGrants();
  assert.deepEqual(cursors, []);
  await store.loadProfile();
  await store.loadGrants();
  fail = true;
  await store.loadGrants(true);
  assert.equal(store.getSnapshot().grants.items.length, 1);
  assert.equal(store.getSnapshot().grants.nextAfterId, 4);
  assert.equal(store.getSnapshot().grants.status, 'error');
  fail = false;
  await store.loadGrants(true);
  assert.deepEqual(store.getSnapshot().grants.items.map(row => row.id), [4, 5]);
  assert.deepEqual(cursors, [0, 4, 4]);
  await store.loadGrants(true);
  assert.deepEqual(cursors, [0, 4, 4]);
});

test('revocation requires confirmation, blocks duplicate writes and changes only the returned grant after success', async () => {
  let finish;
  let writes = 0;
  const store = createPatientWorkspace(serviceFixture({
    getAccessGrants: async () => ({ grants: [accessGrant(), accessGrant({ id: 5 })], nextAfterId: null }),
    revokeAccessGrant: (patientId, id) => { assert.equal(patientId, 1); assert.equal(id, 4); writes++; return new Promise(resolve => { finish = resolve; }); },
  }));
  await store.loadProfile(); await store.loadGrants();
  await store.revokeGrant(4);
  assert.equal(writes, 0);
  store.confirmGrantRevocation(4); store.cancelGrantRevocation();
  await store.revokeGrant(4);
  assert.equal(writes, 0);
  store.confirmGrantRevocation(4);
  const pending = store.revokeGrant(4);
  assert.equal(store.getSnapshot().grants.status, 'revoking');
  assert.equal(store.getSnapshot().grants.items[0].status, 'issued');
  await store.revokeGrant(4); await store.loadGrants();
  assert.equal(writes, 1);
  finish(revokedGrant()); await pending;
  assert.equal(store.getSnapshot().grants.items[0].status, 'revoked');
  assert.equal(store.getSnapshot().grants.items[1].status, 'issued');
  assert.equal(store.getSnapshot().grants.confirmingId, null);
  assert.match(store.getSnapshot().grants.notice, /revoked/);
});

test('failed revocation retains the active grant and confirmation for explicit retry', async () => {
  let fail = true;
  const store = createPatientWorkspace(serviceFixture({
    getAccessGrants: async () => ({ grants: [accessGrant(), accessGrant({ id: 5, status: 'expired' })], nextAfterId: null }),
    revokeAccessGrant: async () => { if (fail) throw new Error('Access unavailable.'); return revokedGrant(); },
  }));
  await store.loadProfile(); await store.loadGrants();
  store.confirmGrantRevocation(5);
  assert.equal(store.getSnapshot().grants.confirmingId, null);
  store.confirmGrantRevocation(4); await store.revokeGrant(4);
  assert.equal(store.getSnapshot().grants.items[0].status, 'issued');
  assert.equal(store.getSnapshot().grants.confirmingId, 4);
  assert.equal(store.getSnapshot().grants.notice, '');
  assert.match(store.getSnapshot().grants.error, /unavailable/);
  fail = false; await store.revokeGrant(4);
  assert.equal(store.getSnapshot().grants.items[0].status, 'revoked');
});

test('profile reload and workspace unmount discard late grant responses', async () => {
  let finish;
  const store = createPatientWorkspace(serviceFixture({ getAccessGrants: () => new Promise(resolve => { finish = resolve; }) }));
  const disconnect = store.connect();
  await store.loadProfile();
  const first = store.loadGrants();
  await store.loadProfile();
  finish({ grants: [accessGrant()], nextAfterId: null }); await first;
  assert.deepEqual(store.getSnapshot().grants.items, []);
  const second = store.loadGrants();
  disconnect(); finish({ grants: [accessGrant()], nextAfterId: null }); await second;
  assert.deepEqual(store.getSnapshot().grants.items, []);
});
