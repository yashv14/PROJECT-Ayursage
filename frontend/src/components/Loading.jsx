export function Loading({ label = 'Loading…' }) {
  return <span role="status"><span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />{label}</span>;
}
