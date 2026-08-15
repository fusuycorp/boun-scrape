import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';
import { ToastContext } from '../hooks/useToast';

let toastIdSeed = 0;

const VARIANT_STYLES = {
  success: {
    border: 'var(--neon-green)',
    bg: 'rgba(0, 255, 102, 0.08)',
    color: 'var(--neon-green)',
    prefix: '[SYS_OK]',
    Icon: CheckCircle2,
    role: 'status',
    live: 'polite',
  },
  error: {
    border: 'var(--neon-pink)',
    bg: 'rgba(255, 0, 85, 0.08)',
    color: 'var(--neon-pink)',
    prefix: '[SYS_FAIL]',
    Icon: AlertCircle,
    role: 'alert',
    live: 'assertive',
  },
  info: {
    border: 'var(--neon-cyan)',
    bg: 'rgba(0, 240, 255, 0.08)',
    color: 'var(--neon-cyan)',
    prefix: '[SYS_INFO]',
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
        style={{
          position: 'fixed',
          top: '32px',
          right: '16px',
          zIndex: 100,
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          maxWidth: '360px',
          width: '100%',
          pointerEvents: 'none',
        }}
      >
        {toasts.map((t) => {
          const v = VARIANT_STYLES[t.variant] || VARIANT_STYLES.info;
          const Icon = v.Icon;
          return (
            <div
              key={t.id}
              role={v.role}
              aria-live={v.live}
              className="animate-fade-in"
              style={{
                pointerEvents: 'auto',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
                padding: '10px 12px',
                background: 'var(--bg-secondary)',
                border: `1px solid ${v.border}`,
                boxShadow: '3px 3px 0 rgba(0, 0, 0, 0.8)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              <Icon size={16} style={{ color: v.color, marginTop: '2px', flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0, fontSize: '11px', lineHeight: '1.4' }}>
                <span style={{ color: v.color, fontWeight: 700, marginRight: '6px' }}>{v.prefix}</span>
                <span style={{ color: 'var(--text-primary)' }}>{t.message}</span>
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss notification"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '2px',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <X size={13} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
