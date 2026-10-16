import { validText } from '../patient/assessmentFields.js';

export function grantId(text) {
  if (typeof text !== 'string' || !/^[1-9]\d*$/.test(text) || Number(text) > 2147483647) throw new Error('Enter a valid positive account or patient ID.');
  return Number(text);
}
const empty = () => ({ status: 'idle', patientId: null, items: [], nextAfterId: null,
  error: '', notice: '', confirmingId: null, issueCandidate: null });
export function createGrantAdmin(service) {
  let state = empty(), active = true, busy = false, version = 0;
  const listeners = new Set();
  const update = value => { state = value; listeners.forEach(listener => listener()); };
  async function run(status, operation, success) {
    if (!active || busy) return;
    busy = true; const current = ++version;
    update({ ...state, status, error: '', notice: '', items: [] });
    try {
      const result = await operation();
      if (active && version === current) update({ ...state, status: 'ready', ...success(result) });
    } catch (error) {
      if (active && version === current) update({ ...state, status: 'error', items: [], nextAfterId: null,
        issueCandidate: null, confirmingId: null,
        error: error.status === 403 ? 'Grant-administrator permission is required. Administrator role alone is insufficient.' : error.message });
    } finally { if (version === current) busy = false; }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    connect() { active = true; return () => { active = false; busy = false; version++; update(empty()); }; },
    load(patientText, more = false) {
      if (busy || !active) return;
      let patientId;
      try { patientId = grantId(patientText); }
      catch (error) { update({ ...empty(), status: 'error', error: error.message }); return; }
      if (more && (state.status !== 'ready' || state.patientId !== patientId || state.nextAfterId === null)) return;
      const cursor = more ? state.nextAfterId : 0;
      const previous = more ? state.items : [];
      update({ ...empty(), patientId });
      return run('loading', () => service.getAccessGrants(patientId, cursor), result => ({
        items: [...previous, ...result.grants], nextAfterId: result.nextAfterId,
      }));
    },
    prepareIssue({ doctorId, reference, allowReview, attested }) {
      if (busy || state.status !== 'ready') return;
      try {
        const doctor_user_id = grantId(doctorId);
        if (!validText(reference, 256, true) || /[\x00-\x1f]/.test(reference)
            || typeof allowReview !== 'boolean' || attested !== true) throw new Error('Confirm the retained consent evidence and complete all required fields.');
        update({ ...state, error: '', notice: '', confirmingId: null,
          issueCandidate: { doctor_user_id, consent_reference: reference.trim(), allow_review: allowReview } });
      } catch (error) { update({ ...state, error: error.message, issueCandidate: null }); }
    },
    cancel() { if (!busy) update({ ...state, issueCandidate: null, confirmingId: null }); },
    issue() {
      if (busy || !state.issueCandidate || state.status !== 'ready') return;
      const { patientId, issueCandidate } = state;
      return run('issuing', () => service.issueAccessGrant(patientId, issueCandidate), row => ({
        items: [row], nextAfterId: null, issueCandidate: null, confirmingId: null,
        notice: `Grant #${row.id} issued. Refresh grants to reload the full history.`,
      }));
    },
    confirmRevoke(id) {
      if (!busy && state.status === 'ready' && state.items.some(row => row.id === id && row.status === 'issued')) {
        update({ ...state, confirmingId: id, issueCandidate: null, notice: '', error: '' });
      }
    },
    revoke(id) {
      if (busy || state.status !== 'ready' || state.confirmingId !== id) return;
      const patientId = state.patientId;
      return run('revoking', () => service.revokeAccessGrant(patientId, id), row => ({
        items: [row], nextAfterId: null, confirmingId: null,
        notice: `Grant #${row.id} revoked. Refresh grants to reload the full history.`,
      }));
    },
  };
}
