const emptyState = () => ({ status: 'idle', items: [], nextAfterId: null, detail: null, error: '', errorStatus: null });
const validId = value => Number.isInteger(value) && value > 0 && value <= 2147483647;

// Read-only state. Every navigation/refresh rechecks access through Flask.
export function createDoctorViewer(service, patientId = null) {
  if (patientId !== null && !validId(patientId)) throw new Error('Enter a valid patient ID.');
  let state = emptyState();
  let active = true;
  let version = 0;
  let pendingKey = null;
  const listeners = new Set();
  const update = value => { state = value; listeners.forEach(listener => listener()); };
  function clear() {
    version++;
    pendingKey = null;
    update(emptyState());
  }
  async function read(key, operation, success) {
    if (!active || pendingKey === key) return;
    const requestVersion = ++version;
    pendingKey = key;
    // Hide previous clinical data even during load-more; a failed recheck must
    // never leave previously fetched records visible as authorized data.
    update({ ...emptyState(), status: 'loading' });
    try {
      const result = await operation();
      if (active && version === requestVersion) update({ ...emptyState(), status: 'ready', ...success(result) });
    } catch (error) {
      if (active && version === requestVersion) {
        const message = error.status === 403
          ? 'Access denied. A current assessment-read grant is required; it may be absent, expired or revoked.'
          : error.status === 404 ? 'This assessment is unavailable for the selected patient.' : error.message;
        update({ ...emptyState(), status: 'error', error: message, errorStatus: error.status ?? null });
      }
    } finally {
      if (version === requestVersion) pendingKey = null;
    }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    connect() {
      active = true;
      return () => { active = false; clear(); };
    },
    clear,
    loadDirectory(more = false) {
      if (pendingKey !== null) return;
      if (more && (state.status !== 'ready' || state.nextAfterId === null)) return;
      const afterId = more ? state.nextAfterId : 0;
      return read(`directory:${afterId}`, () => service.getAuthorizedPatients(afterId), result => ({
        // Each page is a fresh authorization snapshot. Do not append patients
        // from an older page whose grant may since have expired or been revoked.
        items: result.patients, nextAfterId: result.nextAfterId,
      }));
    },
    loadHistory(more = false) {
      if (pendingKey !== null) return;
      if (more && (state.status !== 'ready' || state.nextAfterId === null)) return;
      const afterId = more ? state.nextAfterId : 0;
      const previous = more ? state.items : [];
      return read(`history:${afterId}`, () => service.getHistory(patientId, afterId), result => ({
        items: [...previous, ...result.assessments], nextAfterId: result.nextAfterId,
      }));
    },
    loadDetail(assessmentId) {
      if (!validId(assessmentId)) { clear(); return; }
      return read(`detail:${assessmentId}`, () => service.getAssessment(patientId, assessmentId), detail => ({ detail }));
    },
  };
}
