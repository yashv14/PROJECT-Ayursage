import assert from 'node:assert/strict';
import test from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
import { createApiClient } from '../src/services/api.js';
import { createReceptionService } from '../src/services/reception.js';
import { resolveRoute } from '../src/routing/routes.js';

test('reception routes deny other roles and clinical patient routes deny receptionist', () => {
  assert.deepEqual(resolveRoute('/receptionist', null), { redirect: '/login' });
  for (const role of ['patient', 'doctor', 'admin']) assert.deepEqual(resolveRoute('/receptionist', { role }), { page: 'forbidden' });
  assert.deepEqual(resolveRoute('/receptionist', { role: 'receptionist' }), { page: 'home' });
  for (const path of ['/patient/profile', '/patient/assessments/new', '/patient/assessments', '/patient/assessments/1']) assert.deepEqual(resolveRoute(path, { role: 'receptionist' }), { page: 'forbidden' });
});
test('reception client uses bearer, exact email and safe administrative errors', async () => {
  const calls = [];
  const api = createApiClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ patient: { id: 3, email: 'patient@example.invalid', administrative_status: 'registered' } }), { status: 200 });
  } });
  api.setToken('fixture');
  const service = createReceptionService(api);
  await service.lookup(' PATIENT@example.invalid ');
  assert.equal(calls[0].url, '/api/reception/patients?email=patient%40example.invalid');
  assert.equal(calls[0].options.headers.Authorization, 'Bearer fixture');
  const failApi = createApiClient({ fetchImpl: async () => new Response('{}', { status: 409 }) }); failApi.setToken('fixture');
  await assert.rejects(createReceptionService(failApi).status(1, 'cancelled'), /conflicts/);
  const malformed = createApiClient({ fetchImpl: async () => new Response(JSON.stringify({ doctors: [], next_after_id: 0 })) }); malformed.setToken('fixture');
  await assert.rejects(createReceptionService(malformed).doctors(), /Unexpected/);
});
test('reception dashboard renders administrative fields and only allowed attendance controls', async t => {
  const vite = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' });
  t.after(() => vite.close());
  const { ReceptionScreen } = await vite.ssrLoadModule('/src/pages/ReceptionPage.jsx');
  const props = { patient: { id: 1, email: 'fixture@example.invalid', administrative_status: 'registered' }, doctors: [{ id: 2, email: 'doctor@example.invalid' }], rows: [], next: null, busy: false, error: '', notice: '', email: '', doctor: '', start: '', end: '', editing: null };
  const render = status => renderToStaticMarkup(React.createElement(ReceptionScreen, { ...props, rows: [{ id: 1, patient_id: 1, doctor_user_id: 2, starts_at: '2026-11-01T10:00:00Z', ends_at: '2026-11-01T10:30:00Z', status }] }));
  assert.match(render('scheduled'), /Reschedule/); assert.match(render('scheduled'), /Check in/); assert.match(render('scheduled'), /No show/);
  assert.match(render('checked_in'), /Complete/); assert.doesNotMatch(render('checked_in'), /Reschedule|>Cancel</);
  for (const status of ['completed', 'cancelled', 'no_show']) assert.doesNotMatch(render(status), /Reschedule|>Complete<|>Check in<|>Cancel</);
  assert.doesNotMatch(render('scheduled'), /type="password"|Herbal Therapy|BP Systolic|consent_reference/);
  assert.match(render('scheduled'), /Invitations are unavailable/);
  const failure = renderToStaticMarkup(React.createElement(ReceptionScreen, { ...props, error: 'Network failed', busy: true }));
  assert.match(failure, /role="alert"/); assert.match(failure, /role="status"/); assert.match(failure, /disabled/);
});
