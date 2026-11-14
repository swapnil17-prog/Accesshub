import { useEffect, useState } from 'react';
import { useDispatch } from 'react-redux';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import Button from '../../components/Button';
import { AlertIcon, CheckCircleIcon, KeyIcon } from '../../components/icons';
import { useAuth } from '../../hooks/useAuth';
import { clearAuthError } from './authSlice';
import { DEMO_ACCOUNTS, DEMO_PASSWORD, validate } from './loginForm';

const FEATURES = [
  'Request access to business applications in minutes',
  'Multi-level approvals routed to the right people',
  'Full audit trail for compliance reviews',
];

export default function LoginPage() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, loggingIn, error, login } = useAuth();
  const [values, setValues] = useState({ email: '', password: '' });
  const [fieldErrors, setFieldErrors] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const from = location.state?.from?.pathname ?? '/';

  useEffect(() => () => dispatch(clearAuthError()), [dispatch]);

  if (isAuthenticated) return <Navigate to={from} replace />;

  async function signIn(credentials) {
    try {
      await login(credentials);
      navigate(from, { replace: true });
    } catch {
      /* the error message comes from the store */
    }
  }

  function handleChange(event) {
    const next = { ...values, [event.target.name]: event.target.value };
    setValues(next);
    if (submitted) setFieldErrors(validate(next));
  }

  function handleSubmit(event) {
    event.preventDefault();
    setSubmitted(true);
    const errors = validate(values);
    setFieldErrors(errors);
    if (Object.keys(errors).length === 0) signIn({ email: values.email.trim(), password: values.password });
  }

  function demoLogin(email) {
    setValues({ email, password: DEMO_PASSWORD });
    setFieldErrors({});
    signIn({ email, password: DEMO_PASSWORD });
  }

  const inputClass = (hasError) =>
    `block w-full rounded-md border-0 px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset placeholder:text-slate-400 focus:ring-2 focus:ring-inset ${
      hasError ? 'ring-rose-400 focus:ring-rose-500' : 'ring-slate-300 focus:ring-indigo-600'
    }`;

  return (
    <div className="flex min-h-screen bg-white">
      <section className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-slate-900 p-12 text-white lg:flex">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-md bg-indigo-500">
            <KeyIcon className="h-5 w-5" />
          </span>
          <span className="text-lg font-semibold">AccessHub</span>
        </div>
        <div className="max-w-md">
          <h2 className="text-3xl font-semibold leading-tight tracking-tight">
            Access requests without the email chains.
          </h2>
          <ul className="mt-8 space-y-4 text-slate-300">
            {FEATURES.map((feature) => (
              <li key={feature} className="flex gap-3">
                <CheckCircleIcon className="h-5 w-5 shrink-0 text-indigo-400" />
                {feature}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm text-slate-500">Access Request &amp; Approval Portal</p>
      </section>

      <main className="flex flex-1 items-center justify-center px-4 py-12 sm:px-8">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-indigo-600 text-white">
              <KeyIcon className="h-5 w-5" />
            </span>
            <span className="text-lg font-semibold text-slate-900">AccessHub</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Sign in</h1>
          <p className="mt-1 text-sm text-slate-500">Use your work account to continue.</p>

          {error ? (
            <div role="alert" className="mt-6 flex gap-2 rounded-md bg-rose-50 p-3 text-sm text-rose-700">
              <AlertIcon className="h-5 w-5 shrink-0" />
              {error}
            </div>
          ) : null}

          <form className="mt-6 space-y-4" onSubmit={handleSubmit} noValidate>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-700">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                value={values.email}
                onChange={handleChange}
                aria-invalid={Boolean(fieldErrors.email)}
                aria-describedby={fieldErrors.email ? 'email-error' : undefined}
                className={`mt-1 ${inputClass(fieldErrors.email)}`}
              />
              {fieldErrors.email ? (
                <p id="email-error" className="mt-1 text-xs text-rose-600">
                  {fieldErrors.email}
                </p>
              ) : null}
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={values.password}
                onChange={handleChange}
                aria-invalid={Boolean(fieldErrors.password)}
                aria-describedby={fieldErrors.password ? 'password-error' : undefined}
                className={`mt-1 ${inputClass(fieldErrors.password)}`}
              />
              {fieldErrors.password ? (
                <p id="password-error" className="mt-1 text-xs text-rose-600">
                  {fieldErrors.password}
                </p>
              ) : null}
            </div>
            <Button type="submit" size="lg" className="w-full" loading={loggingIn}>
              Sign in
            </Button>
          </form>

          <div className="mt-10">
            <div className="flex items-center gap-3 text-xs font-medium uppercase tracking-wide text-slate-400">
              <span className="h-px flex-1 bg-slate-200" />
              Demo accounts
              <span className="h-px flex-1 bg-slate-200" />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {DEMO_ACCOUNTS.map((account) => (
                <Button
                  key={account.email}
                  variant="secondary"
                  size="sm"
                  disabled={loggingIn}
                  onClick={() => demoLogin(account.email)}
                  className="last:col-span-2"
                >
                  Demo login as {account.role}
                </Button>
              ))}
            </div>
            <p className="mt-3 text-center text-xs text-slate-400">All demo accounts use the password {DEMO_PASSWORD}</p>
          </div>
        </div>
      </main>
    </div>
  );
}
