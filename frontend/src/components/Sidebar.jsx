import { NavLink } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { visibleSections } from '../navigation';
import { KeyIcon } from './icons';

function CountBadge({ count }) {
  if (!count) return null;
  return (
    <span className="ml-auto rounded-full bg-indigo-500 px-2 py-0.5 text-xs font-semibold text-white">
      {count > 99 ? '99+' : count}
    </span>
  );
}

export default function Sidebar({ inboxCount, onNavigate }) {
  const { hasRole } = useAuth();
  const sections = visibleSections(hasRole);

  return (
    <div className="flex h-full flex-col bg-slate-900 text-slate-300">
      <div className="flex h-16 shrink-0 items-center gap-2 px-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-md bg-indigo-500 text-white">
          <KeyIcon className="h-5 w-5" />
        </span>
        <span className="text-base font-semibold tracking-tight text-white">AccessHub</span>
      </div>
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4" aria-label="Main">
        {sections.map((section) => (
          <div key={section.label ?? 'main'}>
            {section.label ? (
              <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">{section.label}</p>
            ) : null}
            <ul className="space-y-1">
              {section.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                        isActive ? 'bg-slate-800 text-white' : 'hover:bg-slate-800/60 hover:text-white'
                      }`
                    }
                  >
                    <item.icon className="h-5 w-5 shrink-0" />
                    {item.label}
                    {item.badge === 'inbox' ? <CountBadge count={inboxCount} /> : null}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <p className="px-5 py-4 text-xs text-slate-500">Access Request &amp; Approval Portal</p>
    </div>
  );
}
