import { useSelector } from 'react-redux';
import { Link } from 'react-router-dom';

import { InboxIcon, PlusIcon, ShieldIcon } from '../../components/icons';
import PageHeader from '../../components/PageHeader';
import { useAuth } from '../../hooks/useAuth';
import { selectInboxCount } from '../approvals/approvalsSlice';

// Phase 7 replaces this with role-aware cards and charts from /api/reports/summary.
export default function DashboardPage() {
  const { user, hasRole } = useAuth();
  const inboxCount = useSelector(selectInboxCount);
  const firstName = user?.name?.split(' ')[0] ?? 'there';

  const cards = [
    hasRole('employee') && {
      to: '/requests/new',
      icon: PlusIcon,
      title: 'Request access',
      text: 'Ask for access to an application.',
    },
    {
      to: '/approvals',
      icon: InboxIcon,
      title: 'Approval inbox',
      text: inboxCount ? `${inboxCount} approval(s) waiting for you.` : 'Nothing waiting for you.',
    },
    hasRole('auditor', 'admin') && {
      to: '/audit',
      icon: ShieldIcon,
      title: 'Audit log',
      text: 'Review every change and decision.',
    },
  ].filter(Boolean);

  return (
    <>
      <PageHeader title={`Welcome back, ${firstName}`} description="Here's where things stand." />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => (
          <Link
            key={card.to}
            to={card.to}
            className="group rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200 transition hover:shadow-md hover:ring-indigo-200"
          >
            <span className="inline-flex rounded-md bg-indigo-50 p-2 text-indigo-600">
              <card.icon className="h-5 w-5" />
            </span>
            <h2 className="mt-4 text-sm font-semibold text-slate-900 group-hover:text-indigo-700">{card.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{card.text}</p>
          </Link>
        ))}
      </div>
    </>
  );
}
