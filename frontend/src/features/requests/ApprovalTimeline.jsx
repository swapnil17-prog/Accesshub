import { AlertIcon, CheckCircleIcon, InfoIcon, XIcon } from '../../components/icons';
import StatusBadge from '../../components/StatusBadge';
import { APPROVER_TYPE_LABELS, dueLabel, formatDateTime, isOverdue } from '../../utils/format';
import { buildTimeline } from './timeline';

const MARKERS = {
  APPROVED: { icon: CheckCircleIcon, ring: 'bg-emerald-50 text-emerald-600 ring-emerald-200' },
  REJECTED: { icon: XIcon, ring: 'bg-rose-50 text-rose-600 ring-rose-200' },
  SKIPPED: { icon: InfoIcon, ring: 'bg-slate-50 text-slate-400 ring-slate-200' },
  PENDING: { icon: InfoIcon, ring: 'bg-amber-50 text-amber-600 ring-amber-200' },
  OVERDUE: { icon: AlertIcon, ring: 'bg-rose-50 text-rose-600 ring-rose-200' },
  NONE: { icon: null, ring: 'bg-white text-slate-300 ring-slate-200' },
};

export default function ApprovalTimeline({ request }) {
  const rows = buildTimeline(request);
  const closed = request.status !== 'PENDING';

  return (
    <ol className="space-y-6" aria-label="Approval timeline">
      {rows.map(({ step, approval }, index) => {
        const overdue = approval?.decision === 'PENDING' && isOverdue(approval.due_at);
        const markerKey = !approval ? 'NONE' : overdue ? 'OVERDUE' : approval.decision;
        const { icon: MarkerIcon, ring } = MARKERS[markerKey];
        return (
          <li key={step.step_order} className="relative flex gap-4" data-testid={`timeline-step-${step.step_order}`}>
            {index < rows.length - 1 ? (
              <span className="absolute left-4 top-9 h-[calc(100%-12px)] w-px bg-slate-200" aria-hidden="true" />
            ) : null}
            <span
              className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold ring-1 ${ring}`}
            >
              {MarkerIcon ? <MarkerIcon className="h-4 w-4" /> : step.step_order}
            </span>
            <div className="min-w-0 flex-1 pb-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-slate-900">
                  Step {step.step_order}: {approval ? approval.approver.name : APPROVER_TYPE_LABELS[step.approver_type]}
                </p>
                {approval ? <StatusBadge status={approval.decision} /> : null}
                {approval?.escalated ? <StatusBadge status="ESCALATED" /> : null}
                {overdue ? <StatusBadge status="OVERDUE" /> : null}
              </div>
              <p className="mt-0.5 text-xs text-slate-500">
                {APPROVER_TYPE_LABELS[step.approver_type]} · SLA {step.sla_hours}h
                {approval?.escalated && approval.escalated_from ? ` · escalated from ${approval.escalated_from.name}` : ''}
              </p>
              {!approval ? (
                <p className="mt-1 text-sm text-slate-400">
                  {closed ? 'Not needed — the request was closed earlier.' : 'Waiting for earlier steps.'}
                </p>
              ) : approval.decision === 'PENDING' ? (
                <p className={`mt-1 text-sm ${overdue ? 'text-rose-700' : 'text-slate-600'}`}>
                  Waiting for a decision · {dueLabel(approval.due_at)}
                </p>
              ) : approval.decision === 'SKIPPED' ? (
                <p className="mt-1 text-sm text-slate-400">Skipped — the request was cancelled.</p>
              ) : (
                <p className="mt-1 text-sm text-slate-600">
                  {approval.decision === 'APPROVED' ? 'Approved' : 'Rejected'} {formatDateTime(approval.decided_at)}
                </p>
              )}
              {approval?.comment ? (
                <blockquote className="mt-2 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700 ring-1 ring-inset ring-slate-200">
                  “{approval.comment}”
                </blockquote>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
