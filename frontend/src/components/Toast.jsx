import { useCallback, useMemo, useReducer, useRef } from 'react';

import { AlertIcon, CheckCircleIcon, InfoIcon, XIcon } from './icons';
import { ToastContext } from './toastContext';

const DURATION_MS = 4500;

function reducer(state, action) {
  switch (action.type) {
    case 'add':
      return [...state.slice(-4), action.toast];
    case 'remove':
      return state.filter((t) => t.id !== action.id);
    default:
      return state;
  }
}

const STYLES = {
  success: { icon: CheckCircleIcon, tone: 'text-emerald-600' },
  error: { icon: AlertIcon, tone: 'text-rose-600' },
  info: { icon: InfoIcon, tone: 'text-indigo-600' },
};

/** Provides ``useToast()`` (components/toastContext.js): ``toast.success(msg)``, ``toast.error(msg)``, ``toast.info(msg)``. */
export function ToastProvider({ children }) {
  const [toasts, dispatch] = useReducer(reducer, []);
  const nextId = useRef(1);

  const dismiss = useCallback((id) => dispatch({ type: 'remove', id }), []);
  const show = useCallback(
    (variant, message, title) => {
      const id = nextId.current++;
      dispatch({ type: 'add', toast: { id, variant, message, title } });
      setTimeout(() => dismiss(id), DURATION_MS);
      return id;
    },
    [dismiss],
  );

  const api = useMemo(
    () => ({
      success: (message, title) => show('success', message, title),
      error: (message, title) => show('error', message, title),
      info: (message, title) => show('info', message, title),
      dismiss,
    }),
    [show, dismiss],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:items-end"
      >
        {toasts.map((toast) => {
          const { icon: ToastIcon, tone } = STYLES[toast.variant] ?? STYLES.info;
          return (
            <div
              key={toast.id}
              role={toast.variant === 'error' ? 'alert' : 'status'}
              className="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg bg-white p-4 shadow-lg ring-1 ring-slate-900/10"
            >
              <ToastIcon className={`h-5 w-5 shrink-0 ${tone}`} />
              <div className="min-w-0 flex-1 text-sm">
                {toast.title ? <p className="font-semibold text-slate-900">{toast.title}</p> : null}
                <p className="text-slate-600">{toast.message}</p>
              </div>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                className="rounded p-0.5 text-slate-400 hover:text-slate-600"
                aria-label="Dismiss notification"
              >
                <XIcon className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
