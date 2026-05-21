import React from 'react';
import { LucideIcon } from 'lucide-react';

export default function EmptyState({ 
  title, 
  description, 
  icon: Icon, 
  action 
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center animate-fade-in">
      <div className="p-5 rounded-3xl bg-[hsla(var(--bg-tertiary)/0.5)] border border-[hsla(var(--glass-border))] text-[hsl(var(--text-muted))] mb-5 shadow-inner">
        {Icon && <Icon size={40} className="opacity-40" aria-hidden="true" />}
      </div>
      <h3 className="text-lg font-bold text-[hsl(var(--text-primary))] mb-2">{title}</h3>
      <p className="text-sm text-[hsl(var(--text-secondary))] max-w-sm mx-auto leading-relaxed mb-8">
        {description}
      </p>
      {action && (
        <button 
          onClick={action.onClick} 
          className="btn-primary text-xs py-2.5 px-6"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
