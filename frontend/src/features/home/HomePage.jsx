import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';

import { fetchHealth } from '../../app/healthSlice';

function Pill({ label, value }) {
  const ok = value === 'ok';
  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3">
      <span className="text-sm font-medium text-slate-600">{label}</span>
      <span
        className={`rounded-full px-2.5 py-0.5 text-sm font-semibold ${
          ok ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
        }`}
      >
        {value ?? '…'}
      </span>
    </div>
  );
}

export default function HomePage() {
  const dispatch = useDispatch();
  const { status, data } = useSelector((state) => state.health);

  useEffect(() => {
    dispatch(fetchHealth());
  }, [dispatch]);

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">AccessHub</h1>
        <p className="text-sm text-slate-500">Access Request &amp; Approval Portal</p>
      </div>

      <section className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">System status</h2>
        {status === 'loading' || status === 'idle' ? (
          <p className="text-sm text-slate-500">Checking API…</p>
        ) : (
          <>
            <Pill label="API" value={data?.status} />
            <Pill label="Database" value={data?.db} />
          </>
        )}
      </section>

      <button
        type="button"
        onClick={() => dispatch(fetchHealth())}
        className="self-start rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
      >
        Re-check
      </button>
    </main>
  );
}
