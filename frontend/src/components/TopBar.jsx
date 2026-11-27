import { Link } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { ROLE_LABELS } from '../navigation';
import { BellIcon, LogoutIcon, MenuIcon } from './icons';

function initials(name = '') {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');
}

export default function TopBar({ inboxCount, onOpenMenu }) {
  const { user, roles, logout } = useAuth();
  const visibleRoles = roles.filter((r) => r !== 'employee' || roles.length === 1);

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-6">
      <button
        type="button"
        onClick={onOpenMenu}
        className="-ml-1 rounded-md p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
        aria-label="Open navigation"
      >
        <MenuIcon />
      </button>

      <div className="flex-1" />

      <Link
        to="/approvals"
        className="relative rounded-full p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
        aria-label={inboxCount ? `Approval inbox, ${inboxCount} pending` : 'Approval inbox'}
      >
        <BellIcon />
        {inboxCount ? (
          <span
            data-testid="inbox-badge"
            className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-500 px-1 text-[11px] font-semibold text-white ring-2 ring-white"
          >
            {inboxCount > 99 ? '99+' : inboxCount}
          </span>
        ) : null}
      </Link>

      <div className="flex items-center gap-3 border-l border-slate-200 pl-3">
        <Link
          to="/account"
          className="flex min-w-0 items-center gap-3 rounded-md p-1 hover:bg-slate-100"
          aria-label="Your account"
          title="Your account"
        >
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700"
            aria-hidden="true"
          >
            {initials(user?.name)}
          </span>
          <span className="hidden min-w-0 sm:block">
            <span className="block truncate text-sm font-medium text-slate-900">{user?.name}</span>
            <span className="block truncate text-xs text-slate-500">
              {visibleRoles.map((r) => ROLE_LABELS[r] ?? r).join(' · ')}
            </span>
          </span>
        </Link>
        <button
          type="button"
          onClick={logout}
          className="rounded-md p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          aria-label="Sign out"
          title="Sign out"
        >
          <LogoutIcon />
        </button>
      </div>
    </header>
  );
}
