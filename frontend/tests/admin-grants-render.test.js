import assert from 'node:assert/strict';
import { test, before, after } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

let vite, Screen, Home;
before(async () => {
  vite = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' });
  Screen = (await vite.ssrLoadModule('/src/pages/AdminGrantsPage.jsx')).AdminGrantsScreen;
});
after(async () => { await vite?.close(); });
const state = { status: 'ready', patientId: 4, items: [], nextAfterId: null, error: '', notice: '', confirmingId: null, issueCandidate: null };
const render = changes => renderToStaticMarkup(React.createElement(Screen, { state: { ...state, ...changes } }));

test('admin screen exposes only existing grant workflow, defaults review unchecked and requires consent', () => {
  const markup = render();
  assert.match(markup,/Patient profile ID/); assert.match(markup,/Doctor account ID/);
  assert.match(markup,/Retained consent reference/); assert.match(markup,/30-day/);
  assert.match(markup,/Review grant before issuing/); assert.doesNotMatch(markup,/checked=""/);
  assert.doesNotMatch(markup,/Clinical notes|Record your clinical decision|V17.*Load/);
});

test('confirmation previews exact patient/doctor/consent and selected permission before write', () => {
  const markup = render({ issueCandidate: { doctor_user_id: 7, consent_reference: '<synthetic>', allow_review: true } });
  assert.match(markup,/Patient #4; doctor #7/); assert.match(markup,/Read and clinical review/);
  assert.match(markup,/&lt;synthetic&gt;/); assert.match(markup,/Confirm issue grant/);
  assert.doesNotMatch(markup,/Review grant before issuing/);
});

test('denied and busy states cannot issue a grant', () => {
  assert.doesNotMatch(render({ status: 'error', error: 'Grant-administrator permission is required.' }), /Review grant before issuing/);
  const markup = render({ status: 'issuing', issueCandidate: { doctor_user_id: 7, consent_reference: 'synthetic', allow_review: false } });
  assert.match(markup,/Permission: Read-only/); assert.match(markup,/disabled=""/);
});
