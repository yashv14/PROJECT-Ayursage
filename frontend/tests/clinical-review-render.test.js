import assert from 'node:assert/strict';
import { test, before, after } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
import { outputTargets } from '../src/patient/assessmentFields.js';

let vite, Screen;
before(async () => {
  vite = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' });
  Screen = (await vite.ssrLoadModule('/src/pages/DoctorReviewPanel.jsx')).DoctorReviewScreen;
});
after(async () => { await vite?.close(); });
const render = data => renderToStaticMarkup(React.createElement(Screen, { state: { status: 'ready', data, error: '', notice: '' } }));
const initial = { assessment_id: 2, state: 'pending_review', version: 0, can_review: true, reviews: [] };

test('review form labels human authorship, explicit decisions and manual prescriptions', () => {
  const markup = render(initial);
  assert.match(markup, /<form/); assert.match(markup, /Clinical notes \(required\)/);
  for (const name of outputTargets) assert.ok(markup.includes(name));
  assert.match(markup, /No V17 inference was run/); assert.match(markup, /Add prescription/);
  assert.match(markup, /Return for changes/); assert.match(markup, /immutable decision/);
});

test('read grant alone and terminal approval show no write form', () => {
  const readOnly = render({ ...initial, can_review: false });
  assert.doesNotMatch(readOnly, /<form/); assert.match(readOnly, /explicit clinical-review permission/);
  const final = render({ ...initial, state: 'approved' });
  assert.doesNotMatch(final, /<form/); assert.match(final, /decision is final/);
});

test('persisted review renders escaped notes, author, timestamp, prescription fields and revised values', () => {
  const markup = render({ ...initial, state: 'approved', version: 1, reviews: [{ sequence: 1, actor_user_id: 7,
    decision: 'approved', decided_at: '2026-10-16T10:00:00Z', origin: 'doctor_entered', clinical_notes: '<script>SYNTHETIC</script>',
    recommendations: Object.fromEntries(outputTargets.map(name => [name, 'SYNTHETIC revised text'])),
    prescriptions: [{ medication: 'SYNTHETIC medicine', dose: 'SYNTHETIC dose', route: 'manual route', frequency: 'manual frequency', duration: 'manual duration', instructions: '' }] }] });
  assert.match(markup, /Doctor account #7/); assert.match(markup, /2026-10-16T10:00:00Z/);
  assert.match(markup, /&lt;script&gt;/); assert.doesNotMatch(markup, /<script>/);
  assert.match(markup, /SYNTHETIC medicine/); assert.match(markup, /SYNTHETIC revised text/);
});

test('returned decisions offer resubmission; denied state shows no old content', () => {
  assert.match(render({ ...initial, state: 'returned_for_changes' }), /Resubmit revised review/);
  const markup = renderToStaticMarkup(React.createElement(Screen, { state: { status: 'error', data: null, error: 'Access denied.', notice: '' } }));
  assert.match(markup, /Access denied/); assert.doesNotMatch(markup, /<form|SYNTHETIC medicine/);
});
