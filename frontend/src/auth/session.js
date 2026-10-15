// Authentication state and token lifetime are independent of React rendering.
export function createSession(api, service, { schedule = setTimeout, cancel = clearTimeout } = {}) {
  let state = { user: null, notice: '', busy: false };
  let timer;
  let generation = 0;
  const listeners = new Set();
  const update = changes => {
    state = { ...state, ...changes };
    listeners.forEach(listener => listener());
  };
  function logout(notice = '') {
    generation++;
    cancel(timer);
    api.setToken(null);
    update({ user: null, notice });
  }
  return {
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    connect() {
      api.setUnauthorizedHandler(() => logout('Your session expired. Please sign in again.'));
      return () => {
        generation++;
        cancel(timer);
        api.setToken(null);
        api.setUnauthorizedHandler(() => {});
      };
    },
    logout,
    register: service.register,
    async login(email, password) {
      if (state.busy) return;
      const attempt = ++generation;
      update({ busy: true, notice: '' });
      try {
        const result = await service.login(email, password);
        if (attempt !== generation) { api.setToken(null); return; }
        cancel(timer);
        timer = schedule(() => logout('Your session expired. Please sign in again.'), result.expiresIn * 1000);
        update({ user: result.user });
      } finally { update({ busy: false }); }
    },
  };
}
