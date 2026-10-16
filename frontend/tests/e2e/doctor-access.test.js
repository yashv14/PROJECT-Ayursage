// Opt-in real-browser test. No downloads, authorization mocks or persistent DB.
import assert from 'node:assert/strict';
import test from 'node:test';
import { spawn, execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { createServer } from 'vite';
import { createApiClient } from '../../src/services/api.js';
import { createAuthService } from '../../src/services/auth.js';
import { createPatientService } from '../../src/services/patients.js';
import { categoricalInputs, numericInputs, outputTargets } from '../../src/patient/assessmentFields.js';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const password = 'fixture-password-123';
const clinicalReview = process.env.AYURSAGE_E2E_CLINICAL_REVIEW === '1';
const adminGrants = process.env.AYURSAGE_E2E_ADMIN_GRANTS === '1';

test(adminGrants ? 'browser: administrator grant issuance, reload, review consent and revocation' : 'browser: patient grant → doctor directory/history/detail → patient revocation → denied fresh reads', { timeout: 180000 }, async t => {
  assert.ok(!(adminGrants && clinicalReview), 'Run administrator and clinical-review scenarios separately.');
  const modulePath = process.env.AYURSAGE_PLAYWRIGHT_MODULE;
  let chromium;
  try {
    ({ chromium } = await import(modulePath ? pathToFileURL(path.resolve(modulePath)).href : 'playwright-core'));
  } catch {
    throw new Error('Existing playwright-core is required. Set AYURSAGE_PLAYWRIGHT_MODULE to its index.mjs; this test never installs tooling.');
  }
  const configuredPython = process.env.AYURSAGE_TEST_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  // On Windows a venv launcher can spawn another interpreter. Own the actual
  // base-interpreter handle so teardown cannot leave its server behind.
  const interpreter = JSON.parse(execFileSync(configuredPython, ['-B', '-c',
    'import sys,sysconfig,json; print(json.dumps({"executable":sys._base_executable,"site":sysconfig.get_path("purelib")}))'],
  { encoding: 'utf8', windowsHide: true }));
  const databaseMode = process.env.AYURSAGE_E2E_DATABASE || 'sqlite';
  assert.ok(['sqlite', 'mysql'].includes(databaseMode), 'Select sqlite or mysql explicitly.');
  let child, mysqlChild, browser, vite, mysqlTarget;
  const exited = async (process, timeout) => {
    if (!process || process.exitCode !== null || process.signalCode !== null) return;
    await Promise.race([once(process, 'exit'), new Promise((_, reject) => {
      const timer = setTimeout(() => reject(new Error('Owned test process did not exit.')), timeout); timer.unref();
    })]);
  };
  t.after(async () => {
    try { await browser?.close(); }
    finally {
      try { await vite?.close(); }
      finally {
        try {
          if (child && child.exitCode === null && child.signalCode === null) {
            child.kill(); await exited(child, 5000);
          }
        } finally {
          if (mysqlChild && mysqlChild.exitCode === null && mysqlChild.signalCode === null) {
            mysqlChild.stdin.end('STOP\n'); await exited(mysqlChild, 35000);
          }
          if (mysqlChild) assert.equal(mysqlChild.exitCode, 0, 'Owned MySQL provisioning/cleanup failed.');
        }
      }
    }
  });
  // MySQL mode owns a new server, schema and credentials; never use DATABASE_URL.
  if (databaseMode === 'mysql') {
    mysqlChild = spawn(interpreter.executable, ['-B', '-u', 'frontend/tests/e2e/disposable_mysql.py', ...(clinicalReview ? ['--drop-owned-schema'] : [])], {
      cwd: root, windowsHide: true, env: { ...process.env, PYTHONPATH: interpreter.site }, stdio: ['pipe', 'pipe', 'pipe'],
    });
    let mysqlFailure = '';
    mysqlChild.stderr.on('data', chunk => {
      const safe = chunk.toString().match(/MYSQL_FIXTURE_FAILED [A-Za-z]+ [\w-]+(?: OWNED_[A-Z_]+)?/);
      if (safe) mysqlFailure = safe[0];
    });
    mysqlTarget = await new Promise((resolve, reject) => {
      let output = '';
      const timer = setTimeout(() => reject(new Error('Owned MySQL provisioning timed out.')), 120000);
      mysqlChild.once('error', error => { clearTimeout(timer); reject(error); });
      mysqlChild.once('exit', code => { clearTimeout(timer); reject(new Error(`Owned MySQL provisioning exited (${code}): ${mysqlFailure}`)); });
      mysqlChild.stdout.on('data', chunk => {
        output = (output + chunk).slice(-8192);
        const match = output.match(/MYSQL_READY ([^\r\n]+)/);
        if (match) { clearTimeout(timer); resolve(JSON.parse(match[1])); }
      });
    });
    t.diagnostic(`Owned MySQL ${mysqlTarget.identity.version}; schema=${mysqlTarget.identity.schema}; loopback port=${mysqlTarget.identity.port}; data=${mysqlTarget.identity.datadir}`);
  }
  child = spawn(interpreter.executable, ['-B', '-u', 'frontend/tests/flask_auth_fixture.py', '--doctor-access-fixtures',
    ...(adminGrants ? ['--admin-grant-fixtures'] : []),
    ...(clinicalReview ? ['--clinical-review-checks'] : []),
    ...(databaseMode === 'mysql' ? ['--mysql'] : [])], {
    cwd: root, windowsHide: true, env: { ...process.env, PYTHONPATH: interpreter.site,
      ...(mysqlTarget ? { AYURSAGE_E2E_MYSQL_URL: mysqlTarget.url, AYURSAGE_E2E_MYSQL_IDENTITY: mysqlTarget.identity_file } : {}) },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let fixtureFailure = '';
  child.stderr.on('data', chunk => {
    const safe = chunk.toString().match(/MYSQL_APP_FAILED [A-Za-z]+ [\w-]+ [A-Za-z_<>]+:\d+/);
    if (safe) fixtureFailure = safe[0];
  });
  let databaseInfo;
  let mysqlChecks;
  let reviewChecks;
  const port = await new Promise((resolve, reject) => {
    let output = '';
    const timer = setTimeout(() => reject(new Error('Disposable backend did not start.')), 15000);
    child.once('error', error => { clearTimeout(timer); reject(error); });
    child.once('exit', code => { clearTimeout(timer); reject(new Error(`Disposable backend exited (${code}): ${fixtureFailure}`)); });
    child.stdout.on('data', chunk => {
      output = (output + chunk).slice(-4096);
      const match = output.match(/READY (\d+)/);
      const database = output.match(/DATABASE ([^\r\n]+)/);
      const checks = output.match(/MYSQL_CHECKS ([^\r\n]+)/);
      const reviews = output.match(/MYSQL_REVIEW_CHECKS ([^\r\n]+)/);
      if (checks) mysqlChecks = JSON.parse(checks[1]);
      if (reviews) reviewChecks = JSON.parse(reviews[1]);
      if (match && database) { databaseInfo = JSON.parse(database[1]); clearTimeout(timer); resolve(Number(match[1])); }
    });
  });
  assert.equal(databaseInfo.dialect, databaseMode === 'mysql' ? 'mysql' : 'sqlite');
  assert.equal(databaseInfo.migration, '0007_clinical_review');
  if (mysqlTarget) assert.equal(databaseInfo.schema, mysqlTarget.identity.schema);
  if (mysqlTarget) { assert.equal(mysqlChecks?.length, 7); t.diagnostic('MySQL-specific checks passed: ' + mysqlChecks.join(', ')); }
  if (clinicalReview) {
    assert.equal(databaseMode, 'mysql', 'Clinical review mode requires disposable MySQL.');
    assert.equal(reviewChecks?.checks.length, 7); assert.equal(reviewChecks.races.length, 3);
    t.diagnostic('MySQL clinical-review checks: ' + JSON.stringify(reviewChecks));
  }
  t.diagnostic(`Verified application database=${databaseInfo.dialect}; migration=${databaseInfo.migration}`);
  vite = await createServer({ clearScreen: false, define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('/api') },
    server: { host: '127.0.0.1', port: 0, strictPort: false,
      proxy: { '/api': { target: `http://127.0.0.1:${port}`, changeOrigin: true } } } });
  await vite.listen();
  const origin = `http://127.0.0.1:${vite.httpServer.address().port}`;
  const client = () => {
    const api = createApiClient({ baseUrl: origin + '/api', fetchImpl: (url, options) => fetch(url, { ...options, signal: AbortSignal.timeout(5000) }) });
    return { api, auth: createAuthService(api), patients: createPatientService(api) };
  };
  const owner = client(), unrelated = client(), doctor = client(), otherDoctor = client(), admin = client(), reception = client();
  for (const [actor, email] of [[owner, 'browser-patient@example.invalid'], [unrelated, 'unrelated-patient@example.invalid']]) {
    await actor.auth.register(email, password); await actor.auth.login(email, password);
  }
  const patient = await owner.patients.getProfile();
  const unrelatedPatient = await unrelated.patients.getProfile();
  const doctorUser = (await doctor.auth.login('doctor@example.invalid', password)).user;
  await otherDoctor.auth.login('other-doctor@example.invalid', password);
  await admin.auth.login('admin@example.invalid', password);
  await reception.auth.login('receptionist@example.invalid', password);
  const inputs = { ...Object.fromEntries(categoricalInputs.map(name => [name, 'Synthetic access test'])),
    ...Object.fromEntries(numericInputs.map(name => [name, 0])) };
  const saved = (await owner.patients.createAssessment(patient.id, { inputs, notes: 'SYNTHETIC BROWSER ASSESSMENT ONLY' }, false)).assessment;
  let grant = (await admin.api.request(`/patients/${patient.id}/doctor-access-grants`, { authenticated: true, method: 'POST',
    body: { doctor_user_id: doctorUser.id, consent_reference: 'synthetic-browser-consent' } })).grant;
  // Use an already-installed vendor browser; never invoke browser acquisition.
  const channel = process.env.AYURSAGE_BROWSER_CHANNEL || 'chrome';
  assert.ok(['chrome', 'msedge'].includes(channel), 'Use an installed chrome or msedge channel.');
  browser = await chromium.launch({ headless: true, channel });
  t.diagnostic(`Real browser: Chromium ${browser.version()}; verified ${databaseInfo.dialect}; no model execution.`);
  const pageFor = async () => {
    const context = await browser.newContext();
    // Only real loopback application traffic is allowed; no network response mocks.
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    return page;
  };
  const patientPage = await pageFor(), doctorPage = await pageFor(), otherPage = await pageFor();
  const login = async (page, email) => {
    await page.goto(origin + '/#/login');
    await page.getByLabel('Email', { exact: true }).fill(email);
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.getByRole('button', { name: 'Log out', exact: true }).waitFor();
  };
  if (adminGrants) {
    const adminPage = otherPage;
    const revoke = async () => {
      await adminPage.getByRole('button', { name: `Revoke grant ${grant.id} for doctor ${doctorUser.id}`, exact: true }).click();
      const response = adminPage.waitForResponse(r => r.url().endsWith(`/${grant.id}/revoke`) && r.request().method() === 'POST');
      await adminPage.getByRole('button', { name: 'Confirm revocation', exact: true }).click();
      assert.equal((await response).status(), 200);
      await adminPage.getByText(`Grant #${grant.id} revoked. Refresh grants to reload the full history.`, { exact: true }).waitFor();
    };
    await t.test('authorized administrator loads nonclinical metadata and revokes an existing grant', async () => {
      await login(adminPage, 'admin@example.invalid');
      await adminPage.getByRole('link', { name: 'Manage patient–doctor grants', exact: true }).click();
      await adminPage.getByLabel('Patient profile ID', { exact: true }).fill(String(patient.id));
      await adminPage.getByRole('button', { name: 'Load patient grants', exact: true }).click();
      await adminPage.getByRole('button', { name: `Revoke grant ${grant.id} for doctor ${doctorUser.id}`, exact: true }).waitFor();
      assert.equal(await adminPage.getByText('SYNTHETIC BROWSER ASSESSMENT ONLY', { exact: true }).count(), 0);
      await revoke();
    });
    const prepare = async (reference, review) => {
      await adminPage.getByLabel('Doctor account ID', { exact: true }).fill(String(doctorUser.id));
      await adminPage.getByLabel('Retained consent reference', { exact: true }).fill(reference);
      const permission = adminPage.getByRole('checkbox', { name: 'Permit doctor-authored clinical review and prescription recording', exact: true });
      assert.equal(await permission.isChecked(), false);
      if (review) await permission.check();
      await adminPage.getByRole('checkbox', { name: 'I verified retained consent for this patient, doctor, selected permissions and 30-day access.', exact: true }).check();
      await adminPage.getByRole('button', { name: 'Review grant before issuing', exact: true }).click();
      await adminPage.getByRole('region', { name: 'Confirm grant issuance', exact: true }).waitFor();
    };
    const issue = async () => {
      const response = adminPage.waitForResponse(r => r.url().endsWith(`/patients/${patient.id}/doctor-access-grants`) && r.request().method() === 'POST');
      await adminPage.getByRole('button', { name: 'Confirm issue grant', exact: true }).click();
      const received = await response; assert.equal(received.status(), 201);
      grant = (await received.json()).grant;
      await adminPage.getByText(`Grant #${grant.id} issued. Refresh grants to reload the full history.`, { exact: true }).waitFor();
    };
    await t.test('read-only default is confirmed before issuance; reload preserves server grant history', async () => {
      await prepare('synthetic-admin-browser-read', false);
      await adminPage.getByText('Permission: Read-only', { exact: true }).waitFor();
      await issue(); assert.equal(grant.allow_review, false);
      const id = grant.id;
      await adminPage.reload(); await login(adminPage, 'admin@example.invalid');
      await adminPage.goto(origin + '/#/admin/grants');
      await adminPage.getByLabel('Patient profile ID', { exact: true }).fill(String(patient.id));
      await adminPage.getByRole('button', { name: 'Load patient grants', exact: true }).click();
      await adminPage.getByRole('button', { name: `Revoke grant ${id} for doctor ${doctorUser.id}`, exact: true }).waitFor();
      assert.equal((await owner.patients.getAccessGrants(patient.id)).grants.find(row => row.id === id).allow_review, false);
      await revoke();
    });
    await t.test('review consent is explicit; cancelled confirmation sends no write; revocation persists', async () => {
      await prepare('synthetic-admin-browser-review', true);
      let postCount = 0;
      const count = request => { if (request.method() === 'POST') postCount++; };
      adminPage.on('request', count);
      await adminPage.getByRole('button', { name: 'Cancel issuance', exact: true }).click();
      assert.equal(postCount, 0); adminPage.off('request', count);
      await adminPage.getByRole('button', { name: 'Review grant before issuing', exact: true }).click();
      await issue(); assert.equal(grant.allow_review, true);
      await revoke();
      assert.equal((await owner.patients.getAccessGrants(patient.id)).grants.find(row => row.id === grant.id).status, 'revoked');
      assert.deepEqual((await doctor.patients.getAuthorizedPatients()).patients, []);
    });
    await t.test('administrator role alone is denied by backend and other roles cannot enter the grant page', async () => {
      const forbiddenPage = await pageFor();
      await login(forbiddenPage, 'unprivileged-admin@example.invalid');
      await forbiddenPage.goto(origin + '/#/admin/grants');
      await forbiddenPage.getByLabel('Patient profile ID', { exact: true }).fill(String(patient.id));
      const denied = forbiddenPage.waitForResponse(r => r.url().includes('/doctor-access-grants?') && r.status() === 403);
      await forbiddenPage.getByRole('button', { name: 'Load patient grants', exact: true }).click();
      await denied;
      await forbiddenPage.getByRole('alert').filter({ hasText: 'Administrator role alone is insufficient' }).waitFor();
      assert.equal(await forbiddenPage.getByRole('button', { name: 'Review grant before issuing', exact: true }).count(), 0);
      await login(patientPage, 'browser-patient@example.invalid');
      await patientPage.goto(origin + '/#/admin/grants');
      await patientPage.getByRole('heading', { name: 'Access restricted', exact: true }).waitFor();
    });
    return;
  }
  await t.test('patient sees issued grant on My Profile', async () => {
    await login(patientPage, 'browser-patient@example.invalid');
    await patientPage.getByRole('navigation').getByRole('link', { name: 'My profile', exact: true }).click();
    await patientPage.getByRole('button', { name: `Revoke grant ${grant.id} for doctor ${doctorUser.id}` }).waitFor();
    assert.equal(await patientPage.getByRole('cell', { name: 'Active', exact: true }).count(), 1);
  });
  await t.test('doctor selects only authorized patient and reads stored assessment fields', async () => {
    await login(doctorPage, 'doctor@example.invalid');
    await doctorPage.getByRole('link', { name: 'Open assessment viewer' }).click();
    await doctorPage.getByRole('link', { name: `Patient #${patient.id} — View assessment history`, exact: true }).waitFor();
    assert.equal(await doctorPage.getByRole('link', { name: /Patient #\d+ — View assessment history/ }).count(), 1);
    assert.equal(await doctorPage.getByRole('link', { name: `Patient #${unrelatedPatient.id} — View assessment history`, exact: true }).count(), 0);
    await doctorPage.getByRole('link', { name: `Patient #${patient.id} — View assessment history`, exact: true }).click();
    await doctorPage.getByRole('link', { name: `Assessment #${saved.id}`, exact: true }).click();
    await doctorPage.getByText('SYNTHETIC BROWSER ASSESSMENT ONLY', { exact: true }).waitFor();
    assert.equal(await doctorPage.getByText('Synthetic access test', { exact: true }).count(), 8);
    assert.equal(await doctorPage.locator('dd').filter({ hasText: /^0$/ }).count(), 4);
    assert.equal(await doctorPage.locator('time').first().getAttribute('datetime'), saved.created_at);
    assert.equal(await doctorPage.getByRole('link', { name: `Patient #${unrelatedPatient.id} — View assessment history`, exact: true }).count(), 0);
    assert.equal(await doctorPage.locator('textarea').count(), 0);
  });
  await t.test('other doctor and unrelated/unauthorized roles gain no clinical access', async () => {
    await login(otherPage, 'other-doctor@example.invalid');
    await otherPage.getByRole('link', { name: 'Open assessment viewer' }).click();
    await otherPage.getByText('No patients are currently authorized for assessment access.', { exact: true }).waitFor();
    await otherPage.goto(`${origin}/#/doctor/patients/${patient.id}/assessments/${saved.id}`);
    await otherPage.getByRole('alert').filter({ hasText: 'Access denied.' }).waitFor();
    assert.equal(await otherPage.getByText('SYNTHETIC BROWSER ASSESSMENT ONLY', { exact: true }).count(), 0);
    for (const actor of [owner, unrelated, admin, reception]) {
      await assert.rejects(actor.patients.getAuthorizedPatients(), error => error.status === 403);
    }
    for (const actor of [otherDoctor, admin, reception]) {
      await assert.rejects(actor.patients.getAssessment(patient.id, saved.id), error => error.status === 403);
    }
    await assert.rejects(unrelated.patients.getAssessment(patient.id, saved.id), error => error.status === 404);
    await assert.rejects(doctor.patients.getHistory(unrelatedPatient.id), error => error.status === 403);
    const staffPage = await pageFor();
    await login(staffPage, 'receptionist@example.invalid');
    await staffPage.goto(`${origin}/#/doctor/patients/${patient.id}/assessments/${saved.id}`);
    await staffPage.getByRole('heading', { name: 'Access restricted' }).waitFor();
    assert.equal(await staffPage.getByText('SYNTHETIC BROWSER ASSESSMENT ONLY', { exact: true }).count(), 0);
    await patientPage.goto(origin + '/#/doctor/assessments');
    await patientPage.getByRole('heading', { name: 'Access restricted' }).waitFor();
    await patientPage.goto(origin + '/#/patient/profile');
    await patientPage.getByRole('button', { name: `Revoke grant ${grant.id} for doctor ${doctorUser.id}` }).waitFor();
  });
  if (clinicalReview) {
    const reviewUrl = `/patients/${patient.id}/assessments/${saved.id}/reviews`;
    const manual = { expected_version: 0, decision: 'approved', clinical_notes: 'SYNTHETIC browser clinical notes',
      recommendations: Object.fromEntries(outputTargets.map(name => [name, 'SYNTHETIC manual ' + name])),
      prescriptions: [{ medication: 'SYNTHETIC medicine', dose: 'manual dose', route: 'manual route', frequency: 'manual frequency', duration: 'manual duration', instructions: 'manual instructions' }] };
    const submit = (actor, body = manual) => actor.api.request(reviewUrl, { authenticated: true, method: 'POST', body });
    await t.test('read-only consent denies review writes and unauthorized actors cannot read or write reviews', async () => {
      const data = await doctor.api.request(reviewUrl, { authenticated: true });
      assert.equal(data.can_review, false); assert.equal(data.version, 0);
      await assert.rejects(submit(doctor), error => error.status === 403);
      await doctorPage.getByText('Read-only access.', { exact: false }).waitFor();
      assert.equal(await doctorPage.getByRole('button', { name: 'Save clinical review', exact: true }).count(), 0);
      for (const actor of [owner, unrelated, admin, reception, otherDoctor]) {
        await assert.rejects(submit(actor), error => error.status === 403);
        await assert.rejects(actor.api.request(reviewUrl, { authenticated: true }), error => error.status === 403);
      }
      await assert.rejects(doctor.api.request(`/patients/${unrelatedPatient.id}/assessments/${saved.id}/reviews`,
        { authenticated: true, method: 'POST', body: manual }), error => error.status === 403);
    });
    await t.test('explicit review consent enables browser save of human notes, recommendations and prescription', async () => {
      await owner.patients.revokeAccessGrant(patient.id, grant.id);
      grant = (await admin.api.request(`/patients/${patient.id}/doctor-access-grants`, { authenticated: true, method: 'POST',
        body: { doctor_user_id: doctorUser.id, consent_reference: 'synthetic-browser-clinical-review-consent', allow_review: true } })).grant;
      assert.equal(grant.allow_review, true);
      await doctorPage.getByRole('button', { name: 'Refresh assessment', exact: true }).click();
      await doctorPage.getByLabel('Clinical notes (required)', { exact: true }).fill(manual.clinical_notes);
      for (const name of outputTargets) await doctorPage.getByLabel(`${name} (doctor-entered, required)`, { exact: true }).fill(manual.recommendations[name]);
      await doctorPage.getByRole('button', { name: 'Add prescription', exact: true }).click();
      for (const [name, value] of Object.entries(manual.prescriptions[0])) await doctorPage.getByLabel(name, { exact: true }).fill(value);
      await doctorPage.getByLabel('Decision', { exact: true }).selectOption('returned_for_changes');
      const response = doctorPage.waitForResponse(r => r.url().endsWith('/reviews') && r.request().method() === 'POST');
      await doctorPage.getByRole('button', { name: 'Save clinical review', exact: true }).click();
      const received = await response; assert.equal(received.status(), 201);
      const data = await received.json(); const review = data.reviews[0];
      assert.equal(data.version, 1); assert.equal(review.actor_user_id, doctorUser.id);
      assert.equal(review.origin, 'doctor_entered'); assert.match(review.decided_at, /Z$/);
      assert.ok(Number.isFinite(Date.parse(review.decided_at)));
      assert.deepEqual(review.recommendations, manual.recommendations); assert.deepEqual(review.prescriptions, manual.prescriptions);
      assert.equal(review.clinical_notes, manual.clinical_notes);
      await doctorPage.getByText('Clinical review saved.', { exact: true }).waitFor();
    });
    await t.test('full reload persists history; revised resubmission and approval append immutable decisions', async () => {
      const original = (await doctor.api.request(reviewUrl, { authenticated: true })).reviews[0];
      await doctorPage.reload(); await login(doctorPage, 'doctor@example.invalid');
      await doctorPage.goto(`${origin}/#/doctor/patients/${patient.id}/assessments/${saved.id}`);
      await doctorPage.getByRole('heading', { name: 'Review #1: Returned for changes', exact: true }).waitFor();
      assert.equal(await doctorPage.getByLabel('Clinical notes (required)', { exact: true }).inputValue(), manual.clinical_notes);
      assert.equal(await doctorPage.getByLabel('medication', { exact: true }).inputValue(), manual.prescriptions[0].medication);
      await doctorPage.getByLabel('Clinical notes (required)', { exact: true }).fill('SYNTHETIC revised clinical notes');
      await doctorPage.getByLabel(`${outputTargets[0]} (doctor-entered, required)`, { exact: true }).fill('SYNTHETIC revised recommendation');
      let response = doctorPage.waitForResponse(r => r.url().endsWith('/reviews') && r.request().method() === 'POST');
      await doctorPage.getByRole('button', { name: 'Save clinical review', exact: true }).click();
      assert.equal((await response).status(), 201);
      await doctorPage.getByRole('heading', { name: 'Review #2: Pending review', exact: true }).waitFor();
      await doctorPage.getByLabel('Decision', { exact: true }).selectOption('approved');
      response = doctorPage.waitForResponse(r => r.url().endsWith('/reviews') && r.request().method() === 'POST');
      await doctorPage.getByRole('button', { name: 'Save clinical review', exact: true }).click();
      assert.equal((await response).status(), 201);
      await doctorPage.getByRole('heading', { name: 'Review #3: Approved', exact: true }).waitFor();
      assert.equal(await doctorPage.getByRole('button', { name: 'Save clinical review', exact: true }).count(), 0);
      const history = await doctor.api.request(reviewUrl, { authenticated: true });
      assert.equal(history.version, 3); assert.deepEqual(history.reviews[0], original);
      assert.deepEqual(history.reviews.map(r => r.sequence), [1, 2, 3]);
      assert.ok(history.reviews.every(r => r.actor_user_id === doctorUser.id && r.decided_at.endsWith('Z')));
      await assert.rejects(submit(doctor), error => error.status === 409);
      await assert.rejects(submit(doctor, { ...manual, expected_version: 3 }), error => error.status === 409);
      await patientPage.getByRole('button', { name: 'Refresh doctor access', exact: true }).click();
      await patientPage.getByRole('button', { name: `Revoke grant ${grant.id} for doctor ${doctorUser.id}` }).waitFor();
      await patientPage.getByText('Clinical review permitted', { exact: false }).waitFor();
    });
  }
  await t.test('patient UI revokes; next doctor request is 403 and removes stale clinical details', async () => {
    await patientPage.getByRole('button', { name: `Revoke grant ${grant.id} for doctor ${doctorUser.id}` }).click();
    await patientPage.getByRole('button', { name: 'Confirm revocation', exact: true }).click();
    await patientPage.getByText(`Access grant #${grant.id} was revoked.`, { exact: true }).waitFor();
    // Do not assert instantaneous remote removal: explicitly trigger a NEW GET.
    const denied = doctorPage.waitForResponse(response => response.url().endsWith(`/api/patients/${patient.id}/assessments/${saved.id}`)
      && response.request().method() === 'GET' && response.status() === 403);
    await doctorPage.getByRole('button', { name: 'Refresh assessment', exact: true }).click();
    assert.equal((await denied).status(), 403);
    await doctorPage.getByRole('alert').filter({ hasText: 'Access denied.' }).waitFor();
    assert.equal(await doctorPage.getByText('SYNTHETIC BROWSER ASSESSMENT ONLY', { exact: true }).count(), 0);
    assert.equal(await doctorPage.getByText('Synthetic access test', { exact: true }).count(), 0);
    assert.equal(await doctorPage.locator('dd').count(), 0);
    await doctorPage.getByRole('link', { name: 'Back to authorized patients', exact: true }).click();
    await doctorPage.getByText('No patients are currently authorized for assessment access.', { exact: true }).waitFor();
    assert.equal(await doctorPage.getByRole('link', { name: `Patient #${patient.id} — View assessment history`, exact: true }).count(), 0);
    await assert.rejects(doctor.patients.getHistory(patient.id), error => error.status === 403);
    await assert.rejects(doctor.patients.getAssessment(patient.id, saved.id), error => error.status === 403);
    assert.deepEqual((await doctor.patients.getAuthorizedPatients()).patients, []);
    if (clinicalReview) {
      const url = `/patients/${patient.id}/assessments/${saved.id}/reviews`;
      await assert.rejects(doctor.api.request(url, { authenticated: true }), error => error.status === 403);
      await assert.rejects(doctor.api.request(url, { authenticated: true, method: 'POST', body: { expected_version: 3 } }), error => error.status === 403);
      assert.equal(await doctorPage.getByText('SYNTHETIC revised clinical notes', { exact: true }).count(), 0);
    }
  });
});
