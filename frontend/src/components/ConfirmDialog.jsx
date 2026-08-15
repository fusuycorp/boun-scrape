import React, { useEffect, useRef } from 'react';
import { AlertTriangle, X } from 'lucide-react';

export default function ConfirmDialog({
  open,
  title = 'CONFIRM_OPERATION?',
  description,
  confirmLabel = '[CONFIRM_EXECUTION]',
  cancelLabel = '[ABORT]',
  destructive = false,
  busy = false,
  onConfirm,
  onCancel,
}) {
  const confirmBtnRef = useRef(null);
  const previouslyFocused = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    previouslyFocused.current = document.activeElement;
    const t = setTimeout(() => confirmBtnRef.current?.focus(), 30);

    const handleKey = (e) => {
      if (e.key === 'Escape' && !busy) {
        e.preventDefault();
        onCancel?.();
      }
    };
    document.addEventListener('keydown', handleKey);

    return () => {
      clearTimeout(t);
      document.removeEventListener('keydown', handleKey);
      if (previouslyFocused.current && typeof previouslyFocused.current.focus === 'function') {
        previouslyFocused.current.focus();
      }
    };
  }, [open, busy, onCancel]);

  if (!open) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-desc"
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(5, 5, 8, 0.85)',
        }}
        onClick={() => !busy && onCancel?.()}
        aria-hidden="true"
      />
      <div
        className="cyber-card animate-fade-in"
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: '460px',
          padding: '20px',
          border: `2px solid ${destructive ? 'var(--neon-pink)' : 'var(--neon-amber)'}`,
          zIndex: 10,
          boxShadow: '6px 6px 0 rgba(0, 0, 0, 0.9)',
        }}
      >
        <div className="hazard-bar" style={{ marginBottom: '16px' }} />

        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
          <div
            style={{
              padding: '6px',
              border: `1px solid ${destructive ? 'var(--neon-pink)' : 'var(--neon-amber)'}`,
              color: destructive ? 'var(--neon-pink)' : 'var(--neon-amber)',
              background: destructive ? 'rgba(255, 0, 85, 0.08)' : 'rgba(255, 176, 0, 0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <AlertTriangle size={18} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2
              id="confirm-dialog-title"
              style={{
                fontSize: '13px',
                fontWeight: 700,
                color: destructive ? 'var(--neon-pink)' : 'var(--neon-amber)',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                margin: 0,
              }}
            >
              {title}
            </h2>
            {description && (
              <div
                id="confirm-dialog-desc"
                style={{
                  fontSize: '11px',
                  color: 'var(--text-secondary)',
                  marginTop: '8px',
                  lineHeight: '1.5',
                }}
              >
                {description}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => !busy && onCancel?.()}
            disabled={busy}
            aria-label="Close dialog"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '2px',
            }}
          >
            <X size={16} />
          </button>
        </div>

        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '20px' }}>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="btn-cyber"
            style={{ fontSize: '10px', padding: '6px 14px' }}
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmBtnRef}
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={`btn-cyber ${destructive ? 'btn-cyber-danger' : 'btn-cyber-primary'}`}
            style={{ fontSize: '10px', padding: '6px 14px' }}
          >
            {busy ? '[...PROCESSING]' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
