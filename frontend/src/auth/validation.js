export function validateCredentials(email, password, registration = false, confirmation = '') {
  const errors = {};
  const normalized = email.trim().toLowerCase();
  const emailPattern = /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$/;
  const local = normalized.split('@')[0];
  if (normalized.length > 254 || !emailPattern.test(normalized) || local.length > 64
      || local.startsWith('.') || local.endsWith('.') || local.includes('..')) {
    errors.email = 'Enter a valid email address (up to 254 characters).';
  }
  // Python counts Unicode code points rather than JavaScript UTF-16 units.
  const length = [...password].length;
  if (length < (registration ? 12 : 1) || length > 128 || !password.trim() || password.includes('\0')) {
    errors.password = registration ? 'Use 12–128 characters, with at least one non-space character.' : 'Enter your password (up to 128 characters).';
  }
  if (registration && password !== confirmation) errors.confirmation = 'Passwords must match.';
  return errors;
}
