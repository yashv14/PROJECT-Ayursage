import { emptyInputs, prepareAssessment } from './assessmentFields.js';

export function createPatientWorkspace(service) {
  let state = {
    profile: { status: 'loading', data: null, error: '', notice: '' },
    form: { values: emptyInputs(), notes: '', predict: false, prediction: null, errors: {}, status: 'idle', error: '', saved: null },
    history: { status: 'idle', items: [], nextAfterId: null, error: '' },
    detail: { status: 'idle', data: null, error: '', requestedId: null },
    grants: { status: 'idle', items: [], nextAfterId: null, error: '', notice: '', confirmingId: null },
  };
  const listeners = new Set();
  const versions = { profile: 0, form: 0, history: 0, detail: 0, grants: 0 };
  let active = true;
  const update = (key, changes) => {
    if (!active) return;
    state = { ...state, [key]: { ...state[key], ...changes } };
    listeners.forEach(listener => listener());
  };
  async function run(key, status, operation, success, failure = () => ({})) {
    const version = ++versions[key];
    update(key, { status, error: '' });
    try {
      const result = await operation();
      if (active && versions[key] === version) update(key, { status: 'ready', ...success(result) });
    } catch (error) {
      if (active && versions[key] === version) update(key, { status: 'error', error: error.message, ...failure(error) });
    }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    connect() {
      active = true;
      return () => { active = false; Object.keys(versions).forEach(key => versions[key]++); };
    },
    loadProfile() {
      versions.grants++;
      update('grants', { status: 'idle', items: [], nextAfterId: null, error: '', notice: '', confirmingId: null });
      update('profile', { data: null, notice: '' });
      return run('profile', 'loading', () => service.getProfile(), data => ({ data }));
    },
    createProfile() {
      if (state.profile.status === 'creating') return;
      return run('profile', 'creating', () => service.createProfile(), data => ({ data, notice: 'Your patient profile is ready.' }));
    },
    changeField(name, value) {
      if (!Object.hasOwn(state.form.values, name) || state.form.status === 'saving') return;
      update('form', { values: { ...state.form.values, [name]: value }, saved: null, prediction: null, error: '', errors: { ...state.form.errors, [name]: undefined } });
    },
    changeNotes(notes) { if (state.form.status !== 'saving') update('form', { notes, saved: null, prediction: null, error: '', errors: { ...state.form.errors, notes: undefined } }); },
    changePredict(predict) {
      if (state.form.status !== 'saving' && typeof predict === 'boolean') {
        update('form', { predict, saved: null, prediction: null, error: '', errors: { ...state.form.errors, form: undefined } });
      }
    },
    resetForm() {
      if (state.form.status !== 'saving') update('form', { values: emptyInputs(), notes: '', predict: false, prediction: null, errors: {}, status: 'idle', error: '', saved: null });
    },
    submit() {
      if (state.form.status === 'saving') return;
      const predict = state.form.predict;
      const { errors, payload } = prepareAssessment(state.form.values, state.form.notes, predict);
      update('form', { errors, error: '', saved: null, prediction: null });
      if (!payload) { update('form', { status: 'invalid' }); return; }
      if (!state.profile.data) { update('form', { status: 'error', error: 'Create or reload your patient profile before saving an assessment.' }); return; }
      return run('form', 'saving', () => service.createAssessment(state.profile.data.id, payload, predict), result => ({
        saved: result.assessment, prediction: result.prediction ?? null,
        error: predict && !result.prediction ? 'The assessment was saved, but the service did not return a prediction.' : '',
      }), error => ({ saved: error.assessment ?? null, prediction: null }));
    },
    loadHistory(more = false) {
      if (!state.profile.data || state.history.status === 'loading') return;
      const afterId = more ? state.history.nextAfterId : 0;
      if (more && afterId === null) return;
      if (!more) update('history', { items: [], nextAfterId: null });
      return run('history', 'loading', () => service.getHistory(state.profile.data.id, afterId), result => ({
        items: more ? [...state.history.items, ...result.assessments] : result.assessments,
        nextAfterId: result.nextAfterId,
      }));
    },
    loadDetail(assessmentId) {
      if (!state.profile.data) return;
      update('detail', { data: null, requestedId: assessmentId });
      return run('detail', 'loading', () => service.getAssessment(state.profile.data.id, assessmentId), data => ({ data }));
    },
    loadGrants(more = false) {
      if (!active || !state.profile.data || ['loading', 'revoking'].includes(state.grants.status)) return;
      const afterId = more ? state.grants.nextAfterId : 0;
      if (more && afterId === null) return;
      update('grants', { notice: '', confirmingId: null, ...(!more ? { items: [], nextAfterId: null } : {}) });
      return run('grants', 'loading', () => service.getAccessGrants(state.profile.data.id, afterId), result => ({
        items: more ? [...state.grants.items, ...result.grants] : result.grants,
        nextAfterId: result.nextAfterId,
      }));
    },
    confirmGrantRevocation(grantId) {
      if (!active || ['loading', 'revoking'].includes(state.grants.status)
          || !state.grants.items.some(row => row.id === grantId && row.status === 'issued')) return;
      update('grants', { confirmingId: grantId, error: '', notice: '' });
    },
    cancelGrantRevocation() {
      if (state.grants.status !== 'revoking') update('grants', { confirmingId: null });
    },
    revokeGrant(grantId) {
      if (!active || !state.profile.data || ['loading', 'revoking'].includes(state.grants.status)
          || state.grants.confirmingId !== grantId
          || !state.grants.items.some(row => row.id === grantId && row.status === 'issued')) return;
      return run('grants', 'revoking', () => service.revokeAccessGrant(state.profile.data.id, grantId), row => ({
        items: state.grants.items.map(item => item.id === row.id ? row : item),
        confirmingId: null, notice: `Access grant #${row.id} was revoked.`,
      }));
    },
  };
}
