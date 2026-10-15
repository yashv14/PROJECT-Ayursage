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
import { categoricalInputs, numericInputs } from '../../src/patient/assessmentFields.js';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const password = 'fixture-password-123';

test('browser: patient grant → doctor directory/history/detail → patient revocation → denied fresh reads', { timeout: 180000 }, async t => {
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
    mysqlChild = spawn(interpreter.executable, ['-B', '-u', 'frontend/tests/e2e/disposable_mysql.py'], {
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
      if (checks) mysqlChecks = JSON.parse(checks[1]);
      if (match && database) { databaseInfo = JSON.parse(database[1]); clearTimeout(timer); resolve(Number(match[1])); }
    });
  });
  assert.equal(databaseInfo.dialect, databaseMode === 'mysql' ? 'mysql' : 'sqlite');
  assert.equal(databaseInfo.migration, '0006_receptionist_appointments');
  if (mysqlTarget) assert.equal(databaseInfo.schema, mysqlTarget.identity.schema);
  if (mysqlTarget) { assert.equal(mysqlChecks?.length, 7); t.diagnostic('MySQL-specific checks passed: ' + mysqlChecks.join(', ')); }
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
  const grant = (await admin.api.request(`/patients/${patient.id}/doctor-access-grants`, { authenticated: true, method: 'POST',
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
  });
});
