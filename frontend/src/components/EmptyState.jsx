import React from 'react';

export default function EmptyState({ 
  title = '[STATUS: NO_RECORDS_FOUND]', 
  description = 'No matching data located in current memory buffer.', 
  icon: Icon, 
  action 
}) {
  return (
    <div
      className="animate-fade-in"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 16px',
        textAlign: 'center',
        fontFamily: 'var(--font-mono)',
      }}
    >
      <div
        style={{
          padding: '16px',
          border: '1px dashed var(--border-hard)',
          background: 'var(--bg-tertiary)',
          color: 'var(--neon-green)',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {Icon ? <Icon size={32} style={{ opacity: 0.6 }} /> : <span style={{ fontSize: '18px' }}>[Ø]</span>}
      </div>
      <h3
        style={{
          fontSize: '13px',
          fontWeight: 700,
          color: 'var(--text-primary)',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          marginBottom: '6px',
        }}
      >
        {title}
      </h3>
      <p
        style={{
          fontSize: '11px',
          color: 'var(--text-secondary)',
          maxWidth: '380px',
          lineHeight: '1.5',
          marginBottom: '20px',
        }}
      >
        {description}
      </p>
      {action && (
        <button 
          onClick={action.onClick} 
          className="btn-cyber btn-cyber-primary"
          style={{ fontSize: '10px', padding: '6px 16px' }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
