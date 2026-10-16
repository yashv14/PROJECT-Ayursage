import { ApiError } from './api.js';

export function createReportService(api) {
  const path = (patient, assessment) => {
    if (![patient, assessment].every(id => Number.isInteger(id) && id > 0 && id <= 2147483647)) throw new ApiError('Invalid assessment.');
    return `/patients/${patient}/assessments/${assessment}/report`;
  };
  async function request(url, options) {
    try { return await api.request(url, { ...options, authenticated: true }); }
    catch (error) {
      const messages = { 400: 'Report request rejected.', 403: 'Report access denied or the download link expired. Refresh before trying again.',
        404: 'No issued report is available.', 409: 'Doctor approval is required before issuing a report.',
        503: 'Report storage or generation is unavailable. Please retry later.' };
      if (messages[error.status]) throw new ApiError(messages[error.status], error.status);
      throw error;
    }
  }
  return {
    async get(p, a) {
      const data = await request(path(p, a));
      if (!['available', 'not_issued', 'awaiting_approval'].includes(data?.status)
          || typeof data.can_generate !== 'boolean'
          || (data.status === 'available' ? data.report?.assessment_id !== a || data.report.version !== 1 : data.report !== null)) throw new ApiError('Invalid report response.');
      return data;
    },
    issue: (p, a) => request(path(p, a), { method: 'POST', body: {} }),
    async download(p, a) {
      const base = path(p, a);
      const link = await request(base + '/download-link', { method: 'POST', body: {} });
      const prefix = base + '/content#';
      if (link?.expires_in !== 900 || typeof link.url !== 'string' || !link.url.startsWith(prefix)
          || !/^[A-Za-z0-9_.-]{1,2048}$/.test(link.url.slice(prefix.length))) throw new ApiError('Invalid report download link.');
      return request(base + '/content', { responseType: 'blob', downloadToken: link.url.slice(prefix.length) });
    },
  };
}

export function createReportStore(service, patientId, assessmentId, { onAccessDenied = () => {} } = {}) {
  const empty = () => ({ status: 'idle', data: null, error: '' });
  let state = empty(), active = true, busy = false, generation = 0;
  const listeners = new Set();
  const update = value => { state = value; listeners.forEach(listener => listener()); };
  async function run(action, operation) {
    if (!active || busy) return;
    busy = true; const current = ++generation;
    update({ status: action, data: null, error: '' });
    try {
      const result = await operation();
      const data = action === 'downloading' ? null : await service.get(patientId, assessmentId);
      if (active && current === generation) {
        update({ status: action === 'downloading' ? 'downloaded' : 'ready', data, error: '' });
        return result;
      }
    } catch (error) {
      if (active && current === generation) {
        update({ ...empty(), status: 'error', error: error.message });
        if ([401, 403].includes(error.status)) onAccessDenied();
      }
    } finally { if (current === generation) busy = false; }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    connect() { active = true; return () => { active = false; busy = false; generation++; update(empty()); }; },
    load: () => run('loading', async () => {}),
    issue() { if (state.status === 'ready' && state.data?.can_generate) return run('issuing', () => service.issue(patientId, assessmentId)); },
    download() { if (state.status === 'ready' && state.data?.status === 'available') return run('downloading', () => service.download(patientId, assessmentId)); },
  };
}
