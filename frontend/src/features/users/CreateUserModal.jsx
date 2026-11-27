import { useState } from 'react';
import { useDispatch } from 'react-redux';

import Button from '../../components/Button';
import ConfirmModal from '../../components/ConfirmModal';
import { ErrorAlert, Field, TextInput } from '../../components/form';
import PasswordChecklist from '../../components/PasswordChecklist';
import { useToast } from '../../components/toastContext';
import UserPicker from '../../components/UserPicker';
import { ALL_ROLES, ROLE_LABELS } from '../../navigation';
import { describedBy } from '../../utils/forms';
import { generatePassword } from '../../utils/passwordPolicy';
import { createUser } from './usersSlice';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const INITIAL = {
  name: '',
  email: '',
  department: '',
  manager: null,
  roles: new Set(['employee']),
  password: '',
};

const firstMessage = (value) => (Array.isArray(value) ? value.join(' ') : value);

/** Admin: create a user with a temporary password to share with them. */
export default function CreateUserModal({ onClose }) {
  const dispatch = useDispatch();
  const toast = useToast();
  const [values, setValues] = useState(INITIAL);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [saving, setSaving] = useState(false);

  function set(field, value) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  }

  function toggleRole(role) {
    const roles = new Set(values.roles);
    if (roles.has(role)) roles.delete(role);
    else roles.add(role);
    set('roles', roles);
  }

  async function save() {
    const found = {};
    if (!values.name.trim()) found.name = 'Name is required.';
    if (!EMAIL_RE.test(values.email.trim())) found.email = 'Enter a valid email address.';
    if (!values.password) found.password = 'Set a temporary password (use Generate).';
    if (values.roles.size === 0) found.roles = 'Give the user at least one role.';
    setErrors(found);
    if (Object.keys(found).length) return;

    setSaving(true);
    setFormError(null);
    const result = await dispatch(
      createUser({
        name: values.name.trim(),
        email: values.email.trim(),
        password: values.password,
        department: values.department.trim() || null,
        manager_id: values.manager?.id ?? null,
        roles: ALL_ROLES.filter((role) => values.roles.has(role)),
      }),
    );
    setSaving(false);
    if (createUser.fulfilled.match(result)) {
      toast.success('Share the temporary password with them securely.', `${result.payload.name} created`);
      onClose(true);
      return;
    }
    const error = result.payload;
    if (error?.code === 'EMAIL_TAKEN') setErrors({ email: error.message });
    else if (error?.code === 'VALIDATION_ERROR' && Object.keys(error.details ?? {}).length) {
      const d = error.details;
      setErrors({
        name: firstMessage(d.name),
        email: firstMessage(d.email),
        password: firstMessage(d.password),
        department: firstMessage(d.department),
        manager: firstMessage(d.manager_id),
        roles: firstMessage(d.roles),
      });
    } else setFormError(error?.message ?? 'Could not create the user.');
  }

  return (
    <ConfirmModal
      open
      title="New user"
      message="They can sign in straight away with the temporary password and change it under Your account."
      confirmLabel="Create user"
      loading={saving}
      onConfirm={save}
      onCancel={() => onClose()}
    >
      <div className="space-y-4">
        {formError ? <ErrorAlert>{formError}</ErrorAlert> : null}
        <Field id="new-name" label="Full name" error={errors.name}>
          <TextInput
            id="new-name"
            value={values.name}
            maxLength={120}
            onChange={(e) => set('name', e.target.value)}
            error={errors.name}
            {...describedBy('new-name', errors.name)}
          />
        </Field>
        <Field id="new-email" label="Work email" error={errors.email}>
          <TextInput
            id="new-email"
            type="email"
            value={values.email}
            maxLength={255}
            onChange={(e) => set('email', e.target.value)}
            error={errors.email}
            {...describedBy('new-email', errors.email)}
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="new-department" label="Department" optional error={errors.department}>
            <TextInput
              id="new-department"
              value={values.department}
              maxLength={120}
              onChange={(e) => set('department', e.target.value)}
            />
          </Field>
          <Field id="new-manager" label="Manager" optional error={errors.manager}>
            <UserPicker id="new-manager" value={values.manager} onChange={(m) => set('manager', m)} error={errors.manager} />
          </Field>
        </div>
        <fieldset>
          <legend className="text-sm font-medium text-slate-700">Roles</legend>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {ALL_ROLES.map((role) => (
              <label key={role} className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={values.roles.has(role)}
                  onChange={() => toggleRole(role)}
                  className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
                />
                {ROLE_LABELS[role]}
              </label>
            ))}
          </div>
          {errors.roles ? <p className="mt-1 text-xs text-rose-600">{errors.roles}</p> : null}
        </fieldset>
        <Field id="new-password" label="Temporary password" error={errors.password}>
          <div className="flex gap-2">
            <TextInput
              id="new-password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              value={values.password}
              onChange={(e) => set('password', e.target.value)}
              error={errors.password}
              className="font-mono"
              {...describedBy('new-password', errors.password)}
            />
            <Button
              variant="secondary"
              onClick={() => {
                set('password', generatePassword());
                setShowPassword(true);
              }}
            >
              Generate
            </Button>
          </div>
          <label className="mt-2 flex items-center gap-2 text-xs text-slate-600">
            <input type="checkbox" checked={showPassword} onChange={(e) => setShowPassword(e.target.checked)} />
            Show password
          </label>
          <PasswordChecklist password={values.password} />
        </Field>
      </div>
    </ConfirmModal>
  );
}
