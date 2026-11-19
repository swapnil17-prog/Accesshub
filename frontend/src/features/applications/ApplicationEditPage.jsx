import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useNavigate, useParams } from 'react-router-dom';

import Button from '../../components/Button';
import ConfirmModal from '../../components/ConfirmModal';
import { ErrorAlert, Field, Textarea, TextInput } from '../../components/form';
import { FullPageSpinner } from '../../components/Spinner';
import StatusBadge from '../../components/StatusBadge';
import { useToast } from '../../components/toastContext';
import UserPicker from '../../components/UserPicker';
import { useAuth } from '../../hooks/useAuth';
import ForbiddenPage from '../../pages/ForbiddenPage';
import { describedBy, fieldErrorsFrom } from '../../utils/forms';
import AccessLevelsEditor from './AccessLevelsEditor';
import {
  createApplication,
  deactivateApplication,
  fetchApplication,
  saveWorkflow,
  selectCurrentApplication,
  updateApplication,
} from './applicationsSlice';
import WorkflowBuilder from './WorkflowBuilder';

function Section({ title, description, children, actions }) {
  return (
    <section className="rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {description ? <p className="mt-0.5 text-sm text-slate-500">{description}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

function DetailsForm({ application, isAdmin, onSubmit, submitting }) {
  const [values, setValues] = useState(() => ({
    name: application?.name ?? '',
    description: application?.description ?? '',
    owner: application?.owner ?? null,
    levels: '',
  }));
  const [errors, setErrors] = useState({});
  const isNew = !application;

  async function handleSubmit(event) {
    event.preventDefault();
    const found = {};
    if (!values.name.trim()) found.name = 'Name is required.';
    if (isAdmin && !values.owner) found.owner_id = 'Choose an owner.';
    setErrors(found);
    if (Object.keys(found).length) return;
    const apiError = await onSubmit(values);
    if (apiError) setErrors(fieldErrorsFrom(apiError));
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="app-name" label="Name" error={errors.name}>
          <TextInput
            id="app-name"
            value={values.name}
            maxLength={120}
            onChange={(e) => setValues({ ...values, name: e.target.value })}
            error={errors.name}
            {...describedBy('app-name', errors.name)}
          />
        </Field>
        <Field
          id="app-owner"
          label="Owner"
          error={errors.owner_id}
          hint={isAdmin ? 'Needs the app owner or admin role.' : 'Only an admin can change the owner.'}
        >
          <UserPicker
            id="app-owner"
            value={values.owner}
            disabled={!isAdmin}
            onChange={(owner) => setValues({ ...values, owner })}
            error={errors.owner_id}
          />
        </Field>
      </div>
      <Field id="app-description" label="Description" optional error={errors.description}>
        <Textarea
          id="app-description"
          rows={2}
          maxLength={2000}
          value={values.description}
          onChange={(e) => setValues({ ...values, description: e.target.value })}
        />
      </Field>
      {isNew ? (
        <Field id="app-levels" label="Access levels" optional hint="One per line. You can add more later.">
          <Textarea
            id="app-levels"
            rows={3}
            value={values.levels}
            placeholder={'Viewer\nEditor\nAdmin'}
            onChange={(e) => setValues({ ...values, levels: e.target.value })}
            {...describedBy('app-levels', null, true)}
          />
        </Field>
      ) : null}
      <div className="flex justify-end">
        <Button type="submit" loading={submitting}>
          {isNew ? 'Create application' : 'Save details'}
        </Button>
      </div>
    </form>
  );
}

export default function ApplicationEditPage() {
  const { appId } = useParams();
  const isNew = appId === 'new';
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const toast = useToast();
  const { user, hasRole } = useAuth();
  const isAdmin = hasRole('admin');
  const { item: application, status, error } = useSelector(selectCurrentApplication);
  const [submitting, setSubmitting] = useState(false);
  const [savingWorkflow, setSavingWorkflow] = useState(false);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);

  useEffect(() => {
    if (!isNew) dispatch(fetchApplication(appId));
  }, [dispatch, appId, isNew]);

  if (isNew && !isAdmin) return <ForbiddenPage />;
  if (!isNew) {
    if (status === 'failed' && !application) return <ErrorAlert title="Couldn't load this application">{error?.message}</ErrorAlert>;
    if (!application || String(application.id) !== String(appId)) return <FullPageSpinner label="Loading application" />;
    if (!isAdmin && application.owner?.id !== user?.id) return <ForbiddenPage />;
  }

  async function submitDetails(values) {
    setSubmitting(true);
    const result = isNew
      ? await dispatch(
          createApplication({
            name: values.name.trim(),
            description: values.description.trim() || null,
            owner_id: values.owner?.id,
            access_levels: values.levels
              .split('\n')
              .map((l) => l.trim())
              .filter(Boolean),
          }),
        )
      : await dispatch(updateApplication({ id: application.id, changes: changedFields(application, values, isAdmin) }));
    setSubmitting(false);
    const thunk = isNew ? createApplication : updateApplication;
    if (thunk.fulfilled.match(result)) {
      toast.success(isNew ? 'Application created. Now set up its approval workflow.' : 'Details saved.');
      if (isNew) navigate(`/admin/applications/${result.payload.id}`, { replace: true });
      return null;
    }
    if (result.payload?.code !== 'VALIDATION_ERROR') toast.error(result.payload?.message ?? 'Could not save.');
    return result.payload;
  }

  async function submitWorkflow(steps) {
    setSavingWorkflow(true);
    const result = await dispatch(saveWorkflow({ appId: application.id, steps }));
    setSavingWorkflow(false);
    if (saveWorkflow.fulfilled.match(result)) {
      toast.success('Workflow saved. It applies to new requests; in-flight requests keep their chain.');
      return { ok: true };
    }
    return { ok: false, error: result.payload };
  }

  async function doDeactivate() {
    setConfirmDeactivate(false);
    const result = await dispatch(deactivateApplication(application.id));
    if (deactivateApplication.fulfilled.match(result)) toast.success(`${application.name} is now inactive.`);
    else toast.error(result.payload?.message ?? 'Could not deactivate.');
  }

  async function reactivate() {
    const result = await dispatch(updateApplication({ id: application.id, changes: { is_active: true } }));
    if (updateApplication.fulfilled.match(result)) toast.success(`${application.name} is active again.`);
  }

  return (
    <>
      <div className="mb-6">
        <Link to="/admin/applications" className="text-sm text-indigo-600 hover:text-indigo-500">
          ← Applications
        </Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-slate-900 sm:text-2xl">
              {isNew ? 'New application' : application.name}
            </h1>
            {isNew ? null : <StatusBadge status={application.is_active ? 'ACTIVE' : 'INACTIVE'} />}
          </div>
          {!isNew && isAdmin ? (
            application.is_active ? (
              <Button variant="secondary" onClick={() => setConfirmDeactivate(true)}>
                Deactivate
              </Button>
            ) : (
              <Button variant="secondary" onClick={reactivate}>
                Reactivate
              </Button>
            )
          ) : null}
        </div>
      </div>

      <div className="space-y-6">
        <Section title="Details">
          <DetailsForm
            key={application?.id ?? 'new'}
            application={isNew ? null : application}
            isAdmin={isAdmin}
            onSubmit={submitDetails}
            submitting={submitting}
          />
        </Section>

        {isNew ? null : (
          <>
            <Section title="Access levels" description="What people can ask for in this application.">
              <AccessLevelsEditor application={application} />
            </Section>
            <Section
              title="Approval workflow"
              description="Steps run in order. Drag or use the arrows to reorder. Changes apply to new requests only."
            >
              <WorkflowBuilder steps={application.workflow_steps} onSave={submitWorkflow} saving={savingWorkflow} />
            </Section>
          </>
        )}
      </div>

      <ConfirmModal
        open={confirmDeactivate}
        title={`Deactivate ${application?.name}?`}
        message="People won't be able to request it any more. Requests already in progress continue, and you can reactivate it later."
        confirmLabel="Deactivate"
        tone="danger"
        onConfirm={doDeactivate}
        onCancel={() => setConfirmDeactivate(false)}
      />
    </>
  );
}

function changedFields(application, values, isAdmin) {
  const changes = {};
  if (values.name.trim() !== application.name) changes.name = values.name.trim();
  const description = values.description.trim() || null;
  if (description !== (application.description || null)) changes.description = description;
  if (isAdmin && values.owner && values.owner.id !== application.owner?.id) changes.owner_id = values.owner.id;
  return changes;
}
