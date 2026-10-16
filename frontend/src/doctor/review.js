import { ApiError } from '../services/api.js';
import { outputTargets, validText } from '../patient/assessmentFields.js';

export const prescriptionFields = ['medication', 'dose', 'route', 'frequency', 'duration', 'instructions'];
const states = ['pending_review', 'approved', 'returned_for_changes'];
const id = value => Number.isInteger(value) && value > 0 && value <= 2147483647;
function validate(data, assessmentId) {
  const invalid = () => { throw new ApiError('The review service returned an invalid response. Refresh before continuing.'); };
  if (data?.assessment_id !== assessmentId || !states.includes(data.state) || typeof data.can_review !== 'boolean'
      || !Number.isInteger(data.version) || data.version < 0 || data.version > 100
      || !Array.isArray(data.reviews) || data.reviews.length !== data.version) invalid();
  let previous = 'pending_review';
  data.reviews.forEach((row, index) => {
    if (!id(row?.id) || !id(row.actor_user_id) || row.sequence !== index + 1 || row.from_state !== previous
        || !(previous === 'pending_review' ? ['approved', 'returned_for_changes'].includes(row.decision)
          : previous === 'returned_for_changes' && row.decision === 'pending_review')
        || typeof row.decided_at !== 'string' || !row.decided_at.endsWith('Z') || !Number.isFinite(Date.parse(row.decided_at))
        || !(row.clinical_notes === null || validText(row.clinical_notes, 4096))) invalid();
    if (row.origin === 'doctor_entered') {
      if (!row.recommendations || Array.isArray(row.recommendations)
          || Object.keys(row.recommendations).length !== outputTargets.length
          || !outputTargets.every(name => validText(row.recommendations[name], 2048, true))
          || !Array.isArray(row.prescriptions) || row.prescriptions.length > 10
          || row.prescriptions.some(item => !item || Object.keys(item).length !== prescriptionFields.length
            || !prescriptionFields.every(name => validText(item[name], 256, name !== 'instructions')))) invalid();
    } else if (row.origin !== 'legacy_unclassified' || row.recommendations !== null || row.prescriptions !== null) invalid();
    previous = row.decision;
  });
  if (previous !== data.state) invalid();
  return data;
}

export function createReviewService(api) {
  const path = (patientId, assessmentId) => {
    if (!id(patientId) || !id(assessmentId)) throw new ApiError('Invalid assessment.');
    return `/patients/${patientId}/assessments/${assessmentId}/reviews`;
  };
  async function request(patientId, assessmentId, options) {
    try {
      return validate(await api.request(path(patientId, assessmentId), { ...options, authenticated: true }), assessmentId);
    } catch (error) {
      const messages = { 400: 'Review rejected. Check the required fields and their lengths.',
        403: 'Review access denied. Explicit review permission and a current read grant are required.',
        404: 'The assessment is unavailable.', 409: 'The review changed or this decision is no longer allowed. Refresh before saving.',
        503: 'The review service is unavailable. Please retry.' };
      if (messages[error.status]) throw new ApiError(messages[error.status], error.status);
      throw error;
    }
  }
  return {
    get: (patientId, assessmentId) => request(patientId, assessmentId),
    save: (patientId, assessmentId, payload) => request(patientId, assessmentId, { method: 'POST', body: payload }),
  };
}

const empty = () => ({ status: 'idle', data: null, error: '', notice: '' });
export function createReviewStore(service, patientId, assessmentId, { onAccessDenied = () => {} } = {}) {
  let state = empty(), active = true, generation = 0, busy = false;
  const listeners = new Set();
  const update = value => { state = value; listeners.forEach(listener => listener()); };
  async function run(operation, saving) {
    if (!active || busy) return;
    busy = true;
    const version = ++generation;
    const data = state.data;
    update({ ...empty(), data: saving ? data : null, status: saving ? 'saving' : 'loading' });
    try {
      const result = await operation();
      if (active && generation === version) update({ ...empty(), status: 'ready', data: result, notice: saving ? 'Clinical review saved.' : '' });
    } catch (error) {
      if (active && generation === version) {
        update({ ...empty(), status: 'error', error: error.message });
        if ([401, 403].includes(error.status)) onAccessDenied();
      }
    } finally { if (generation === version) busy = false; }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    connect() { active = true; return () => { active = false; generation++; busy = false; update(empty()); }; },
    load: () => run(() => service.get(patientId, assessmentId), false),
    save(payload) {
      if (state.status !== 'ready' || !state.data?.can_review || state.data.state === 'approved') return;
      return run(() => service.save(patientId, assessmentId, { ...payload, expected_version: state.data.version }), true);
    },
  };
}
