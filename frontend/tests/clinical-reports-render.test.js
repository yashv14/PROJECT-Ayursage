import assert from 'node:assert/strict';
import { test, before, after } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
let vite, Screen;
before(async () => {
  vite = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' });
  Screen = (await vite.ssrLoadModule('/src/pages/ClinicalReportPanel.jsx')).ClinicalReportScreen;
});
after(async () => { await vite?.close(); });
const render = state => renderToStaticMarkup(React.createElement(Screen, { state }));
test('approval gate shows status without issuance or download controls', () => {
  const markup = render({ status: 'ready', data: { status: 'awaiting_approval', can_generate: false, report: null } });
  assert.match(markup,/Doctor approval is required/); assert.doesNotMatch(markup,/Issue approved PDF|Download approved PDF/);
});
test('issuance and one download control follow authoritative report availability', () => {
  assert.match(render({ status: 'ready', data: { status: 'not_issued', can_generate: true, report: null } }),/Issue approved PDF report/);
  const markup = render({ status: 'ready', data: { status: 'available', can_generate: false, report: { version: 1, issued_at: 'synthetic' } } });
  assert.equal((markup.match(/Download approved PDF/g)||[]).length,1); assert.doesNotMatch(markup,/Issue approved PDF/);
});
test('denial and expired-link errors expose no stale metadata or signed capability', () => {
  const markup = render({ status: 'error', data: null, error: 'Report access denied or the download link expired.' });
  assert.match(markup,/link expired/); assert.doesNotMatch(markup,/Download approved PDF|Report version|X-Report-Link/);
});
