import { createContext, useContext } from 'react';

export const ToastContext = createContext({
  toast: () => {},
  success: () => {},
  error: () => {},
  info: () => {},
  dismiss: () => {},
});

export function useToast() {
  const ctx = useContext(ToastContext);

  const showToast = (message, variant = 'info', opts = {}) => {
    if (ctx && ctx.toast) {
      return ctx.toast(variant, message, opts);
    }
  };

  showToast.success = (msg, opts) => ctx?.success?.(msg, opts);
  showToast.error = (msg, opts) => ctx?.error?.(msg, opts);
  showToast.info = (msg, opts) => ctx?.info?.(msg, opts);
  showToast.dismiss = (id) => ctx?.dismiss?.(id);
  showToast.toast = ctx?.toast;

  return showToast;
}
