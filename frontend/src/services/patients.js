import { ApiError } from './api.js';
import { categoricalInputs, numericInputs, inputFeatures, outputTargets, validText } from '../patient/assessmentFields.js';

const idValid = id => Number.isInteger(id) && id > 0 && id <= 2147483647;
const unexpected = () => new ApiError('The patient service returned an unexpected response. Please retry.');
function profile(data) {
  if (!idValid(data?.patient?.id) || !idValid(data.patient.owner_user_id)) throw unexpected();
  return data.patient;
}
function assessment(row, patientId) {
  if (!idValid(row?.id) || row.patient_id !== patientId || !idValid(row.recorded_by_user_id)
      || typeof row.created_at !== 'string' || !row.created_at
      || !(row.notes === null || validText(row.notes, 4096))) throw unexpected();
  // Old manual assessments may have inputs:null; never manufacture their inputs.
  if (row.inputs !== null) {
    if (!row.inputs || Array.isArray(row.inputs) || typeof row.inputs !== 'object'
        || Object.keys(row.inputs).length !== inputFeatures.length
        || !categoricalInputs.every(name => validText(row.inputs[name], 256, true))
        || !numericInputs.every(name => typeof row.inputs[name] === 'number' && Number.isFinite(row.inputs[name]))) throw unexpected();
  }
  return row;
}
function resourcePath(patientId) {
  if (!idValid(patientId)) throw unexpected();
  return `/patients/${patientId}/assessments`;
}

function grant(row, patientId) {
  const timestamp = value => typeof value === 'string' && value.endsWith('Z') && Number.isFinite(Date.parse(value));
  if (!idValid(row?.id) || row.patient_id !== patientId || !idValid(row.doctor_user_id)
      || (Object.hasOwn(row, 'allow_review') && typeof row.allow_review !== 'boolean')
      || !idValid(row.issuer_user_id) || !idValid(row.consent_owner_user_id)
      || row.scope !== 'assessment_read' || !['issued', 'expired', 'revoked'].includes(row.status)
      || !validText(row.consent_reference, 256, true)
      || !timestamp(row.issued_at) || !timestamp(row.expires_at)
      || Date.parse(row.expires_at) <= Date.parse(row.issued_at)
      || (row.status === 'revoked'
        ? !idValid(row.revoked_by_user_id) || !timestamp(row.revoked_at) || Date.parse(row.revoked_at) < Date.parse(row.issued_at)
        : row.revoked_by_user_id !== null || row.revoked_at !== null)) throw unexpected();
  return row;
}

function grantPath(patientId) {
  if (!idValid(patientId)) throw unexpected();
  return `/patients/${patientId}/doctor-access-grants`;
}

function validatePrediction(prediction) {
  const outputs = prediction?.outputs;
  if (prediction?.model_version !== 'AyurSage_v17'
      || prediction.status !== 'pending_clinical_review' || prediction.persisted !== false
      || !outputs || typeof outputs !== 'object' || Array.isArray(outputs)
      || Object.keys(outputs).length !== outputTargets.length
      || !outputTargets.every(name => Object.hasOwn(outputs, name) && validText(outputs[name], 4096, true))) {
    throw new ApiError('The assessment was saved, but the prediction response was invalid. No prediction is displayed.');
  }
}

export function createPatientService(api) {
  async function request(path, options = {}) {
    try { return await api.request(path, { ...options, authenticated: true }); }
    catch (error) {
      const detail = error.response?.error;
      const reasons = {
        400: ['invalid_assessment', 'invalid_model_input'],
        503: ['model_unavailable'],
        500: ['inference_error'],
      };
      if (detail?.code === error.status && reasons[error.status]?.includes(detail.reason)
          && validText(detail.message, 512, true)) {
        const modelError = new ApiError(detail.message, error.status);
        modelError.response = error.response;
        throw modelError;
      }
      // Existing API client uses authentication-specific copy for 400/409/503.
      // Override only patient-operation copy, preserving its 401 session handling.
      const messages = {
        400: 'The patient request was rejected. Check all required fields and their types.',
        404: 'The profile or assessment is unavailable to your account.',
        409: 'A patient profile already exists for this account.',
        503: 'The patient service is unavailable. Please try again later.',
      };
      if (messages[error.status]) {
        const patientError = new ApiError(messages[error.status], error.status);
        patientError.response = error.response;
        throw patientError;
      }
      throw error;
    }
  }
  return {
    async issueAccessGrant(patientId, payload) {
      if (!payload || Object.keys(payload).length !== 3 || !idValid(payload.doctor_user_id)
          || !validText(payload.consent_reference, 256, true) || /[\x00-\x1f]/.test(payload.consent_reference)
          || typeof payload.allow_review !== 'boolean') throw new ApiError('Check the doctor ID, consent reference and review permission.', 400);
      let data;
      try { data = await request(grantPath(patientId), { method: 'POST', body: payload }); }
      catch (error) {
        const messages = { 400: 'Grant rejected. Check the doctor ID and recorded consent reference.',
          403: 'Grant-administrator permission is required.',
          404: 'The selected patient is unavailable.',
          409: 'An active grant or reused consent reference already exists. Refresh grants before continuing.' };
        if (messages[error.status]) throw new ApiError(messages[error.status], error.status);
        throw error;
      }
      const row = grant(data.grant, patientId);
      if (row.doctor_user_id !== payload.doctor_user_id || row.allow_review !== payload.allow_review
          || row.consent_reference !== payload.consent_reference.trim() || row.status !== 'issued') throw unexpected();
      return row;
    },
    async getAuthorizedPatients(afterId = 0) {
      if (!Number.isInteger(afterId) || afterId < 0 || afterId > 2147483647) throw unexpected();
      const data = await request(`/patients/authorized?after_id=${afterId}`);
      if (!Array.isArray(data.patients) || data.patients.length > 20
          || !(data.next_after_id === null || idValid(data.next_after_id))) throw unexpected();
      const patients = data.patients.map(row => {
        if (!idValid(row?.id) || Object.keys(row).length !== 1) throw unexpected();
        return { id: row.id };
      });
      if (patients.some((row, index) => row.id <= (index ? patients[index - 1].id : afterId))
          || (data.next_after_id !== null && data.next_after_id !== patients.at(-1)?.id)) throw unexpected();
      return { patients, nextAfterId: data.next_after_id };
    },
    async getAccessGrants(patientId, afterId = 0) {
      if (!Number.isInteger(afterId) || afterId < 0 || afterId > 2147483647) throw unexpected();
      const data = await request(`${grantPath(patientId)}?after_id=${afterId}`);
      if (!Array.isArray(data.grants) || data.grants.length > 20
          || !(data.next_after_id === null || idValid(data.next_after_id))) throw unexpected();
      const rows = data.grants.map(row => grant(row, patientId));
      if (rows.some((row, index) => row.id <= (index ? rows[index - 1].id : afterId))
          || (data.next_after_id !== null && data.next_after_id !== rows.at(-1)?.id)) throw unexpected();
      return { grants: rows, nextAfterId: data.next_after_id };
    },
    async revokeAccessGrant(patientId, grantId) {
      if (!idValid(grantId)) throw unexpected();
      const row = grant((await request(`${grantPath(patientId)}/${grantId}/revoke`, { method: 'POST', body: {} })).grant, patientId);
      if (row.id !== grantId || row.status !== 'revoked') throw unexpected();
      return row;
    },
    async getProfile() {
      try { return profile(await request('/patients/me')); }
      catch (error) { if (error.status === 404) return null; throw error; }
    },
    async createProfile() {
      try { return profile(await request('/patients', { method: 'POST', body: {} })); }
      catch (error) {
        if (error.status !== 409) throw error;
        // A concurrent creation or registration may already have supplied it.
        return profile(await request('/patients/me'));
      }
    },
    async createAssessment(patientId, payload, predict = false) {
      if (typeof predict !== 'boolean') throw new ApiError('predict must be a boolean.', 400);
      let saved = null;
      try {
        const data = await request(resourcePath(patientId), { method: 'POST', body: { ...payload, predict } });
        saved = assessment(data.assessment, patientId);
        if (Object.hasOwn(data, 'prediction')) validatePrediction(data.prediction);
        return data;
      } catch (error) {
        // Retain a valid saved record even if prediction validation fails or
        // an error response explicitly includes the saved assessment.
        if (!saved && error.response?.assessment && [400, 500, 503].includes(error.status)) {
          try { saved = assessment(error.response.assessment, patientId); }
          catch { /* Invalid records are never treated as successful saves. */ }
        }
        if (saved) error.assessment = saved;
        throw error;
      }
    },
    async getHistory(patientId, afterId = 0) {
      if (!Number.isInteger(afterId) || afterId < 0 || afterId > 2147483647) throw unexpected();
      const data = await request(`${resourcePath(patientId)}?limit=20&after_id=${afterId}`);
      if (!Array.isArray(data.assessments) || !(data.next_after_id === null || idValid(data.next_after_id))) throw unexpected();
      const rows = data.assessments.map(row => assessment(row, patientId));
      if (rows.some((row, index) => row.id <= (index ? rows[index - 1].id : afterId))
          || (data.next_after_id !== null && data.next_after_id !== rows.at(-1)?.id)) throw unexpected();
      return { assessments: rows, nextAfterId: data.next_after_id };
    },
    async getAssessment(patientId, assessmentId) {
      if (!idValid(assessmentId)) throw unexpected();
      const row = assessment((await request(`${resourcePath(patientId)}/${assessmentId}`)).assessment, patientId);
      if (row.id !== assessmentId) throw unexpected();
      return row;
    },
  };
}
