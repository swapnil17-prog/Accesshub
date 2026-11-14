import { Link } from 'react-router-dom';

import { LockIcon } from '../components/icons';

export default function ForbiddenPage() {
  return (
    <ErrorScreen
      icon={LockIcon}
      code="403"
      title="You don't have access to this page"
      description="Your role doesn't include this area. If you think you need it, submit an access request or ask an administrator."
    />
  );
}

export function ErrorScreen({ icon: IconComponent, code, title, description }) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
      <div className="rounded-full bg-slate-100 p-4 text-slate-500">
        <IconComponent className="h-8 w-8" />
      </div>
      <p className="mt-6 text-sm font-semibold text-indigo-600">{code}</p>
      <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
      <p className="mt-2 max-w-md text-sm text-slate-500">{description}</p>
      <Link
        to="/"
        className="mt-6 rounded-md bg-indigo-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
      >
        Back to dashboard
      </Link>
    </div>
  );
}
