import assert from 'node:assert/strict';
import { test, before, after } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
import { createPatientWorkspace } from '../src/patient/workspace.js';
import { inputFeatures, numericInputs, emptyInputs, prepareAssessment } from '../src/patient/assessmentFields.js';
import { createApiClient } from '../src/services/api.js';
import { createPatientService } from '../src/services/patients.js';

let vite;
let ProfileScreen, AccessGrantsScreen, AssessmentFormScreen, AssessmentHistoryScreen, AssessmentDetailScreen;
before(async () => {
  vite = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' });
  ({ ProfileScreen, AccessGrantsScreen } = await vite.ssrLoadModule('/src/pages/PatientProfilePage.jsx'));
  ({ AssessmentFormScreen } = await vite.ssrLoadModule('/src/pages/AssessmentFormPage.jsx'));
  ({ AssessmentHistoryScreen } = await vite.ssrLoadModule('/src/pages/AssessmentHistoryPage.jsx'));
  ({ AssessmentDetailScreen } = await vite.ssrLoadModule('/src/pages/AssessmentDetailPage.jsx'));
});
after(async () => { await vite?.close(); });
const html = element => renderToStaticMarkup(element);
function elements(element) {
  if (!React.isValidElement(element)) return [];
  return [element, ...React.Children.toArray(element.props.children).flatMap(elements)];
}
const profile = { id: 1, owner_user_id: 7 };
const values = () => Object.fromEntries(inputFeatures.map(name => [name, numericInputs.includes(name) ? '0' : ' entered text ']));
const assessment = { id: 2, patient_id: 1, recorded_by_user_id: 7, created_at: '2026-10-13T11:00:00', inputs: prepareAssessment(values()).payload.inputs, notes: ' patient notes ' };
const formScreen = store => AssessmentFormScreen({ form: store.getSnapshot().form, onField: store.changeField,
  onNotes: store.changeNotes, onPredict: store.changePredict, onSubmit: store.submit, onReset: store.resetForm });
const profileScreen = store => ProfileScreen({ profile: store.getSnapshot().profile, onCreate: store.createProfile, onReload: store.loadProfile });

test('doctor access panel renders empty/loading/error states, history and confirmation controls', () => {
  const base = { status: 'ready', items: [], nextAfterId: null, error: '', notice: '', confirmingId: null };
  const render = grants => html(AccessGrantsScreen({ grants }));
  assert.match(render(base), /No doctor-access grants/);
  assert.match(render({ ...base, status: 'loading' }), /Loading doctor access/);
  assert.match(render({ ...base, error: 'Access unavailable.' }), /role="alert"/);
  const grants = { ...base, items: ['issued', 'expired', 'revoked'].map((status, i) => ({ id: i + 1,
    doctor_user_id: 8, status, expires_at: '2026-11-13T10:00:00Z' })), nextAfterId: 3 };
  const markup = render(grants);
  assert.match(markup, /Active/); assert.match(markup, /Expired/); assert.match(markup, /Revoked/);
  assert.match(markup, /Load more grants/);
  assert.equal((markup.match(/Revoke access/g) || []).length, 1);
  const confirmation = render({ ...grants, confirmingId: 1 });
  assert.match(confirmation, /Revoke grant #1 for doctor #8/);
  assert.match(confirmation, /Confirm revocation/); assert.match(confirmation, />Cancel</);
  assert.match(render({ ...grants, confirmingId: 1, status: 'revoking' }), /Revoking doctor access/);
  assert.doesNotMatch(html(ProfileScreen({ profile: { status: 'ready', data: null }, grants })), /doctor-access-title/);
});

test('doctor access panel connects confirmation/cancel/revoke handlers and disables actions during requests', async () => {
  const grant = { id: 4, doctor_user_id: 8, status: 'issued', expires_at: '2026-11-13T10:00:00Z' };
  let finish;
  const store = createPatientWorkspace({ getProfile: async () => profile,
    getAccessGrants: async () => ({ grants: [grant], nextAfterId: null }),
    revokeAccessGrant: () => new Promise(resolve => { finish = resolve; }) });
  await store.loadProfile(); await store.loadGrants();
  const screen = () => AccessGrantsScreen({ grants: store.getSnapshot().grants,
    onConfirm: store.confirmGrantRevocation, onCancel: store.cancelGrantRevocation,
    onRevoke: store.revokeGrant, onReload: () => store.loadGrants(), onMore: () => store.loadGrants(true) });
  const button = text => elements(screen()).find(node => node.type === 'button' && node.props.children === text);
  button('Revoke access').props.onClick();
  button('Cancel').props.onClick();
  assert.equal(store.getSnapshot().grants.confirmingId, null);
  button('Revoke access').props.onClick();
  const pending = button('Confirm revocation').props.onClick();
  assert.ok(elements(screen()).filter(node => node.type === 'button').every(node => node.props.disabled));
  finish({ ...grant, status: 'revoked' }); await pending;
  assert.match(html(screen()), /Access grant #4 was revoked/);
  assert.equal(button('Revoke access'), undefined);
});

test('Patient profile screen shows loading, missing profile, actual create handler and owner-linked result', async () => {
  let finish;
  const store = createPatientWorkspace({ getProfile: async () => null, createProfile: () => new Promise(resolve => { finish = resolve; }) });
  assert.match(html(profileScreen(store)), /Loading your profile/);
  await store.loadProfile();
  assert.match(html(profileScreen(store)), /No profile exists/);
  const button = elements(profileScreen(store)).find(node => node.type === 'button' && node.props.onClick === store.createProfile);
  assert.ok(button);
  const creating = button.props.onClick();
  assert.match(html(profileScreen(store)), /Creating your profile/);
  finish(profile);
  await creating;
  const result = html(profileScreen(store));
  assert.match(result, /Owner account ID/);
  assert.match(result, />7<\/dd>/);
  assert.match(result, /Your patient profile is ready/);
  assert.match(result, /#\/patient\/assessments\/new/);
});

test('Clinical assessment form renders all 12 exact named required inputs with text/number types and no medical ranges', () => {
  const store = createPatientWorkspace({});
  const screen = formScreen(store);
  const inputs = elements(screen).filter(node => node.type === 'input' && node.props.type !== 'checkbox');
  assert.deepEqual(inputs.map(node => node.props.name), inputFeatures);
  for (const input of inputs) {
    assert.equal(input.props.required, true);
    assert.equal(input.props.value, '');
    assert.equal(input.props.type, numericInputs.includes(input.props.name) ? 'number' : 'text');
    if (input.props.type === 'number') assert.equal(input.props.step, 'any');
    assert.equal(input.props.min, undefined);
    assert.equal(input.props.max, undefined);
    assert.equal(input.props.defaultValue, undefined);
  }
  const markup = html(screen);
  assert.match(markup, /Save the assessment alone/);
  const checkbox = elements(screen).find(node => node.type === 'input' && node.props.type === 'checkbox');
  assert.equal(checkbox.props.checked, false);
  assert.match(markup, /Notes \(optional\)/);
  assert.doesNotMatch(markup, /<select|prediction-result|Herbal Therapy Strategy/);
});

test('Assessment form input/change/submit handlers validate, display loading and save actual numeric payload', async () => {
  let finish;
  let submitted;
  const store = createPatientWorkspace({ getProfile: async () => profile, createAssessment: (id, payload) => {
    submitted = { id, payload };
    return new Promise(resolve => { finish = resolve; });
  } });
  await store.loadProfile();
  let screen = formScreen(store);
  const submit = () => elements(formScreen(store)).find(node => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await submit();
  assert.match(html(formScreen(store)), /Please correct the marked fields/);
  assert.equal(elements(formScreen(store)).filter(node => node.type === 'input' && node.props['aria-invalid']).length, 12);
  screen = formScreen(store);
  for (const input of elements(screen).filter(node => node.type === 'input' && node.props.type !== 'checkbox')) input.props.onChange({ target: { value: values()[input.props.name] } });
  elements(screen).find(node => node.type === 'textarea').props.onChange({ target: { value: ' patient notes ' } });
  const saving = submit();
  const pending = html(formScreen(store));
  assert.match(pending, /Saving assessment/);
  assert.match(pending, /<fieldset disabled=""/);
  assert.equal(submitted.id, 1);
  assert.deepEqual(submitted.payload, { inputs: assessment.inputs, notes: ' patient notes ', predict: false });
  finish({ assessment });
  await saving;
  const success = html(formScreen(store));
  assert.match(success, /Assessment #2 was saved/);
  assert.match(success, /#\/patient\/assessments\/2/);
  elements(formScreen(store)).find(node => node.type === 'button').props.onClick();
  assert.deepEqual(store.getSnapshot().form.values, emptyInputs());
});

test('Profile/form/history/detail render network and authorization error alerts with retries where appropriate', async () => {
  for (const message of ['Unable to connect to AYUR-SAGE. Please try again.', 'You do not have permission to perform this action.']) {
    const profileError = html(ProfileScreen({ profile: { status: 'error', data: null, error: message }, onReload: () => {} }));
    const formError = html(AssessmentFormScreen({ form: { values: emptyInputs(), notes: '', errors: {}, status: 'error', saved: null, error: message }, onField: () => {}, onNotes: () => {}, onSubmit: () => {} }));
    const historyError = html(AssessmentHistoryScreen({ history: { status: 'error', items: [], nextAfterId: null, error: message }, onReload: () => {} }));
    const detailError = html(AssessmentDetailScreen({ detail: { status: 'error', data: null, error: message }, onRetry: () => {} }));
    for (const markup of [profileError, formError, historyError, detailError]) { assert.match(markup, /role="alert"/); assert.ok(markup.includes(message)); }
    for (const markup of [profileError, historyError, detailError]) assert.match(markup, /Try again/);
  }
  const store = createPatientWorkspace({ getProfile: async () => { throw new Error('Unavailable'); } });
  await store.loadProfile();
  assert.doesNotMatch(html(profileScreen(store)), /Create my profile/); // Failure is not a missing profile.
});

test('Assessment history renders empty/loading states, records, detail links and load-more handler', () => {
  assert.match(html(AssessmentHistoryScreen({ history: { status: 'loading', items: [], error: '', nextAfterId: null } })), /Loading assessment history/);
  assert.match(html(AssessmentHistoryScreen({ history: { status: 'ready', items: [], error: '', nextAfterId: null } })), /No assessments have been saved yet/);
  let more = false;
  const screen = AssessmentHistoryScreen({ history: { status: 'ready', items: [assessment, { ...assessment, id: 3, inputs: null }], error: '', nextAfterId: 3 }, onMore: () => { more = true; } });
  const markup = html(screen);
  assert.match(markup, /#\/patient\/assessments\/2/);
  assert.match(markup, /Legacy record: no stored inputs/);
  assert.match(markup, /Recorded at \(server time\)/);
  elements(screen).find(node => node.type === 'button' && node.props.children === 'Load more').props.onClick();
  assert.equal(more, true);
});

test('Assessment detail renders all saved inputs, explicit zero, notes, and preserves null legacy records', () => {
  const markup = html(AssessmentDetailScreen({ detail: { status: 'ready', data: assessment, error: '' } }));
  for (const name of inputFeatures) assert.ok(markup.includes(name));
  assert.match(markup, />0<\/dd>/);
  assert.match(markup, / patient notes /);
  assert.match(markup, /predictions are response-only/);
  const legacy = html(AssessmentDetailScreen({ detail: { status: 'ready', data: { ...assessment, inputs: null, notes: null }, error: '' } }));
  assert.match(legacy, /no saved input values/);
  assert.match(legacy, /No notes were supplied/);
  assert.doesNotMatch(legacy, /BP Systolic|>0<\/dd>/);
});

// Synthetic labels exercise rendering only; they are not model predictions.
const predictionTargets = [
  'Herbal Therapy Strategy', 'Lifestyle Recommendations',
  'Therapeutic Yoga Module', 'Follow-up Recommendation',
];
const controlledPrediction = () => ({ model_version: 'AyurSage_v17', status: 'pending_clinical_review', persisted: false,
  outputs: Object.fromEntries(predictionTargets.map((name, i) => [name, `TEST_ONLY_LABEL_${i}`])) });
async function predictionStore(data, status = 201) {
  const calls = [];
  const api = createApiClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify(data), { status });
  } });
  api.setToken('test-only-token');
  const store = createPatientWorkspace({ ...createPatientService(api), getProfile: async () => profile });
  await store.loadProfile();
  for (const input of elements(formScreen(store)).filter(node => node.type === 'input' && node.props.type !== 'checkbox')) {
    input.props.onChange({ target: { value: values()[input.props.name] } });
  }
  const checkbox = elements(formScreen(store)).find(node => node.type === 'input' && node.props.type === 'checkbox');
  checkbox.props.onChange({ target: { checked: true } });
  assert.equal(store.getSnapshot().form.predict, true);
  return { store, calls };
}
const submitPrediction = store => elements(formScreen(store)).find(node => node.type === 'form').props.onSubmit({ preventDefault() {} });

test('explicit prediction checkbox submits true and renders exactly four cards with review and non-persistence notices', async () => {
  const result = controlledPrediction();
  const { store, calls } = await predictionStore({ assessment, prediction: result });
  await submitPrediction(store);
  assert.equal(calls.length, 1);
  assert.equal(JSON.parse(calls[0].options.body).predict, true);
  const screen = formScreen(store);
  const cards = elements(screen).filter(node => node.type === 'h3');
  assert.deepEqual(cards.map(node => node.props.children), predictionTargets);
  const markup = html(screen);
  assert.match(markup, /Assessment #2 was saved/);
  assert.match(markup, /Doctor review required/);
  assert.match(markup, /pending clinical review/);
  assert.match(markup, /This prediction was not saved/);
  assert.doesNotMatch(markup, /prediction was saved|Doctor Prescription &amp; Care Notes/);
  for (const label of Object.values(result.outputs)) assert.ok(markup.includes(label));
  assert.equal(store.getSnapshot().form.prediction.persisted, false);
});

for (const [status, reason, message] of [
  [400, 'invalid_assessment', 'inputs must contain exactly the 12 V17 feature names.'],
  [503, 'model_unavailable', 'V17 model is unavailable; no prediction or assessment was saved.'],
  [500, 'inference_error', 'V17 inference failed; no prediction or assessment was saved.'],
]) {
  test(`prediction ${status} failure displays an error, no saved confirmation or cards, and makes one request`, async () => {
    const { store, calls } = await predictionStore({ error: { code: status, reason, message } }, status);
    await submitPrediction(store);
    const markup = html(formScreen(store));
    assert.match(markup, /role="alert"/);
    assert.ok(markup.includes(message));
    assert.doesNotMatch(markup, /Assessment #2 was saved|<h2[^>]*>Generated prediction|<h3/);
    assert.equal(store.getSnapshot().form.saved, null);
    assert.equal(store.getSnapshot().form.prediction, null);
    assert.equal(calls.length, 1);
    assert.equal(JSON.parse(calls[0].options.body).predict, true);
  });
}

test('invalid prediction or explicit partial-save error retains saved confirmation but displays no model cards', async () => {
  const invalid = controlledPrediction(); invalid.outputs['Unexpected fifth output'] = 'FORBIDDEN';
  for (const [data, status] of [
    [{ assessment, prediction: invalid }, 201],
    [{ assessment, error: { code: 500, reason: 'inference_error', message: 'Test prediction failure.' } }, 500],
  ]) {
    const { store, calls } = await predictionStore(data, status);
    await submitPrediction(store);
    const markup = html(formScreen(store));
    assert.match(markup, /Assessment #2 was saved/);
    assert.match(markup, /role="alert"/);
    assert.doesNotMatch(markup, /<h3|FORBIDDEN|TEST_ONLY_LABEL/);
    assert.deepEqual(store.getSnapshot().form.saved, assessment);
    assert.equal(store.getSnapshot().form.prediction, null);
    assert.equal(calls.length, 1);
  }
});
