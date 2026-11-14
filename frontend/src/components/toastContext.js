import { createContext, useContext } from 'react';

export const ToastContext = createContext(null);

/** ``toast.success(msg)``, ``toast.error(msg)``, ``toast.info(msg)``; needs <ToastProvider>. */
export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used inside <ToastProvider>');
  return context;
}
