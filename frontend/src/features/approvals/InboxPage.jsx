import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useSearchParams } from 'react-router-dom';

import Button from '../../components/Button';
import DataTable from '../../components/DataTable';
import EmptyState from '../../components/EmptyState';
import { ErrorAlert } from '../../components/form';
import { CheckCircleIcon } from '../../components/icons';
import PageHeader from '../../components/PageHeader';
import StatusBadge from '../../components/StatusBadge';
import { useToast } from '../../components/toastContext';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import { dueLabel, formatDateTime, isOverdue } from '../../utils/format';
import { approveApproval, fetchInbox, rejectApproval, selectInbox } from './approvalsSlice';
import DecisionModal from './DecisionModal';

function DueInfo({ item }) {
  const overdue = item.is_overdue || isOverdue(item.due_at);
  return (
    <div className="space-y-1 whitespace-nowrap">
      <p className={overdue ? 'font-semibold text-rose-700' : 'text-slate-600'}>{dueLabel(item.due_at)}</p>
      <div className="flex gap-1">
        {overdue ? <StatusBadge status="OVERDUE" /> : null}
        {item.escalated ? <StatusBadge status="ESCALATED" /> : null}
      </div>
    </div>
  );
}

function DecisionButtons({ item, onDecide }) {
  const name = item.request.requester.name;
  return (
    <div className="flex gap-2 md:justify-end">
      <Button size="sm" variant="secondary" onClick={() => onDecide('reject', item.id)} aria-label={`Reject request from ${name}`}>
        Reject
      </Button>
      <Button size="sm" onClick={() => onDecide('approve', item.id)} aria-label={`Approve request from ${name}`}>
        Approve
      </Button>
    </div>
  );
}

export default function InboxPage() {
  const dispatch = useDispatch();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const inbox = useSelector(selectInbox);
  const page = Number(searchParams.get('page') ?? 1);
  const wide = useMediaQuery('(min-width: 768px)');

  const [selected, setSelected] = useState(() => new Set());
  const [modal, setModal] = useState(null); // { mode: 'approve' | 'reject', ids: number[] }

  useEffect(() => {
    dispatch(fetchInbox({ page }));
  }, [dispatch, page]);

  // Forget selections for rows that have left the list.
  const visibleIds = useMemo(() => new Set(inbox.items.map((i) => i.id)), [inbox.items]);
  const selectedVisible = [...selected].filter((id) => visibleIds.has(id));
  const allSelected = inbox.items.length > 0 && selectedVisible.length === inbox.items.length;

  function toggle(id) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function openDecision(mode, id) {
    setModal({ mode, ids: [id] });
  }

  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(inbox.items.map((i) => i.id)));
  }

  async function decide(comment) {
    const { mode, ids } = modal;
    setModal(null); // optimistic: rows disappear immediately, the modal doesn't wait
    setSelected((current) => new Set([...current].filter((id) => !ids.includes(id))));
    const thunk = mode === 'reject' ? rejectApproval : approveApproval;
    const results = await Promise.all(ids.map((id) => dispatch(thunk({ id, comment }))));

    const failed = results.filter((r) => thunk.rejected.match(r));
    const done = results.length - failed.length;
    const verb = mode === 'reject' ? 'Rejected' : 'Approved';
    if (done > 0) toast.success(ids.length === 1 ? `${verb}.` : `${verb} ${done} of ${ids.length} requests.`);
    if (failed.length > 0) {
      const message = failed[0].payload?.message ?? 'Please try again.';
      toast.error(message, failed.length === 1 ? "Couldn't save that decision" : `${failed.length} decisions failed`);
    }
  }

  const modalItems = modal ? inbox.items.filter((i) => modal.ids.includes(i.id)) : [];
  const modalSubject =
    modalItems.length === 1
      ? `${modalItems[0].request.requester.name} · ${modalItems[0].request.application.name} (${modalItems[0].request.access_level.name})`
      : undefined;

  const columns = [
    {
      key: 'select',
      header: (
        <input
          type="checkbox"
          aria-label="Select all"
          checked={allSelected}
          onChange={toggleAll}
          className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
        />
      ),
      className: 'w-10',
      render: (item) => (
        <input
          type="checkbox"
          aria-label={`Select request from ${item.request.requester.name}`}
          checked={selected.has(item.id)}
          onChange={() => toggle(item.id)}
          onClick={(e) => e.stopPropagation()}
          className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
        />
      ),
    },
    {
      key: 'request',
      header: 'Request',
      render: (item) => (
        <div className="max-w-xl md:min-w-[16rem]">
          <p className="font-medium text-slate-900">
            {item.request.requester.name}{' '}
            <span className="font-normal text-slate-500">
              wants <span className="font-medium text-slate-700">{item.request.access_level.name}</span> on{' '}
              <span className="font-medium text-slate-700">{item.request.application.name}</span>
            </span>
          </p>
          <p className="mt-1 line-clamp-2 text-sm text-slate-600" title={item.request.justification}>
            {item.request.justification}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Step {item.step_order} of {item.request.total_steps} · submitted {formatDateTime(item.request.created_at)} ·{' '}
            <Link to={`/requests/${item.request.id}`} className="text-indigo-600 hover:text-indigo-500">
              View timeline
            </Link>
          </p>
          {/* Small screens: due time and actions live in this cell instead of their own columns. */}
          {wide ? null : (
            <div className="mt-3 space-y-3">
              <DueInfo item={item} />
              <DecisionButtons item={item} onDecide={openDecision} />
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'due_at',
      header: 'Due',
      sortable: true,
      render: (item) => <DueInfo item={item} />,
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      render: (item) => <DecisionButtons item={item} onDecide={openDecision} />,
    },
  ].filter((column) => wide || !['due_at', 'actions'].includes(column.key));

  return (
    <>
      <PageHeader
        title="Approval inbox"
        description="Requests waiting for your decision, the one due soonest first."
        actions={
          <Button
            onClick={() => setModal({ mode: 'approve', ids: selectedVisible })}
            disabled={selectedVisible.length === 0}
          >
            Approve selected{selectedVisible.length ? ` (${selectedVisible.length})` : ''}
          </Button>
        }
      />

      {inbox.error ? (
        <div className="mb-4">
          <ErrorAlert title="Couldn't load your inbox">{inbox.error.message}</ErrorAlert>
        </div>
      ) : null}

      <DataTable
        caption="Pending approvals"
        columns={columns}
        rows={inbox.items}
        loading={inbox.status === 'loading' && inbox.items.length === 0}
        rowClassName={(item) => (item.is_overdue || isOverdue(item.due_at) ? 'bg-rose-50/60' : '')}
        pagination={
          inbox.total > inbox.perPage
            ? {
                page: inbox.page,
                perPage: inbox.perPage,
                total: inbox.total,
                onPageChange: (p) => setSearchParams({ page: String(p) }),
              }
            : undefined
        }
        empty={
          <EmptyState icon={CheckCircleIcon} title="You're all caught up" description="Nothing is waiting for your approval." />
        }
      />

      <DecisionModal
        open={modal !== null}
        mode={modal?.mode}
        count={modal?.ids.length ?? 1}
        subject={modalSubject}
        onConfirm={decide}
        onCancel={() => setModal(null)}
      />
    </>
  );
}
