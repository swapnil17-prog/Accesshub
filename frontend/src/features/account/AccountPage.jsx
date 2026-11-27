import { useState } from 'react';
import { useDispatch } from 'react-redux';

import Button from '../../components/Button';
import { Field, TextInput } from '../../components/form';
import PageHeader from '../../components/PageHeader';
import PasswordChecklist from '../../components/PasswordChecklist';
import { useToast } from '../../components/toastContext';
import { useAuth } from '../../hooks/useAuth';
import { ROLE_LABELS } from '../../navigation';
import { describedBy } from '../../utils/forms';
import { changePassword } from '../auth/authSlice';

const EMPTY = { current: '', next: '', confirm: '' };

function Detail({ label, children }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm text-slate-900">{children}</dd>
    </div>
  );
}

const joinMessages = (value) => (Array.isArray(value) ? value.join(' ') : value);

/** The signed-in user's profile and the "change my password" form. */
export default function AccountPage() {
  const dispatch = useDispatch();
  const toast = useToast();
  const { user, roles } = useAuth();
  const [values, setValues] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  function update(field) {
    return (event) => {
      setValues((current) => ({ ...current, [field]: event.target.value }));
      setErrors((current) => ({ ...current, [field]: undefined }));
    };
  }

  async function submit(event) {
    event.preventDefault();
    const found = {};
    if (!values.current) found.current = 'Enter your current password.';
    if (!values.next) found.next = 'Enter a new password.';
    if (values.next && values.confirm !== values.next) found.confirm = "The passwords don't match.";
    setErrors(found);
    if (Object.keys(found).length) return;

    setSaving(true);
    const result = await dispatch(changePassword({ currentPassword: values.current, newPassword: values.next }));
    setSaving(false);
    if (changePassword.fulfilled.match(result)) {
      setValues(EMPTY);
      toast.success('Your other sessions were signed out.', 'Password changed');
      return;
    }
    const details = result.payload?.details ?? {};
    if (details.current_password || details.new_password) {
      setErrors({ current: joinMessages(details.current_password), next: joinMessages(details.new_password) });
    } else {
      toast.error(result.payload?.message ?? 'Could not change your password.');
    }
  }

  return (
    <>
      <PageHeader title="Your account" description="Your profile and sign-in settings." />
      <div className="grid gap-6 lg:grid-cols-3">
        <section className="rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h2 className="text-sm font-semibold text-slate-900">Profile</h2>
          <dl className="mt-4 space-y-4">
            <Detail label="Name">{user?.name}</Detail>
            <Detail label="Email">{user?.email}</Detail>
            <Detail label="Department">{user?.department || '—'}</Detail>
            <Detail label="Roles">{roles.map((role) => ROLE_LABELS[role] ?? role).join(', ')}</Detail>
          </dl>
          <p className="mt-4 text-xs text-slate-500">To change these details, ask an administrator.</p>
        </section>

        <section className="rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200 lg:col-span-2">
          <h2 className="text-sm font-semibold text-slate-900">Change password</h2>
          <p className="mt-1 text-sm text-slate-500">You&apos;ll stay signed in here; other devices will be signed out.</p>
          <form onSubmit={submit} noValidate className="mt-4 max-w-md space-y-4">
            <Field id="current-password" label="Current password" error={errors.current}>
              <TextInput
                id="current-password"
                type="password"
                autoComplete="current-password"
                value={values.current}
                onChange={update('current')}
                error={errors.current}
                {...describedBy('current-password', errors.current)}
              />
            </Field>
            <Field id="new-password" label="New password" error={errors.next}>
              <TextInput
                id="new-password"
                type="password"
                autoComplete="new-password"
                value={values.next}
                onChange={update('next')}
                error={errors.next}
                {...describedBy('new-password', errors.next)}
              />
              <PasswordChecklist password={values.next} />
            </Field>
            <Field id="confirm-password" label="Confirm new password" error={errors.confirm}>
              <TextInput
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                value={values.confirm}
                onChange={update('confirm')}
                error={errors.confirm}
                {...describedBy('confirm-password', errors.confirm)}
              />
            </Field>
            <Button type="submit" loading={saving}>
              Change password
            </Button>
          </form>
        </section>
      </div>
    </>
  );
}
