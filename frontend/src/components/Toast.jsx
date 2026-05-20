import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';
import { ToastContext } from '../hooks/useToast';

let toastIdSeed = 0;

const VARIANT_STYLES = {
  success: {
    border: 'hsla(var(--color-success)/0.35)',
    bg: 'hsla(var(--color-success)/0.08)',
    color: 'hsl(var(--color-success))',
    Icon: CheckCircle2,
    role: 'status',
    live: 'polite',
  },
  error: {
    border: 'hsla(var(--color-danger)/0.35)',
    bg: 'hsla(var(--color-danger)/0.08)',
    color: 'hsl(var(--color-danger))',
    Icon: AlertCircle,
    role: 'alert',
    live: 'assertive',
  },
  info: {
    border: 'hsla(var(--color-info)/0.35)',
    bg: 'hsla(var(--color-info)/0.08)',
    color: 'hsl(var(--color-info))',
    Icon: Info,
    role: 'status',
    live: 'polite',
  },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timersRef = useRef(new Map());

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, []);

  const push = useCallback((variant, message, opts = {}) => {
    const id = ++toastIdSeed;
    const duration = opts.duration ?? (variant === 'error' ? 6000 : 3500);
    setToasts((prev) => [...prev, { id, variant, message }]);
    if (duration > 0) {
      const handle = setTimeout(() => dismiss(id), duration);
      timersRef.current.set(id, handle);
    }
    return id;
  }, [dismiss]);

  useEffect(() => () => {
    timersRef.current.forEach((t) => clearTimeout(t));
    timersRef.current.clear();
  }, []);

  const value = {
    toast: push,
    success: (msg, opts) => push('success', msg, opts),
    error: (msg, opts) => push('error', msg, opts),
    info: (msg, opts) => push('info', msg, opts),
    dismiss,
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm pointer-events-none"
      >
        {toasts.map((t) => {
          const v = VARIANT_STYLES[t.variant] || VARIANT_STYLES.info;
          const Icon = v.Icon;
          return (
            <div
              key={t.id}
              role={v.role}
              aria-live={v.live}
              className="glass-panel pointer-events-auto flex items-start gap-3 p-3 pr-2 animate-fade-in"
              style={{ borderColor: v.border, background: v.bg }}
            >
              <Icon size={18} style={{ color: v.color }} className="mt-0.5 shrink-0" />
              <div className="text-xs text-[hsl(var(--text-primary))] leading-relaxed flex-1">
                {t.message}
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss notification"
                className="text-[hsl(var(--text-muted))] hover:text-[hsl(var(--text-primary))] p-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-primary))]"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
