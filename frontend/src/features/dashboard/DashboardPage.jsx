import { lazy, Suspense, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';

import { ButtonLink } from '../../components/Button';
import { ErrorAlert } from '../../components/form';
import { PlusIcon } from '../../components/icons';
import PageHeader from '../../components/PageHeader';
import Spinner from '../../components/Spinner';
import { useAuth } from '../../hooks/useAuth';
import { fetchSummary, selectSummary } from '../audit/auditSlice';
import { StatTile } from './ChartParts';
import { fetchMyStats, selectDashboard } from './dashboardSlice';

// Recharts is only needed by admins/auditors, so it loads in its own chunk.
const SummaryCharts = lazy(() => import('./SummaryCharts'));

const dash = (value) => (value === null || value === undefined ? '—' : value);

export default function DashboardPage() {
  const dispatch = useDispatch();
  const { user, hasRole } = useAuth();
  const isEmployee = hasRole('employee');
  const seesReports = hasRole('admin', 'auditor');
  const { stats, error: statsError } = useSelector(selectDashboard);
  const summary = useSelector(selectSummary);
  const firstName = user?.name?.split(' ')[0] ?? 'there';

  useEffect(() => {
    dispatch(fetchMyStats({ isEmployee }));
  }, [dispatch, isEmployee]);

  useEffect(() => {
    if (seesReports) dispatch(fetchSummary());
  }, [dispatch, seesReports]);

  const data = summary.data;

  return (
    <>
      <PageHeader
        title={`Welcome back, ${firstName}`}
        description="Here's where things stand."
        actions={
          isEmployee ? (
            <ButtonLink to="/requests/new">
              <PlusIcon className="h-4 w-4" />
              Request access
            </ButtonLink>
          ) : null
        }
      />

      {statsError ? (
        <div className="mb-4">
          <ErrorAlert title="Couldn't load your numbers">{statsError.message}</ErrorAlert>
        </div>
      ) : null}

      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">You</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {isEmployee ? (
          <StatTile
            label="My pending requests"
            value={dash(stats?.myPending)}
            hint="Waiting for approval"
            to="/requests?status=PENDING"
            LinkComponent={Link}
          />
        ) : null}
        <StatTile
          label="Waiting for my approval"
          value={dash(stats?.inboxTotal)}
          hint="In your approval inbox"
          to="/approvals"
          LinkComponent={Link}
        />
        <StatTile
          label="Overdue in my inbox"
          value={dash(stats?.inboxOverdue)}
          hint={stats?.inboxOverdue ? 'Past their response deadline' : 'Nothing overdue'}
          tone={stats?.inboxOverdue ? 'alert' : 'default'}
          to="/approvals"
          LinkComponent={Link}
        />
      </div>

      {seesReports ? (
        <>
          <h2 className="mb-3 mt-8 text-xs font-semibold uppercase tracking-wide text-slate-500">Organisation</h2>
          {summary.error ? (
            <ErrorAlert title="Couldn't load the report">{summary.error.message}</ErrorAlert>
          ) : !data ? (
            <div className="py-10 text-center">
              <Spinner label="Loading report" />
            </div>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatTile label="Total requests" value={data.total_requests} hint={`${data.by_status.PENDING} pending`} />
                <StatTile
                  label="Average approval time"
                  value={data.avg_approval_hours === null ? '—' : `${data.avg_approval_hours} h`}
                  hint="Submission to final approval"
                />
                <StatTile
                  label="Overdue approvals"
                  value={data.overdue_approvals}
                  hint="Pending past their SLA, everyone"
                  tone={data.overdue_approvals ? 'alert' : 'default'}
                />
                <StatTile label="Escalations" value={data.escalations_last_30_days} hint="In the last 30 days" />
              </div>
              <Suspense
                fallback={
                  <div className="py-10 text-center">
                    <Spinner label="Loading charts" />
                  </div>
                }
              >
                <SummaryCharts summary={data} />
              </Suspense>
            </>
          )}
        </>
      ) : null}
    </>
  );
}
