import { useEffect, useState } from 'react';
import { useDispatch } from 'react-redux';

import ConfirmModal from '../../components/ConfirmModal';
import { ErrorAlert, Field, TextInput } from '../../components/form';
import { useToast } from '../../components/toastContext';
import UserPicker from '../../components/UserPicker';
import { ALL_ROLES, ROLE_LABELS } from '../../navigation';
import { describedBy, fieldErrorsFrom } from '../../utils/forms';
import { saveUser } from './usersSlice';

function initialValues(user) {
  return {
    department: user?.department ?? '',
    manager: user?.manager ?? null,
    isActive: user?.is_active ?? true,
    roles: new Set(user?.roles ?? []),
  };
}

/** Edit department, manager, active flag and roles of one user. */
export default function EditUserModal({ user, onClose }) {
  const dispatch = useDispatch();
  const toast = useToast();
  const [values, setValues] = useState(() => initialValues(user));
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setValues(initialValues(user));
    setErrors({});
    setFormError(null);
  }, [user]);

  if (!user) return null;

  function toggleRole(role) {
    setValues((current) => {
      const roles = new Set(current.roles);
      if (roles.has(role)) roles.delete(role);
      else roles.add(role);
      return { ...current, roles };
    });
  }

  async function save() {
    const changes = {};
    const department = values.department.trim() || null;
    if (department !== (user.department || null)) changes.department = department;
    const managerId = values.manager?.id ?? null;
    if (managerId !== (user.manager_id ?? null)) changes.manager_id = managerId;
    if (values.isActive !== user.is_active) changes.is_active = values.isActive;
    const roles = ALL_ROLES.filter((r) => values.roles.has(r));
    const rolesChanged = roles.join() !== ALL_ROLES.filter((r) => user.roles.includes(r)).join();

    if (!Object.keys(changes).length && !rolesChanged) {
      onClose();
      return;
    }
    setSaving(true);
    setErrors({});
    setFormError(null);
    const result = await dispatch(saveUser({ id: user.id, changes, roles: rolesChanged ? roles : undefined }));
    setSaving(false);
    if (saveUser.fulfilled.match(result)) {
      toast.success(`${user.name} updated.`);
      onClose(true);
      return;
    }
    const error = result.payload;
    if (error?.code === 'VALIDATION_ERROR' && Object.keys(error.details ?? {}).length) setErrors(fieldErrorsFrom(error));
    else setFormError(error?.message ?? 'Could not save.');
  }

  return (
    <ConfirmModal
      open
      title={`Edit ${user.name}`}
      message={user.email}
      confirmLabel="Save changes"
      loading={saving}
      onConfirm={save}
      onCancel={() => onClose()}
    >
      <div className="space-y-4">
        {formError ? <ErrorAlert>{formError}</ErrorAlert> : null}
        <Field id="edit-department" label="Department" optional error={errors.department}>
          <TextInput
            id="edit-department"
            value={values.department}
            maxLength={120}
            onChange={(e) => setValues({ ...values, department: e.target.value })}
            {...describedBy('edit-department', errors.department)}
          />
        </Field>
        <Field id="edit-manager" label="Manager" optional error={errors.manager_id}>
          <UserPicker
            id="edit-manager"
            value={values.manager}
            onChange={(manager) => setValues({ ...values, manager })}
            error={errors.manager_id}
          />
        </Field>
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
        <label className="flex items-start gap-2 rounded-md bg-slate-50 p-3 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={values.isActive}
            onChange={(e) => setValues({ ...values, isActive: e.target.checked })}
            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
          />
          <span>
            <span className="font-medium">Active</span>
            <span className="block text-xs text-slate-500">Inactive users can&apos;t sign in. Their history is kept.</span>
          </span>
        </label>
      </div>
    </ConfirmModal>
  );
}
