import React from 'react';
import { 
  LayoutDashboard, 
  Terminal, 
  Database, 
  Activity, 
  Sliders, 
  LogOut,
  Compass
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, onLogout, username }) {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'scraper', label: 'Scraper Control', icon: Terminal },
    { id: 'data', label: 'Course Explorer', icon: Database },
    { id: 'quota', label: 'Quota Monitor', icon: Activity },
    { id: 'config', label: 'Configurations', icon: Sliders },
  ];

  return (
    <aside className="w-64 min-h-screen bg-[hsl(var(--bg-secondary))] border-r border-[hsla(var(--glass-border))] flex flex-col justify-between p-6 z-20">
      <div className="flex flex-col gap-8">
        {/* Brand Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-tr from-[hsl(var(--accent-primary))] to-[hsl(var(--accent-secondary))] text-white shadow-md">
            <Compass size={22} className="animate-spin-slow" />
          </div>
          <div>
            <h1 className="font-extrabold text-[17px] text-gradient-purple tracking-wide leading-tight">ULTIMATE BOUN</h1>
            <p className="text-[10px] text-[hsl(var(--text-muted))] uppercase tracking-wider font-semibold">Admin Panel</p>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="flex flex-col gap-1.5">
          <p className="text-[10px] text-[hsl(var(--text-muted))] uppercase font-bold tracking-wider mb-2 px-3">
            Core Utilities
          </p>
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                  isActive 
                    ? 'bg-[hsla(var(--accent-primary)/0.12)] text-[hsl(var(--text-primary))] border-l-4 border-[hsl(var(--accent-primary))] shadow-sm'
                    : 'text-[hsl(var(--text-secondary))] hover:bg-[hsla(var(--bg-tertiary)/0.5)] hover:text-[hsl(var(--text-primary))]'
                }`}
              >
                <Icon size={18} className={isActive ? 'text-[hsl(var(--accent-primary))]' : 'text-[hsl(var(--text-muted))]'} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer Profile & Logout */}
      <div className="flex flex-col gap-4 border-t border-[hsla(var(--glass-border))] pt-6">
        <div className="flex items-center gap-3 px-1">
          <div className="w-10 h-10 rounded-xl bg-[hsla(var(--accent-primary)/0.15)] border border-[hsla(var(--accent-primary)/0.3)] flex items-center justify-center font-bold text-[hsl(var(--accent-primary))]">
            {username.slice(0, 2).toUpperCase()}
          </div>
          <div className="overflow-hidden">
            <p className="text-sm font-semibold text-[hsl(var(--text-primary))] truncate">{username}</p>
            <span className="flex items-center gap-1.5 text-[10px] text-[hsl(var(--color-success))] font-medium uppercase tracking-wider">
              <span className="pulse-indicator pulse-green w-1.5 h-1.5" />
              Online Session
            </span>
          </div>
        </div>

        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-[hsla(var(--glass-border))] text-sm font-medium text-[hsl(var(--text-secondary))] hover:bg-[hsla(var(--color-danger)/0.1)] hover:text-[hsl(var(--color-danger))] hover:border-[hsla(var(--color-danger)/0.2)] transition-all"
        >
          <LogOut size={16} />
          End Session
        </button>
      </div>
    </aside>
  );
}
