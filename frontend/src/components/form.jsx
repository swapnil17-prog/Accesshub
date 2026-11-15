// Form primitives with consistent styling and accessible error wiring.
import { controlClass } from '../utils/forms';

/** Wraps a control with its label, hint and error. ``id`` must match the control's id. */
export function Field({ id, label, hint, error, optional = false, children, className = '' }) {
  return (
    <div className={className}>
      <label htmlFor={id} className="flex items-baseline justify-between text-sm font-medium text-slate-700">
        <span>{label}</span>
        {optional ? <span className="text-xs font-normal text-slate-400">Optional</span> : null}
      </label>
      <div className="mt-1">{children}</div>
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-xs text-rose-600">
          {Array.isArray(error) ? error.join(' ') : error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function TextInput({ error, className = '', ...props }) {
  return <input className={`${controlClass(error)} px-3 ${className}`} {...props} />;
}

export function Select({ error, className = '', children, ...props }) {
  return (
    <select className={`${controlClass(error)} pl-3 pr-8 ${className}`} {...props}>
      {children}
    </select>
  );
}

export function Textarea({ error, className = '', ...props }) {
  return <textarea className={`${controlClass(error)} px-3 ${className}`} {...props} />;
}

/** A dismissible-free alert box for page-level errors. */
export function ErrorAlert({ title, children }) {
  return (
    <div role="alert" className="rounded-md bg-rose-50 p-4 text-sm text-rose-800 ring-1 ring-inset ring-rose-200">
      {title ? <p className="font-semibold">{title}</p> : null}
      <div className={title ? 'mt-1' : ''}>{children}</div>
    </div>
  );
}
