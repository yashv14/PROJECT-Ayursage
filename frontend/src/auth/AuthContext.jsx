import { createContext, useContext, useEffect, useState, useSyncExternalStore } from 'react';
import { createApiClient } from '../services/api.js';
import { createAuthService } from '../services/auth.js';
import { createSession } from './session.js';
import { createPatientService } from '../services/patients.js';
import { createReceptionService } from '../services/reception.js';
import { createReviewService } from '../doctor/review.js';
import { createReportService } from '../services/reports.js';

const AuthContext = createContext(null);
export function AuthProvider({ children }) {
  const [session] = useState(() => {
    const api = createApiClient({ baseUrl: import.meta.env.VITE_API_BASE_URL || '/api' });
    return { ...createSession(api, createAuthService(api)), patients: createPatientService(api), reception: createReceptionService(api), reviews: createReviewService(api), reports: createReportService(api) };
  });
  const state = useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot);
  useEffect(() => session.connect(), [session]);
  return <AuthContext.Provider value={{ ...state, login: session.login, logout: session.logout, register: session.register, patients: session.patients, reception: session.reception, reviews: session.reviews, reports: session.reports }}>
    {children}
  </AuthContext.Provider>;
}
export function useAuth() { return useContext(AuthContext); }
