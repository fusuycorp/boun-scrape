import React, { useEffect, useRef } from 'react';
import { AlertTriangle, X } from 'lucide-react';

/**
 * Reusable accessible confirmation dialog.
 * Props:
 *  - open: boolean
 *  - title: string
 *  - description: string | ReactNode
 *  - confirmLabel: string (default "Confirm")
 *  - cancelLabel: string (default "Cancel")
 *  - destructive: boolean (styles confirm as danger)
 *  - busy: boolean (disables buttons + shows spinner)
 *  - onConfirm: () => void | Promise<void>
 *  - onCancel: () => void
 */
export default function ConfirmDialog({
  open,
  title = 'Are you sure?',
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
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
    // Focus confirm button on open (after paint)
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
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-desc"
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={() => !busy && onCancel?.()}
        aria-hidden="true"
      />
      <div className="glass-panel relative w-full max-w-md p-6 z-10">
        <div className="flex items-start gap-4">
          <div
            className={`p-2.5 rounded-xl shrink-0 ${
              destructive
                ? 'bg-[hsla(var(--color-danger)/0.12)] text-[hsl(var(--color-danger))] border border-[hsla(var(--color-danger)/0.25)]'
                : 'bg-[hsla(var(--accent-primary)/0.12)] text-[hsl(var(--accent-primary))] border border-[hsla(var(--accent-primary)/0.25)]'
            }`}
          >
            <AlertTriangle size={20} />
          </div>
          <div className="flex-1 min-w-0">
            <h2 id="confirm-dialog-title" className="text-base font-bold leading-tight">
              {title}
            </h2>
            {description && (
              <div
                id="confirm-dialog-desc"
                className="text-xs text-[hsl(var(--text-secondary))] mt-2 leading-relaxed"
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
            className="text-[hsl(var(--text-muted))] hover:text-[hsl(var(--text-primary))] p-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-primary))]"
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex gap-3 justify-end mt-6">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="btn-secondary text-xs py-2 px-4"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmBtnRef}
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={
              destructive
                ? 'btn-secondary text-xs py-2 px-4 text-[hsl(var(--color-danger))] border-[hsla(var(--color-danger)/0.3)] hover:bg-[hsla(var(--color-danger)/0.1)] hover:border-[hsla(var(--color-danger)/0.5)]'
                : 'btn-primary text-xs py-2 px-4'
            }
          >
            {busy ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Working...
              </span>
            ) : (
              confirmLabel
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
