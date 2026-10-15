import React from 'react';
import { createRoot } from 'react-dom/client';
import 'bootstrap/dist/css/bootstrap.min.css';
import './styles.css';
import { AuthProvider } from './auth/AuthContext.jsx';
import { AppShell } from './components/AppShell.jsx';
import { Router } from './routing/Router.jsx';

createRoot(document.getElementById('root')).render(
  <React.StrictMode><AuthProvider><AppShell><Router /></AppShell></AuthProvider></React.StrictMode>,
);
