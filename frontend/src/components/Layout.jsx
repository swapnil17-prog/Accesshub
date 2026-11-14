import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Outlet, useLocation } from 'react-router-dom';

import { fetchInboxCount, selectInboxCount } from '../features/approvals/approvalsSlice';
import { XIcon } from './icons';
import Sidebar from './Sidebar';
import TopBar from './TopBar';

const INBOX_POLL_MS = 60_000;

/** App shell: fixed sidebar on large screens, slide-over drawer on small ones. */
export default function Layout() {
  const dispatch = useDispatch();
  const inboxCount = useSelector(selectInboxCount);
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  // Refresh the inbox badge on navigation and every minute while the tab is open.
  useEffect(() => {
    dispatch(fetchInboxCount());
  }, [dispatch, location.pathname]);
  useEffect(() => {
    const id = setInterval(() => dispatch(fetchInboxCount()), INBOX_POLL_MS);
    return () => clearInterval(id);
  }, [dispatch]);

  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 lg:block">
        <Sidebar inboxCount={inboxCount} />
      </aside>

      {menuOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-slate-900/60" onClick={() => setMenuOpen(false)} aria-hidden="true" />
          <div className="relative h-full w-72 max-w-[85%] shadow-xl">
            <Sidebar inboxCount={inboxCount} onNavigate={() => setMenuOpen(false)} />
            <button
              type="button"
              onClick={() => setMenuOpen(false)}
              className="absolute right-2 top-4 rounded-md p-2 text-slate-400 hover:text-white"
              aria-label="Close navigation"
            >
              <XIcon />
            </button>
          </div>
        </div>
      ) : null}

      <div className="flex min-h-screen flex-col lg:pl-64">
        <TopBar inboxCount={inboxCount} onOpenMenu={() => setMenuOpen(true)} />
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
