import assert from 'node:assert/strict';
import { test, before, after } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
import { createDoctorViewer } from '../src/doctor/workspace.js';
import { inputFeatures, numericInputs } from '../src/patient/assessmentFields.js';

let vite, DoctorAssessmentScreen, DoctorDirectoryScreen;
before(async () => {
  vite = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' });
  ({ DoctorAssessmentScreen, DoctorDirectoryScreen } = await vite.ssrLoadModule('/src/pages/DoctorAssessmentsPage.jsx'));
});
after(async () => { await vite?.close(); });
const html = element => renderToStaticMarkup(element);
function elements(element) {
  if (!React.isValidElement(element)) return [];
  return [element, ...React.Children.toArray(element.props.children).flatMap(elements)];
}
const row = { id: 2, patient_id: 1, recorded_by_user_id: 7, created_at: '2026-10-15T10:00:00',
  inputs: Object.fromEntries(inputFeatures.map(name => [name, numericInputs.includes(name) ? 0 : 'synthetic value'])), notes: 'Synthetic patient note' };
const initial = { status: 'ready', items: [], nextAfterId: null, detail: null, error: '' };

test('authorized directory renders patient links, minimal IDs, loading, empty and denied states', () => {
  const render = state => html(DoctorDirectoryScreen({ state }));
  const markup = render({ ...initial, items: [{ id: 1 }], nextAfterId: 1 });
  assert.match(markup, /#\/doctor\/patients\/1\/assessments/);
  assert.match(markup, /Patient #1/); assert.match(markup, /Next patients/);
  assert.match(markup, /names are not available/);
  assert.doesNotMatch(markup, /<input|<form|prescribe|Confirm revocation|New assessment/);
  assert.match(render(initial), /No patients are currently authorized/);
  assert.match(render({ ...initial, status: 'loading' }), /Loading authorized patients/);
  const denied = render({ ...initial, status: 'error', error: 'Access denied.' });
  assert.match(denied, /role="alert"/); assert.doesNotMatch(denied, /Patient #1/);
});

test('directory refresh and pagination callbacks render no earlier patients after a failed access recheck', async () => {
  let finish;
  let denied = false;
  const store = createDoctorViewer({ getAuthorizedPatients: () => new Promise((resolve, reject) => {
    finish = () => denied ? reject(Object.assign(new Error('Forbidden'), { status: 403 }))
      : resolve({ patients: [{ id: 1 }], nextAfterId: 1 });
  }) });
  const screen = () => DoctorDirectoryScreen({ state: store.getSnapshot(), onReload: () => store.loadDirectory(), onMore: () => store.loadDirectory(true) });
  const button = label => elements(screen()).find(node => node.type === 'button' && node.props.children === label);
  let pending = store.loadDirectory(); finish(); await pending;
  assert.match(html(screen()), /Patient #1/);
  pending = button('Next patients').props.onClick();
  assert.doesNotMatch(html(screen()), /Patient #1/);
  assert.ok(elements(screen()).filter(node => node.type === 'button').every(node => node.props.disabled));
  denied = true; finish(); await pending;
  assert.match(html(screen()), /Access denied/);
  assert.doesNotMatch(html(screen()), /Patient #1/);
  pending = button('Refresh patients').props.onClick();
  denied = false; finish(); await pending;
  assert.match(html(screen()), /Patient #1/);
});

test('read-only history renders stored IDs/times and doctor-scoped navigation without patient write links', () => {
  const screen = state => html(DoctorAssessmentScreen({ patientId: 1, state }));
  const markup = screen({ ...initial, items: [row], nextAfterId: 2 });
  assert.match(markup, /Patient ID: 1/);
  assert.match(markup, /#\/doctor\/patients\/1\/assessments\/2/);
  assert.match(markup, /2026-10-15T10:00:00/);
  assert.match(markup, /Load more/); assert.match(markup, /Refresh history/);
  assert.doesNotMatch(markup, /#\/patient\/|New assessment|approve|prescription|Revoke access/);
  assert.match(screen(initial), /No assessments have been saved/);
  assert.match(screen({ ...initial, status: 'loading' }), /Loading assessment history/);
  const denied = screen({ ...initial, status: 'error', error: 'Access denied. Grant revoked.' });
  assert.match(denied, /role="alert"/); assert.doesNotMatch(denied, /Assessment #2/);
});

test('detail renders twelve stored inputs and patient notes with a doctor history link; legacy null stays null', () => {
  const screen = detail => html(DoctorAssessmentScreen({ patientId: 1, assessmentId: 2, state: { ...initial, detail } }));
  const markup = screen(row);
  for (const name of inputFeatures) assert.ok(markup.includes(name));
  assert.match(markup, /Synthetic patient note/);
  assert.match(markup, /#\/doctor\/patients\/1\/assessments/);
  assert.match(markup, /Patient-supplied notes/); assert.match(markup, /Refresh assessment/);
  assert.doesNotMatch(markup, /<form|<textarea|#\/patient\//);
  assert.match(screen({ ...row, inputs: null }), /older assessment has no saved input values/);
});

test('refresh and revoked-access retry handlers clear previously rendered data and recover only on fresh success', async () => {
  let fail = false;
  let finish;
  const store = createDoctorViewer({ getHistory: () => new Promise((resolve, reject) => {
    finish = () => fail ? reject(Object.assign(new Error('Forbidden'), { status: 403 })) : resolve({ assessments: [row], nextAfterId: null });
  }) }, 1);
  const screen = () => DoctorAssessmentScreen({ patientId: 1, state: store.getSnapshot(), onReload: () => store.loadHistory() });
  let pending = store.loadHistory(); finish(); await pending;
  assert.match(html(screen()), /Assessment #2/);
  // The shared history component receives the actual refresh/retry callbacks.
  const history = elements(screen()).find(node => node.props.history);
  pending = history.props.onReload();
  assert.doesNotMatch(html(screen()), /Assessment #2/);
  fail = true; finish(); await pending;
  assert.match(html(screen()), /Access denied/);
  assert.doesNotMatch(html(screen()), /Assessment #2|Synthetic patient note/);
  pending = elements(screen()).find(node => node.props.history).props.onReload();
  fail = false; finish(); await pending;
  assert.match(html(screen()), /Assessment #2/);
});
