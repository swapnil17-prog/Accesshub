export const DEMO_PASSWORD = 'Password@123';
export const DEMO_ACCOUNTS = [
  { role: 'Admin', email: 'admin@accesshub.dev' },
  { role: 'Auditor', email: 'auditor@accesshub.dev' },
  { role: 'Manager', email: 'manager@accesshub.dev' },
  { role: 'App owner', email: 'owner@accesshub.dev' },
  { role: 'Employee', email: 'employee@accesshub.dev' },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validate({ email, password }) {
  const errors = {};
  if (!email.trim()) errors.email = 'Email is required.';
  else if (!EMAIL_RE.test(email.trim())) errors.email = 'Enter a valid email address.';
  if (!password) errors.password = 'Password is required.';
  return errors;
}
