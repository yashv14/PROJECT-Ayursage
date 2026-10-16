import assert from 'node:assert/strict';
import test from 'node:test';
import { createGrantAdmin, grantId } from '../src/admin/grants.js';
import { createPatientService } from '../src/services/patients.js';
import { createApiClient, ApiError } from '../src/services/api.js';
import { resolveRoute } from '../src/routing/routes.js';

const row = { id: 1, patient_id: 4, doctor_user_id: 7, issuer_user_id: 8, consent_owner_user_id: 9,
  scope: 'assessment_read', allow_review: false, status: 'issued', consent_reference: 'synthetic-consent',
  issued_at: '2026-10-16T10:00:00Z', expires_at: '2026-11-15T10:00:00Z', revoked_by_user_id: null, revoked_at: null };
const candidate = { doctorId: '7', reference: 'synthetic-consent', allowReview: false, attested: true };
const service = changes => ({ getAccessGrants: async () => ({ grants: [row], nextAfterId: null }),
  issueAccessGrant: async () => row, revokeAccessGrant: async () => ({ ...row, status: 'revoked' }), ...changes });

test('administrator grant route is guarded and IDs reject coercion/overflow', () => {
  assert.deepEqual(resolveRoute('/admin/grants', null), { redirect: '/login' });
  assert.deepEqual(resolveRoute('/admin/grants', { role: 'admin' }), { page: 'adminGrants' });
  for (const role of ['patient','doctor','receptionist']) assert.deepEqual(resolveRoute('/admin/grants', { role }), { page: 'forbidden' });
  assert.equal(grantId('2147483647'), 2147483647);
  for (const value of [null, true, 1, '01','0','-1','1.0','1e2','2147483648','']) assert.throws(() => grantId(value));
});

test('issue client sends exact authenticated contract and checks returned patient/doctor/permission', async () => {
  const calls = [];
  const api = createApiClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options }); return new Response(JSON.stringify({ grant: row }), { status: 201 });
  } });
  api.setToken('synthetic-admin-token');
  const client = createPatientService(api);
  const body = { doctor_user_id: 7, consent_reference: 'synthetic-consent', allow_review: false };
  assert.deepEqual(await client.issueAccessGrant(4, body), row);
  assert.equal(calls[0].url, '/api/patients/4/doctor-access-grants');
  assert.equal(calls[0].options.headers.Authorization, 'Bearer synthetic-admin-token');
  assert.equal(calls[0].options.method, 'POST'); assert.deepEqual(JSON.parse(calls[0].options.body), body);
  await assert.rejects(client.issueAccessGrant(4, { ...body, allow_review: 'true' }));
  await assert.rejects(client.issueAccessGrant(4, { ...body, expires_at: '2099' }));
  await assert.rejects(client.issueAccessGrant(4, { ...body, doctor_user_id: 5 }));
  assert.equal(calls.length, 2);
});

test('grant conflict and permission errors are contextual, and 401 retains session handling', async () => {
  for (const status of [400, 401, 403, 404, 409, 503]) {
    let expired = false;
    const api = createApiClient({ fetchImpl: async () => new Response(JSON.stringify({ error: { code: status } }), { status }) });
    api.setToken('synthetic'); api.setUnauthorizedHandler(() => { expired = true; });
    await assert.rejects(createPatientService(api).issueAccessGrant(4, { doctor_user_id: 7, consent_reference: 'synthetic', allow_review: false }), error => error.status === status && !/profile already exists|account with this email/.test(error.message));
    assert.equal(expired, status === 401);
  }
});

test('issuance needs a loaded patient, consent attestation and separate confirmation; duplicate clicks suppressed', async () => {
  let finish, calls = 0;
  const store = createGrantAdmin(service({ issueAccessGrant: (_id, body) => {
    calls++; assert.equal(body.allow_review, false); return new Promise(resolve => { finish = resolve; });
  } }));
  store.prepareIssue(candidate); assert.equal(store.getSnapshot().issueCandidate, null);
  await store.load('4'); store.prepareIssue({ ...candidate, attested: false });
  assert.equal(store.getSnapshot().issueCandidate, null);
  store.prepareIssue(candidate); assert.equal(calls, 0);
  const pending = store.issue(); await store.issue(); assert.equal(calls, 1);
  assert.equal(store.getSnapshot().notice, ''); assert.deepEqual(store.getSnapshot().items, []);
  finish(row); await pending; assert.match(store.getSnapshot().notice, /issued/);
  assert.equal(store.getSnapshot().issueCandidate, null);
});

test('patient changes discard prior confirmations and pagination uses exact server cursor', async () => {
  const calls = [];
  const store = createGrantAdmin(service({ getAccessGrants: async (id, cursor) => {
    calls.push([id,cursor]); return { grants: [{ ...row, id: cursor ? 2 : 1, patient_id: id }], nextAfterId: cursor ? null : 1 };
  } }));
  await store.load('4'); store.prepareIssue(candidate); await store.load('5');
  assert.equal(store.getSnapshot().issueCandidate, null); assert.equal(store.getSnapshot().patientId, 5);
  await store.load('5', true); assert.deepEqual(calls, [[4,0],[5,0],[5,1]]);
  assert.deepEqual(store.getSnapshot().items.map(r => r.id), [1,2]);
});

test('revocation requires confirmation and cancellation sends no write', async () => {
  let calls = 0;
  const store = createGrantAdmin(service({ revokeAccessGrant: async () => { calls++; return { ...row, status: 'revoked' }; } }));
  await store.load('4'); await store.revoke(1); assert.equal(calls, 0);
  store.confirmRevoke(1); store.cancel(); await store.revoke(1); assert.equal(calls, 0);
  store.confirmRevoke(1); await store.revoke(1); assert.equal(calls, 1);
  assert.equal(store.getSnapshot().items[0].status, 'revoked');
});

test('permission/network failures clear stale grant metadata and unmount ignores late responses', async () => {
  let fail = false;
  const store = createGrantAdmin(service({ getAccessGrants: async () => {
    if (fail) throw new ApiError('Forbidden',403); return { grants: [row], nextAfterId: null };
  } }));
  await store.load('4'); store.prepareIssue(candidate); fail = true; await store.load('4');
  assert.deepEqual(store.getSnapshot().items, []); assert.equal(store.getSnapshot().issueCandidate,null);
  assert.match(store.getSnapshot().error,/Administrator role alone is insufficient/);
  let finish;
  const pendingStore = createGrantAdmin(service({ getAccessGrants: () => new Promise(resolve => { finish = resolve; }) }));
  const disconnect = pendingStore.connect(); const pending = pendingStore.load('4'); disconnect();
  finish({ grants: [row], nextAfterId: null }); await pending;
  assert.equal(pendingStore.getSnapshot().patientId, null); assert.deepEqual(pendingStore.getSnapshot().items, []);
});
