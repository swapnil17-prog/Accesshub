import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import Button from '../../components/Button';
import EmptyState from '../../components/EmptyState';
import { ErrorAlert, Field, Select, Textarea, TextInput } from '../../components/form';
import { SearchIcon } from '../../components/icons';
import PageHeader from '../../components/PageHeader';
import Spinner from '../../components/Spinner';
import { useToast } from '../../components/toastContext';
import { describedBy, fieldErrorsFrom } from '../../utils/forms';
import { fetchCatalog, selectCatalog } from '../applications/applicationsSlice';
import ApprovalChainPreview from './ApprovalChainPreview';
import { resetSubmit, selectSubmit, submitRequest } from './requestsSlice';
import { JUSTIFICATION_MAX, JUSTIFICATION_MIN, validateRequest } from './requestValidation';

const DURATIONS = [
  { value: '', label: 'Permanent (no end date)' },
  { value: '30', label: '30 days' },
  { value: '90', label: '90 days' },
  { value: '180', label: '6 months' },
  { value: '365', label: '1 year' },
  { value: 'custom', label: 'Custom…' },
];

export default function NewRequestPage() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const toast = useToast();
  const [searchParams] = useSearchParams();
  const catalog = useSelector(selectCatalog);
  const submit = useSelector(selectSubmit);

  const [query, setQuery] = useState('');
  const [form, setForm] = useState({
    applicationId: searchParams.get('app') ?? '',
    accessLevelId: '',
    justification: '',
    duration: '',
    customDays: '',
  });
  const [errors, setErrors] = useState({});

  useEffect(() => {
    dispatch(fetchCatalog());
    return () => dispatch(resetSubmit());
  }, [dispatch]);

  // API validation errors (422) are shown inline next to the matching field.
  useEffect(() => {
    if (submit.error?.code === 'VALIDATION_ERROR') {
      const api = fieldErrorsFrom(submit.error);
      setErrors({
        applicationId: api.application_id,
        accessLevelId: api.access_level_id,
        justification: api.justification,
        duration: api.duration_days,
      });
    }
  }, [submit.error]);

  const application = catalog.items.find((app) => String(app.id) === String(form.applicationId));
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return catalog.items;
    return catalog.items.filter(
      (app) => app.name.toLowerCase().includes(q) || (app.description ?? '').toLowerCase().includes(q),
    );
  }, [catalog.items, query]);

  function update(field, value) {
    setForm((current) => {
      const next = { ...current, [field]: value };
      if (field === 'applicationId') next.accessLevelId = '';
      return next;
    });
    setErrors((current) => ({ ...current, [field]: undefined }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const { errors: found, body } = validateRequest(form, application);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    const result = await dispatch(submitRequest(body));
    if (submitRequest.fulfilled.match(result)) {
      toast.success(`Request #${result.payload.id} sent to ${result.payload.approvals[0]?.approver.name}.`, 'Request submitted');
      navigate(`/requests/${result.payload.id}`);
    }
  }

  const trimmedLength = form.justification.trim().length;
  const otherError = submit.error && submit.error.code !== 'VALIDATION_ERROR' ? submit.error : null;

  return (
    <>
      <PageHeader title="New access request" description="Pick an application and tell approvers why you need it." />

      {otherError ? (
        <div className="mb-6">
          <ErrorAlert title={otherError.code === 'DUPLICATE_REQUEST' ? 'Already requested' : "Couldn't submit"}>
            {otherError.message}
            {otherError.code === 'DUPLICATE_REQUEST' ? (
              <>
                {' '}
                <Link to="/requests?status=PENDING" className="font-semibold underline">
                  View your pending requests
                </Link>
              </>
            ) : null}
          </ErrorAlert>
        </div>
      ) : null}

      <form onSubmit={handleSubmit} noValidate className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <section className="rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200">
            <h2 className="text-sm font-semibold text-slate-900">1. Application</h2>
            <div className="relative mt-3">
              <SearchIcon className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <TextInput
                type="search"
                placeholder="Search applications"
                aria-label="Search applications"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            {catalog.status === 'loading' && catalog.items.length === 0 ? (
              <div className="py-8 text-center">
                <Spinner label="Loading applications" />
              </div>
            ) : filtered.length === 0 ? (
              <EmptyState title="No applications match" description="Try a different search." />
            ) : (
              <div
                role="radiogroup"
                aria-label="Application"
                aria-describedby={errors.applicationId ? 'applicationId-error' : undefined}
                className="mt-3 grid max-h-80 gap-2 overflow-y-auto pr-1 sm:grid-cols-2"
              >
                {filtered.map((app) => {
                  const selected = String(app.id) === String(form.applicationId);
                  return (
                    <button
                      key={app.id}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      onClick={() => update('applicationId', String(app.id))}
                      className={`rounded-md p-3 text-left ring-1 transition ${
                        selected ? 'bg-indigo-50 ring-2 ring-indigo-600' : 'bg-white ring-slate-200 hover:ring-slate-300'
                      }`}
                    >
                      <span className="block text-sm font-semibold text-slate-900">{app.name}</span>
                      <span className="mt-0.5 block text-xs text-slate-500">{app.description || 'No description'}</span>
                      <span className="mt-1 block text-xs text-slate-400">
                        Owner: {app.owner?.name} · {app.workflow_steps.length} approval step
                        {app.workflow_steps.length === 1 ? '' : 's'}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
            {errors.applicationId ? (
              <p id="applicationId-error" className="mt-2 text-xs text-rose-600">
                {errors.applicationId}
              </p>
            ) : null}
          </section>

          <section className="space-y-5 rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200">
            <h2 className="text-sm font-semibold text-slate-900">2. Details</h2>
            <Field id="accessLevelId" label="Access level" error={errors.accessLevelId}>
              <Select
                id="accessLevelId"
                value={form.accessLevelId}
                onChange={(e) => update('accessLevelId', e.target.value)}
                disabled={!application}
                error={errors.accessLevelId}
                {...describedBy('accessLevelId', errors.accessLevelId)}
              >
                <option value="">{application ? 'Select an access level' : 'Choose an application first'}</option>
                {application?.access_levels.map((level) => (
                  <option key={level.id} value={level.id}>
                    {level.name}
                  </option>
                ))}
              </Select>
            </Field>

            <Field
              id="justification"
              label="Business justification"
              error={errors.justification}
              hint={`At least ${JUSTIFICATION_MIN} characters. Approvers see this.`}
            >
              <Textarea
                id="justification"
                rows={4}
                maxLength={JUSTIFICATION_MAX}
                value={form.justification}
                onChange={(e) => update('justification', e.target.value)}
                error={errors.justification}
                placeholder="What will you use this access for, and why now?"
                {...describedBy('justification', errors.justification, true)}
              />
              <p
                className={`mt-1 text-right text-xs ${trimmedLength < JUSTIFICATION_MIN ? 'text-slate-400' : 'text-emerald-600'}`}
              >
                {trimmedLength}/{JUSTIFICATION_MIN} minimum
              </p>
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="duration" label="Duration" optional error={errors.duration}>
                <Select
                  id="duration"
                  value={form.duration}
                  onChange={(e) => update('duration', e.target.value)}
                  error={errors.duration}
                  {...describedBy('duration', errors.duration)}
                >
                  {DURATIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </Field>
              {form.duration === 'custom' ? (
                <Field id="customDays" label="Number of days" error={errors.customDays} hint="1 to 365">
                  <TextInput
                    id="customDays"
                    type="number"
                    min={1}
                    max={365}
                    value={form.customDays}
                    onChange={(e) => update('customDays', e.target.value)}
                    error={errors.customDays}
                    {...describedBy('customDays', errors.customDays, true)}
                  />
                </Field>
              ) : null}
            </div>
          </section>
        </div>

        <aside className="lg:col-span-1">
          <div className="space-y-4 rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200 lg:sticky lg:top-24">
            <h2 className="text-sm font-semibold text-slate-900">Approval chain</h2>
            <ApprovalChainPreview application={application} />
            <Button type="submit" size="lg" className="w-full" loading={submit.status === 'loading'}>
              Submit request
            </Button>
          </div>
        </aside>
      </form>
    </>
  );
}
