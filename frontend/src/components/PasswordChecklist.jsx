import { passwordChecks } from '../utils/passwordPolicy';
import { CheckCircleIcon } from './icons';

/** Live password-policy hints under a password field. */
export default function PasswordChecklist({ password, id }) {
  return (
    <ul id={id} className="mt-2 space-y-1 text-xs" aria-label="Password requirements">
      {passwordChecks(password).map((check) => (
        <li key={check.id} className={`flex items-center gap-1.5 ${check.ok ? 'text-emerald-700' : 'text-slate-500'}`}>
          <CheckCircleIcon className={`h-3.5 w-3.5 ${check.ok ? '' : 'opacity-30'}`} />
          <span>
            {check.label}
            <span className="sr-only">{check.ok ? ' (met)' : ' (not met)'}</span>
          </span>
        </li>
      ))}
      <li className="text-slate-400">Not a common password, and not containing the person&apos;s name or email.</li>
    </ul>
  );
}
