import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useParams } from 'react-router-dom';

import Button, { ButtonLink } from '../../components/Button';
import ConfirmModal from '../../components/ConfirmModal';
import EmptyState from '../../components/EmptyState';
import { ErrorAlert } from '../../components/form';
import { SearchIcon } from '../../components/icons';
import { FullPageSpinner } from '../../components/Spinner';
import StatusBadge from '../../components/StatusBadge';
import { useToast } from '../../components/toastContext';
import { useAuth } from '../../hooks/useAuth';
import { durationLabel, formatDate, formatDateTime } from '../../utils/format';
import { approveApproval, fetchInboxCount, rejectApproval } from '../approvals/approvalsSlice';
import DecisionModal from '../approvals/DecisionModal';
import ApprovalTimeline from './ApprovalTimeline';
import { cancelRequest, fetchRequest, requestUpdated, selectCancelling, selectRequestDetail } from './requestsSlice';

function Detail({ label, children }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm text-slate-900">{children}</dd>
    </div>
  );
}

export default function RequestDetailPage() {
  const { requestId } = useParams();
  const dispatch = useDispatch();
  const toast = useToast();
  const { user } = useAuth();
  const { item: request, status, error } = useSelector(selectRequestDetail);
  const cancelling = useSelector(selectCancelling);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [decision, setDecision] = useState(null); // 'approve' | 'reject' | null
  const [deciding, setDeciding] = useState(false);

  useEffect(() => {
    dispatch(fetchRequest(requestId));
  }, [dispatch, requestId]);

  if (status === 'failed' && !request) {
    return error?.code === 'NOT_FOUND' ? (
      <EmptyState
        icon={SearchIcon}
        title="Request not found"
        description="It doesn't exist, or you don't have access to it."
        action={
          <ButtonLink to="/requests" variant="secondary">
            Back to my requests
          </ButtonLink>
        }
      />
    ) : (
      <ErrorAlert title="Couldn't load this request">{error?.message}</ErrorAlert>
    );
  }
  if (!request || String(request.id) !== String(requestId)) return <FullPageSpinner label="Loading request" />;

  const isRequester = request.requester.id === user?.id;
  const wasApprover = request.approvals.some((a) => a.approver.id === user?.id || a.escalated_from?.id === user?.id);
  // Back to where this person most likely came from (auditors/admins browsing land on the dashboard).
  const back = isRequester
    ? { to: '/requests', label: 'My requests' }
    : wasApprover
      ? { to: '/approvals', label: 'Approval inbox' }
      : { to: '/', label: 'Dashboard' };
  const myPending = request.approvals.find((a) => a.decision === 'PENDING' && a.approver.id === user?.id);

  async function doCancel() {
    const result = await dispatch(cancelRequest(request.id));
    setConfirmCancel(false);
    if (cancelRequest.fulfilled.match(result)) toast.success('Your request was cancelled.');
    else toast.error(result.payload?.message ?? 'Could not cancel the request.');
  }

  async function doDecide(comment) {
    setDeciding(true);
    const thunk = decision === 'reject' ? rejectApproval : approveApproval;
    const result = await dispatch(thunk({ id: myPending.id, comment }));
    setDeciding(false);
    setDecision(null);
    if (thunk.fulfilled.match(result)) {
      dispatch(requestUpdated(result.payload));
      dispatch(fetchInboxCount());
      toast.success(decision === 'reject' ? 'Request rejected.' : 'Approved.');
    } else {
      toast.error(result.payload?.message ?? 'That did not work.');
      dispatch(fetchRequest(request.id));
    }
  }

  return (
    <>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link to={back.to} className="text-sm text-indigo-600 hover:text-indigo-500">
            ← {back.label}
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-slate-900 sm:text-2xl">
              {request.application.name} · {request.access_level.name}
            </h1>
            <StatusBadge status={request.status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Request #{request.id} · submitted {formatDateTime(request.created_at)}
          </p>
        </div>
        <div className="flex gap-2">
          {myPending ? (
            <>
              <Button variant="secondary" onClick={() => setDecision('reject')}>
                Reject
              </Button>
              <Button onClick={() => setDecision('approve')}>Approve</Button>
            </>
          ) : null}
          {isRequester && request.status === 'PENDING' ? (
            <Button variant="secondary" onClick={() => setConfirmCancel(true)}>
              Cancel request
            </Button>
          ) : null}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200 lg:col-span-1">
          <h2 className="text-sm font-semibold text-slate-900">Details</h2>
          <dl className="mt-4 space-y-4">
            <Detail label="Requester">
              {request.requester.name}
              <span className="block text-xs text-slate-500">{request.requester.email}</span>
            </Detail>
            <Detail label="Duration">{durationLabel(request.duration_days)}</Detail>
            {request.expires_at ? <Detail label="Expires">{formatDate(request.expires_at)}</Detail> : null}
            <Detail label="Progress">
              {request.status === 'PENDING'
                ? `Step ${request.current_step} of ${request.total_steps}`
                : `${request.total_steps} step${request.total_steps === 1 ? '' : 's'}`}
            </Detail>
            <Detail label="Justification">
              <p className="whitespace-pre-line">{request.justification}</p>
            </Detail>
          </dl>
        </section>

        <section className="rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200 lg:col-span-2">
          <h2 className="mb-5 text-sm font-semibold text-slate-900">Approval timeline</h2>
          <ApprovalTimeline request={request} />
        </section>
      </div>

      <ConfirmModal
        open={confirmCancel}
        title="Cancel this request?"
        message="Approvers will no longer be asked to decide. You can submit a new request later."
        confirmLabel="Cancel request"
        cancelLabel="Keep it"
        tone="danger"
        loading={cancelling}
        onConfirm={doCancel}
        onCancel={() => setConfirmCancel(false)}
      />
      <DecisionModal
        open={decision !== null}
        mode={decision}
        subject={`${request.requester.name} · ${request.application.name} (${request.access_level.name})`}
        loading={deciding}
        onConfirm={doDecide}
        onCancel={() => setDecision(null)}
      />
    </>
  );
}
