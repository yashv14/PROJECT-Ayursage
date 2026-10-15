import { ApiError } from './api.js';
const validId = value => Number.isInteger(value) && value > 0 && value <= 2147483647;
export const transitions = { scheduled: ['checked_in', 'cancelled', 'no_show'], checked_in: ['completed'], completed: [], cancelled: [], no_show: [] };
function appointment(row) {
  if (!validId(row?.id) || !validId(row.patient_id) || !validId(row.doctor_user_id)
      || !Object.hasOwn(transitions, row.status) || !Number.isFinite(Date.parse(row.starts_at))
      || !(Date.parse(row.ends_at) > Date.parse(row.starts_at))) throw new Error('Unexpected appointment response.');
  return row;
}
export function createReceptionService(api) {
  async function request(path, options = {}) {
    try { return await api.request('/reception' + path, { ...options, authenticated: true }); }
    catch (error) {
      const copy = { 400: 'Check the patient, doctor and times. Use valid dates with a timezone.', 404: 'No matching record was found.', 409: 'The booking conflicts or its status no longer permits that action.', 503: 'Reception services are unavailable. Please retry.' };
      if (copy[error.status]) throw new ApiError(copy[error.status], error.status);
      throw error;
    }
  }
  return {
    async lookup(email) {
      const { patient } = await request('/patients?email=' + encodeURIComponent(email.trim().toLowerCase()));
      if (!validId(patient?.id) || typeof patient.email !== 'string' || !['registered', 'credential_setup_required'].includes(patient.administrative_status)) throw new Error('Unexpected patient response.');
      return patient;
    },
    async doctors(after = 0) {
      const data = await request('/doctors?after_id=' + after);
      if (!Array.isArray(data.doctors) || data.doctors.some(row => !validId(row.id) || typeof row.email !== 'string')
          || !(data.next_after_id === null || validId(data.next_after_id) && data.next_after_id > after)) throw new Error('Unexpected doctor list.');
      return data;
    },
    async list(after = 0) {
      const data = await request('/appointments?after_id=' + after);
      if (!Array.isArray(data.appointments) || !(data.next_after_id === null || validId(data.next_after_id))) throw new Error('Unexpected appointment list.');
      return { ...data, appointments: data.appointments.map(appointment) };
    },
    async create(body) { return appointment((await request('/appointments', { method: 'POST', body })).appointment); },
    async reschedule(id, body) { return appointment((await request(`/appointments/${id}/reschedule`, { method: 'POST', body })).appointment); },
    async status(id, status) { return appointment((await request(`/appointments/${id}/status`, { method: 'POST', body: { status } })).appointment); },
  };
}
