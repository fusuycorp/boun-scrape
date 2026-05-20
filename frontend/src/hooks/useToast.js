import { createContext, useContext } from 'react';

export const ToastContext = createContext({
  toast: () => {},
  success: () => {},
  error: () => {},
  info: () => {},
  dismiss: () => {},
});

export function useToast() {
  return useContext(ToastContext);
}
