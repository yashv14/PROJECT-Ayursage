import assert from 'node:assert/strict';
import test from 'node:test';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createServer } from 'vite';
import { createApiClient } from '../src/services/api.js';
import { createAuthService } from '../src/services/auth.js';
import { resolveRoute } from '../src/routing/routes.js';

const root = fileURLToPath(new URL('../../', import.meta.url));

test('Vite HTTP entry and proxy with real Flask auth, migrated disposable SQLite and all three roles', { timeout: 20000 }, async t => {
  const python = process.env.AYURSAGE_TEST_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const child = spawn(python, ['-B', '-u', 'frontend/tests/flask_auth_fixture.py'], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });
  t.after(() => child.kill());
  const port = await new Promise((resolve, reject) => {
    let output = '';
    const timer = setTimeout(() => reject(new Error('Flask fixture did not start.')), 10000);
    child.once('error', error => { clearTimeout(timer); reject(error); });
    child.once('exit', code => { clearTimeout(timer); reject(new Error('Flask fixture exited: ' + code)); });
    child.stderr.resume();
    child.stdout.on('data', chunk => {
      output += chunk;
      const ready = output.match(/READY (\d+)/);
      if (ready) { clearTimeout(timer); resolve(Number(ready[1])); }
    });
  });
  const vite = await createServer({ server: { host: '127.0.0.1', port: 0, strictPort: false,
    proxy: { '/api': { target: `http://127.0.0.1:${port}`, changeOrigin: true } } } });
  t.after(() => vite.close());
  await vite.listen();
  const frontendPort = vite.httpServer.address().port;
  const frontendUrl = `http://127.0.0.1:${frontendPort}`;
  const html = await fetch(frontendUrl);
  assert.equal(html.status, 200);
  assert.match(await html.text(), /AYUR-SAGE/);
  const entry = await fetch(frontendUrl + '/src/main.jsx');
  assert.equal(entry.status, 200);
  const api = createApiClient({ baseUrl: frontendUrl + '/api' });
  const auth = createAuthService(api);
  const email = 'patient@example.invalid';
  const password = 'fixture-password-123';
  const patient = await auth.register(email, password);
  assert.equal(patient.role, 'patient');
  await assert.rejects(auth.register(email, password), error => error.status === 409);
  await assert.rejects(api.request('/auth/register', { method: 'POST', body: { email: 'escalate@example.invalid', password, role: 'doctor' } }), error => error.status === 400);
  await assert.rejects(auth.login(email, 'wrong'), error => error.status === 401 && error.message.includes('incorrect'));
  for (const role of ['patient', 'doctor', 'admin', 'receptionist']) {
    const session = await auth.login(role + '@example.invalid', password);
    assert.equal(session.user.role, role);
    assert.equal(session.expiresIn, 900);
    assert.deepEqual(resolveRoute('/' + role, session.user), { page: 'home' });
    if (role !== 'patient') {
      await assert.rejects(api.request('/patients/me', { authenticated: true }), error => error.status === 403);
    }
    api.setToken(null);
    await assert.rejects(api.request('/auth/me', { authenticated: true }), error => error.status === 401);
  }
  let expired = false;
  api.setUnauthorizedHandler(() => { expired = true; api.setToken(null); });
  api.setToken('invalid-token');
  await assert.rejects(api.request('/auth/me', { authenticated: true }), error => error.status === 401);
  assert.equal(expired, true);
});
