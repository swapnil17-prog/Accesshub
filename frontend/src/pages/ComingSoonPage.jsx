import EmptyState from '../components/EmptyState';
import PageHeader from '../components/PageHeader';

/** Placeholder for screens built in later phases, so navigation and guards work today. */
export default function ComingSoonPage({ title, description }) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <div className="rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
        <EmptyState title="Coming soon" description="This screen is part of the next build phase." />
      </div>
    </>
  );
}
