import assert from 'node:assert/strict';
import test from 'node:test';
import { createApiClient, ApiError } from '../src/services/api.js';
import { createReportService, createReportStore } from '../src/services/reports.js';

const ready = { status: 'available', can_generate: false, report: { assessment_id: 2, version: 1 } };
test('report download validates same-resource signed link and sends capability in header with JWT, never URL', async () => {
  const calls = [];
  const api = createApiClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return url.endsWith('download-link') ? new Response(JSON.stringify({ url: '/patients/1/assessments/2/report/content#synthetic.signature', expires_in: 900 }))
      : new Response('%PDF-synthetic', { headers: { 'content-type': 'application/pdf' } });
  } });
  api.setToken('synthetic-jwt');
  const blob = await createReportService(api).download(1, 2);
  assert.equal(await blob.text(), '%PDF-synthetic');
  assert.ok(calls.every(call => !call.url.includes('signature') && call.options.headers.Authorization === 'Bearer synthetic-jwt' && call.options.cache === 'no-store'));
  assert.equal(calls[1].options.headers['X-Report-Link'], 'synthetic.signature');
});

test('malformed, foreign or wrong-expiry download links fail closed', async () => {
  for (const link of [{ url: 'https://foreign.invalid/#secret', expires_in: 900 },
    { url: '/patients/1/assessments/2/report/content#token', expires_in: 901 },
    { url: '/patients/1/assessments/3/report/content#token', expires_in: 900 }]) {
    let calls = 0;
    const service = createReportService({ request: async () => { calls++; return link; } });
    await assert.rejects(service.download(1, 2)); assert.equal(calls, 1);
  }
});

test('missing/denied/expired/unavailable results are contextual and discard old metadata', async () => {
  for (const status of [403,404,409,503]) {
    const service = createReportService({ request: async () => { throw new ApiError('private provider text', status); } });
    await assert.rejects(service.download(1, 2), error => error.status === status && !error.message.includes('private'));
  }
  let deny = false, rechecks = 0;
  const store = createReportStore({ get: async () => { if (deny) throw new ApiError('denied',403); return ready; } }, 1, 2,
    { onAccessDenied: () => rechecks++ });
  await store.load(); assert.deepEqual(store.getSnapshot().data, ready);
  deny = true; await store.load(); assert.equal(store.getSnapshot().data, null); assert.equal(rechecks, 1);
});

test('issuance requires server permission, prevents duplicate requests and reloads authoritative state', async () => {
  let finish, calls = 0, issued = false;
  const store = createReportStore({ get: async () => issued ? ready : { status: 'not_issued', can_generate: true, report: null },
    issue: async () => { calls++; return new Promise(resolve => { finish = () => { issued = true; resolve(); }; }); } }, 1, 2);
  await store.issue(); assert.equal(calls, 0);
  await store.load(); const pending = store.issue(); await store.issue(); assert.equal(calls, 1);
  assert.equal(store.getSnapshot().data, null); finish(); await pending;
  assert.deepEqual(store.getSnapshot().data, ready); await store.issue(); assert.equal(calls, 1);
});

test('unmount cancels late document delivery and never retains a download capability', async () => {
  let finish;
  const store = createReportStore({ get: async () => ready, download: () => new Promise(resolve => { finish = resolve; }) }, 1, 2);
  const disconnect = store.connect(); await store.load(); const pending = store.download(); disconnect();
  finish(new Blob(['synthetic'])); assert.equal(await pending, undefined);
  assert.equal(store.getSnapshot().data, null);
});
