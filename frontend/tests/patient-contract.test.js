import assert from 'node:assert/strict';
import test from 'node:test';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createServer } from 'vite';
import { createApiClient } from '../src/services/api.js';
import { createAuthService } from '../src/services/auth.js';
import { createPatientService } from '../src/services/patients.js';
import { createPatientWorkspace } from '../src/patient/workspace.js';
import { categoricalInputs, numericInputs, inputFeatures, prepareAssessment } from '../src/patient/assessmentFields.js';

const root = fileURLToPath(new URL('../../', import.meta.url));
const password = 'fixture-password-123';
const values = () => Object.fromEntries(inputFeatures.map(name => [name, numericInputs.includes(name) ? '0' : ' entered fixture ']));

test('Patient Assessment UI operations through Vite proxy and real owner-only Flask persistence', { timeout: 30000 }, async t => {
  const python = process.env.AYURSAGE_TEST_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const child = spawn(python, ['-B', '-u', 'frontend/tests/flask_auth_fixture.py', '--patient-fixtures'], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });
  t.after(() => child.kill());
  const { port, contract } = await new Promise((resolve, reject) => {
    let output = '';
    const timer = setTimeout(() => reject(new Error('Patient fixture did not start.')), 10000);
    child.once('error', error => { clearTimeout(timer); reject(error); });
    child.once('exit', code => { clearTimeout(timer); reject(new Error('Patient fixture exited: ' + code)); });
    child.stderr.resume();
    child.stdout.on('data', chunk => {
      output += chunk;
      const ready = output.match(/READY (\d+)/);
      const contract = output.match(/CONTRACT ([^\r\n]+)/);
      if (ready && contract) { clearTimeout(timer); resolve({ port: Number(ready[1]), contract: JSON.parse(contract[1]) }); }
    });
  });
  const vite = await createServer({ server: { host: '127.0.0.1', port: 0, strictPort: false,
    proxy: { '/api': { target: `http://127.0.0.1:${port}`, changeOrigin: true } } } });
  t.after(() => vite.close());
  await vite.listen();
  const api = createApiClient({ baseUrl: `http://127.0.0.1:${vite.httpServer.address().port}/api` });
  const auth = createAuthService(api);
  const patients = createPatientService(api);
  let owner, saved, ownerProfile, secondProfile;

  await t.test('12 exact frontend field names and types agree with backend and parsed frozen V17 declarations', () => {
    assert.deepEqual(categoricalInputs, contract.CATEGORICAL_COLS);
    assert.deepEqual(numericInputs, contract.NUMERIC_COLS);
    assert.equal(inputFeatures.length, 12);
  });
  await t.test('missing legacy profile is viewed, created with empty body and retrieved for authenticated owner', async () => {
    const session = await auth.login('legacy-patient@example.invalid', password);
    const workspace = createPatientWorkspace(patients);
    await workspace.loadProfile();
    assert.equal(workspace.getSnapshot().profile.data, null);
    await workspace.createProfile();
    const profile = workspace.getSnapshot().profile.data;
    assert.equal(profile.owner_user_id, session.user.id);
    assert.deepEqual(await patients.getProfile(), profile);
    assert.deepEqual(await patients.createProfile(), profile); // Existing-profile race recovery.
  });
  await t.test('registration profile is reused and assessment form submission persists all inputs, zero, notes and actor', async () => {
    owner = (await auth.login('record-owner@example.invalid', password)).user;
    const workspace = createPatientWorkspace(patients);
    await workspace.loadProfile();
    ownerProfile = workspace.getSnapshot().profile.data;
    assert.equal(ownerProfile.owner_user_id, owner.id);
    for (const [name, value] of Object.entries(values())) workspace.changeField(name, value);
    workspace.changeNotes(' patient fixture notes\n ');
    await workspace.submit();
    assert.equal(workspace.getSnapshot().form.status, 'ready');
    saved = workspace.getSnapshot().form.saved;
    assert.ok(saved);
    assert.deepEqual(saved.inputs, prepareAssessment(values()).payload.inputs);
    assert.equal(saved.inputs['BP Systolic'], 0);
    assert.equal(saved.notes, ' patient fixture notes\n ');
    assert.equal(saved.recorded_by_user_id, owner.id);
    assert.deepEqual(Object.keys(saved).sort(), ['id', 'patient_id', 'recorded_by_user_id', 'created_at', 'inputs', 'notes'].sort());
    assert.deepEqual(await patients.getAssessment(ownerProfile.id, saved.id), saved);
  });
  await t.test('real Flask rejects each missing field, wrong numeric type and client-supplied ownership', async () => {
    const payload = prepareAssessment(values()).payload;
    for (const name of inputFeatures) {
      const inputs = { ...payload.inputs };
      delete inputs[name];
      await assert.rejects(patients.createAssessment(ownerProfile.id, { inputs }), error => error.status === 400);
    }
    await assert.rejects(patients.createAssessment(ownerProfile.id, { inputs: { ...payload.inputs, 'Pulse Rate': '0' } }), error => error.status === 400);
    await assert.rejects(patients.createAssessment(ownerProfile.id, { ...payload, recorded_by_user_id: 999 }), error => error.status === 400);
  });
  await t.test('assessment history paginates actual records and detail preserves legacy null inputs', async () => {
    const workspace = createPatientWorkspace(patients);
    await workspace.loadProfile();
    const payload = prepareAssessment(values()).payload;
    for (let index = 0; index < 21; index++) await patients.createAssessment(ownerProfile.id, payload);
    await workspace.loadHistory();
    const first = workspace.getSnapshot().history;
    assert.equal(first.items.length, 20);
    assert.ok(first.nextAfterId);
    const legacy = first.items[0];
    assert.equal(legacy.inputs, null);
    await workspace.loadDetail(legacy.id);
    assert.equal(workspace.getSnapshot().detail.data.inputs, null);
    await workspace.loadHistory(true);
    assert.equal(workspace.getSnapshot().history.items.length, 23); // legacy + saved + 21 additional.
    assert.equal(workspace.getSnapshot().history.nextAfterId, null);
    assert.equal(new Set(workspace.getSnapshot().history.items.map(row => row.id)).size, 23);
  });
  await t.test('new patient history is empty; another patient cannot view, create or retrieve owner records', async () => {
    await auth.register('other-patient@example.invalid', password);
    await auth.login('other-patient@example.invalid', password);
    secondProfile = await patients.getProfile();
    const history = await patients.getHistory(secondProfile.id);
    assert.deepEqual(history, { assessments: [], nextAfterId: null });
    await assert.rejects(api.request(`/patients/${ownerProfile.id}`, { authenticated: true }), error => error.status === 404);
    await assert.rejects(patients.getHistory(ownerProfile.id), error => error.status === 404);
    await assert.rejects(patients.getAssessment(ownerProfile.id, saved.id), error => error.status === 404);
    await assert.rejects(patients.createAssessment(ownerProfile.id, prepareAssessment(values()).payload), error => error.status === 404);
    await assert.rejects(patients.getAssessment(secondProfile.id, saved.id), error => error.status === 404);
  });
  await t.test('doctor/admin operations remain forbidden and invalid tokens trigger existing logout handling', async () => {
    for (const role of ['doctor', 'admin']) {
      await auth.login(role + '@example.invalid', password);
      for (const operation of [() => patients.getProfile(), () => patients.createProfile(),
        () => patients.getHistory(ownerProfile.id), () => patients.getAssessment(ownerProfile.id, saved.id),
        () => patients.createAssessment(ownerProfile.id, prepareAssessment(values()).payload)]) {
        await assert.rejects(operation(), error => error.status === 403);
      }
    }
    let expired = false;
    api.setUnauthorizedHandler(() => { expired = true; api.setToken(null); });
    api.setToken('invalid-test-token');
    await assert.rejects(patients.getProfile(), error => error.status === 401);
    assert.equal(expired, true);
  });
});
