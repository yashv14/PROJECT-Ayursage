// Contract fixtures only. No HTTP server or real model is used by these tests.
import assert from 'node:assert/strict';
import test from 'node:test';
import { createApiClient } from '../src/services/api.js';
import { createPatientService } from '../src/services/patients.js';
import { createPatientWorkspace } from '../src/patient/workspace.js';
import { inputFeatures, numericInputs, outputTargets, prepareAssessment } from '../src/patient/assessmentFields.js';

const expectedOutputs = [
  'Herbal Therapy Strategy', 'Lifestyle Recommendations',
  'Therapeutic Yoga Module', 'Follow-up Recommendation',
];
const values = () => Object.fromEntries(inputFeatures.map(name => [name, numericInputs.includes(name) ? '0' : ' test input ']));
const payload = () => prepareAssessment(values(), 'test notes').payload;
const assessment = () => ({ id: 2, patient_id: 1, recorded_by_user_id: 7,
  created_at: '2026-10-14T10:00:00', inputs: payload().inputs, notes: 'test notes' });
const prediction = () => ({ model_version: 'AyurSage_v17', status: 'pending_clinical_review', persisted: false,
  outputs: Object.fromEntries(expectedOutputs.map((name, i) => [name, `TEST_ONLY_LABEL_${i}`])) });
function fixture(data, status = 201) {
  const calls = [];
  let unauthorized = 0;
  const api = createApiClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify(data), { status });
  } });
  api.setToken('test-only-token');
  api.setUnauthorizedHandler(() => { unauthorized++; });
  const service = createPatientService(api);
  return { api, service, calls, unauthorized: () => unauthorized };
}
async function workspace(f, predict = true) {
  const store = createPatientWorkspace({ ...f.service, getProfile: async () => ({ id: 1, owner_user_id: 7 }) });
  await store.loadProfile();
  for (const [name, value] of Object.entries(values())) store.changeField(name, value);
  store.changeNotes('test notes');
  store.changePredict(predict);
  return store;
}

test('save-only sends explicit false, twelve typed fields, correct endpoint and bearer; retains response envelope', async () => {
  const data = { assessment: assessment() };
  const f = fixture(data);
  const result = await f.service.createAssessment(1, payload(), false);
  assert.deepEqual(result, data);
  const { url, options } = f.calls[0];
  assert.equal(url, '/api/patients/1/assessments');
  assert.equal(options.method, 'POST');
  assert.equal(options.headers.Authorization, 'Bearer test-only-token');
  const body = JSON.parse(options.body);
  assert.deepEqual(body, payload());
  assert.equal(body.predict, false);
  assert.deepEqual(Object.keys(body.inputs), inputFeatures);
  for (const name of inputFeatures) assert.equal(typeof body.inputs[name], numericInputs.includes(name) ? 'number' : 'string');
  const store = await workspace(f, false);
  await store.submit();
  assert.deepEqual(store.getSnapshot().form.saved, data.assessment);
  assert.equal(store.getSnapshot().form.prediction, null);
  assert.equal(store.getSnapshot().form.error, '');
});

test('predict defaults to false and nonboolean prediction controls are rejected without a request', async () => {
  const f = fixture({ assessment: assessment() });
  await f.service.createAssessment(1, payload());
  assert.equal(JSON.parse(f.calls[0].options.body).predict, false);
  for (const invalid of ['true', 1, null]) {
    await assert.rejects(f.service.createAssessment(1, payload(), invalid), error => error.status === 400);
    assert.equal(prepareAssessment(values(), '', invalid).payload, null);
  }
  assert.equal(f.calls.length, 1);
  assert.equal(createPatientWorkspace(f.service).getSnapshot().form.predict, false);
});

test('controlled prediction preserves full envelope and all four raw labels in workspace state', async () => {
  assert.deepEqual(outputTargets, expectedOutputs);
  const data = { assessment: assessment(), prediction: prediction() };
  const f = fixture(data);
  assert.deepEqual(await f.service.createAssessment(1, payload(), true), data);
  const store = await workspace(f);
  await store.submit();
  assert.equal(JSON.parse(f.calls.at(-1).options.body).predict, true);
  const form = store.getSnapshot().form;
  assert.equal(form.status, 'ready');
  assert.deepEqual(form.saved, data.assessment);
  assert.deepEqual(form.prediction, data.prediction);
  assert.equal(form.error, '');
  store.resetForm();
  assert.equal(store.getSnapshot().form.prediction, null);
  assert.equal(store.getSnapshot().form.predict, false);
});

for (const [status, reason, message] of [
  [400, 'invalid_assessment', 'inputs must contain exactly the 12 V17 feature names.'],
  [400, 'invalid_model_input', 'V17 requires all 12 typed inputs and exact fitted categorical values.'],
  [503, 'model_unavailable', 'V17 model is unavailable; no prediction or assessment was saved.'],
  [500, 'inference_error', 'V17 inference failed; no prediction or assessment was saved.'],
]) {
  test(`${status} ${reason} preserves safe error, draft and no-save state; no fallback request`, async () => {
    const f = fixture({ error: { code: status, reason, message } }, status);
    const store = await workspace(f);
    await store.submit();
    const form = store.getSnapshot().form;
    assert.equal(form.status, 'error');
    assert.equal(form.error, message);
    assert.equal(form.saved, null);
    assert.equal(form.prediction, null);
    assert.deepEqual(form.values, values());
    assert.equal(form.predict, true);
    assert.equal(f.calls.length, 1);
    assert.equal(JSON.parse(f.calls[0].options.body).predict, true);
    assert.equal(f.unauthorized(), 0);
  });
}

test('malformed predictions are rejected while the genuine saved assessment is retained', async () => {
  const missing = prediction(); delete missing.outputs[expectedOutputs[0]];
  const extra = prediction(); extra.outputs['Doctor Prescription & Care Notes'] = 'UNAUTHORIZED_EXTRA';
  const wrongType = prediction(); wrongType.outputs[expectedOutputs[0]] = {};
  for (const invalid of [null, missing, extra, wrongType,
    { ...prediction(), model_version: 'other' }, { ...prediction(), status: 'approved' },
    { ...prediction(), persisted: true }]) {
    const f = fixture({ assessment: assessment(), prediction: invalid });
    const store = await workspace(f);
    await store.submit();
    const form = store.getSnapshot().form;
    assert.deepEqual(form.saved, assessment());
    assert.equal(form.prediction, null);
    assert.match(form.error, /prediction response was invalid/);
    assert.equal(f.calls.length, 1);
  }
});

test('missing optional prediction does not fabricate one or discard a successful assessment', async () => {
  const f = fixture({ assessment: assessment() });
  const store = await workspace(f);
  await store.submit();
  assert.deepEqual(store.getSnapshot().form.saved, assessment());
  assert.equal(store.getSnapshot().form.prediction, null);
  assert.match(store.getSnapshot().form.error, /did not return a prediction/);
  assert.equal(f.calls.length, 1);
});

test('error envelopes retain only valid saved assessment data for the requested patient', async () => {
  for (const saved of [assessment(), { ...assessment(), patient_id: 99 }, { id: 2 }]) {
    const f = fixture({ assessment: saved, error: { code: 500, reason: 'inference_error', message: 'Test prediction failure.' } }, 500);
    const store = await workspace(f);
    await store.submit();
    assert.deepEqual(store.getSnapshot().form.saved, saved.patient_id === 1 ? assessment() : null);
    assert.equal(store.getSnapshot().form.prediction, null);
    assert.equal(store.getSnapshot().form.status, 'error');
  }
});

test('unrecognized server messages are hidden; 401 handling and cross-patient response checks remain active', async () => {
  const unrecognized = fixture({ error: { code: 503, reason: 'internal_debug', message: 'PRIVATE_INTERNAL_DETAIL' } }, 503);
  await assert.rejects(unrecognized.service.createAssessment(1, payload(), true), error => error.status === 503 && !error.message.includes('PRIVATE_INTERNAL_DETAIL'));
  const unauthorized = fixture({ error: { code: 401, message: 'Unauthorized' } }, 401);
  await assert.rejects(unauthorized.service.createAssessment(1, payload(), true), error => error.status === 401 && !error.assessment);
  assert.equal(unauthorized.unauthorized(), 1);
  unauthorized.api.setToken(null);
  await assert.rejects(unauthorized.service.createAssessment(1, payload(), true), error => error.status === 401);
  assert.equal(unauthorized.calls.length, 1);
  const forbidden = fixture({ error: { code: 403, message: 'Forbidden' } }, 403);
  await assert.rejects(forbidden.service.createAssessment(1, payload(), true), error => error.status === 403 && !error.assessment);
  const crossPatient = fixture({ assessment: { ...assessment(), patient_id: 99 }, prediction: prediction() });
  await assert.rejects(crossPatient.service.createAssessment(1, payload(), true), error => !error.assessment && /unexpected response/.test(error.message));
});
