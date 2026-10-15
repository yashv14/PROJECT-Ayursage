export const roleLabels = { patient: 'Patient', doctor: 'Doctor', admin: 'Administrator', receptionist: 'Receptionist' };

function readUser(data) {
  const user = data?.user;
  if (!user || !Number.isInteger(user.id) || user.id < 1 || typeof user.email !== 'string'
      || !Object.hasOwn(roleLabels, user.role)) {
    throw new Error('The service returned an unexpected account. Please try again.');
  }
  return user;
}

export function createAuthService(api) {
  return {
    async register(email, password) {
      return readUser(await api.request('/auth/register', { method: 'POST', body: { email, password } }));
    },
    async login(email, password) {
      const data = await api.request('/auth/login', { method: 'POST', body: { email, password } });
      if (typeof data.access_token !== 'string' || !data.access_token || data.token_type !== 'Bearer'
          || !Number.isInteger(data.expires_in) || data.expires_in < 1 || data.expires_in > 86400) {
        throw new Error('The service returned an unexpected sign-in response. Please try again.');
      }
      api.setToken(data.access_token);
      try {
        const user = readUser(await api.request('/auth/me', { authenticated: true }));
        return { user, expiresIn: data.expires_in };
      } catch (error) {
        api.setToken(null);
        throw error;
      }
    },
  };
}
