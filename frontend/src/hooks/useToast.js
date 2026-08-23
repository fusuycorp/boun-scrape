import { createContext, useContext, useMemo } from 'react';

export const ToastContext = createContext({
  toast: () => {},
  success: () => {},
  error: () => {},
  info: () => {},
  dismiss: () => {},
});

export function useToast() {
  const ctx = useContext(ToastContext);

  return useMemo(() => {
    return Object.assign(
      (message, variant = 'info', opts = {}) => ctx?.toast?.(variant, message, opts),
      {
        toast: (variant, message, opts) => ctx?.toast?.(variant, message, opts),
        success: (msg, opts) => ctx?.success?.(msg, opts),
        error: (msg, opts) => ctx?.error?.(msg, opts),
        info: (msg, opts) => ctx?.info?.(msg, opts),
        dismiss: (id) => ctx?.dismiss?.(id),
      }
    );
  }, [ctx]);
}
