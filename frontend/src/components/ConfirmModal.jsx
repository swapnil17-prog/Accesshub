import { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';

import Button from './Button';

/**
 * Accessible confirmation dialog: Escape and the backdrop cancel, focus moves into the
 * dialog when it opens. ``children`` can hold extra fields (e.g. a required comment).
 */
export default function ConfirmModal({
  open,
  title,
  message,
  children,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'primary',
  loading = false,
  confirmDisabled = false,
  onConfirm,
  onCancel,
}) {
  const titleId = useId();
  const panelRef = useRef(null);
  // Latest handler/state in refs, so the effects below run only when the dialog opens or
  // closes. (Depending on an inline onCancel re-ran them on every render, which moved focus back
  // to the first field after each keystroke.)
  const latest = useRef({ onCancel, loading });
  useEffect(() => {
    latest.current = { onCancel, loading };
  });

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape' && !latest.current.loading) latest.current.onCancel?.();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  useEffect(() => {
    if (open) panelRef.current?.querySelector('textarea, input, select, button')?.focus();
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center">
      <div className="absolute inset-0 bg-slate-900/50" aria-hidden="true" onClick={loading ? undefined : onCancel} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
      >
        <h2 id={titleId} className="text-base font-semibold text-slate-900">
          {title}
        </h2>
        {message ? <div className="mt-2 text-sm text-slate-600">{message}</div> : null}
        {children ? <div className="mt-4">{children}</div> : null}
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant={tone === 'danger' ? 'danger' : 'primary'}
            onClick={onConfirm}
            loading={loading}
            disabled={confirmDisabled}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
