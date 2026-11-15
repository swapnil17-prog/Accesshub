import { APPROVER_TYPE_LABELS } from '../../utils/format';

/** Who will be asked, in order, for an application's workflow steps. */
export default function ApprovalChainPreview({ application }) {
  if (!application) {
    return <p className="text-sm text-slate-500">Choose an application to see who will approve your request.</p>;
  }
  const steps = application.workflow_steps ?? [];
  if (steps.length === 0) {
    return (
      <p className="text-sm text-amber-700">
        This application has no approval workflow yet, so requests can&apos;t be submitted. Contact its owner.
      </p>
    );
  }
  return (
    <ol className="space-y-4" aria-label="Approval chain">
      {steps.map((step, index) => (
        <li key={step.step_order} className="relative flex gap-3">
          {index < steps.length - 1 ? (
            <span className="absolute left-3 top-7 h-[calc(100%-4px)] w-px bg-slate-200" aria-hidden="true" />
          ) : null}
          <span className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-700 ring-1 ring-indigo-200">
            {step.step_order}
          </span>
          <div className="min-w-0 text-sm">
            <p className="font-medium text-slate-900">{approverName(step, application)}</p>
            <p className="text-slate-500">
              {APPROVER_TYPE_LABELS[step.approver_type]} · responds within {step.sla_hours}h
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function approverName(step, application) {
  if (step.approver_type === 'APP_OWNER') return application.owner?.name ?? 'Application owner';
  if (step.approver_type === 'SPECIFIC_USER') return step.approver_user?.name ?? 'Named approver';
  return 'Your manager';
}
