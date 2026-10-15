import assert from 'node:assert/strict';
import test from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

test('React pages render accessible registration/login, anonymous navigation and loading state', async t => {
  const vite = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' });
  t.after(() => vite.close());
  const { AuthProvider } = await vite.ssrLoadModule('/src/auth/AuthContext.jsx');
  const { AuthPage } = await vite.ssrLoadModule('/src/pages/AuthPage.jsx');
  const { AppShell } = await vite.ssrLoadModule('/src/components/AppShell.jsx');
  const { Loading } = await vite.ssrLoadModule('/src/components/Loading.jsx');
  const render = registration => renderToStaticMarkup(React.createElement(AuthProvider, null,
    React.createElement(AppShell, null, React.createElement(AuthPage, { registration }))));
  const login = render(false);
  const registration = render(true);
  assert.match(login, /Welcome back/);
  assert.match(login, /autoComplete="current-password"/);
  assert.match(login, /aria-label="Main navigation"/);
  assert.match(login, /id="main-content"/);
  assert.match(registration, /Create your patient account/);
  assert.match(registration, /id="confirmation"/);
  assert.match(registration, /Use 12–128 characters/);
  assert.doesNotMatch(registration, /<select|\/patients\/|\/reviews\/|\/predict/);
  const loading = renderToStaticMarkup(React.createElement(Loading, { label: 'Signing in…' }));
  assert.match(loading, /role="status"/);
  assert.match(loading, /Signing in/);
});
