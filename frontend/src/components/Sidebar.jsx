import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Terminal,
  Database,
  Activity,
  Sliders,
  LogOut,
  Compass,
  Menu,
  X,
} from 'lucide-react';

const MENU_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, path: '/' },
  { id: 'scraper', label: 'Scraper Control', icon: Terminal, path: '/scraper' },
  { id: 'data', label: 'Course Explorer', icon: Database, path: '/explorer' },
  { id: 'quota', label: 'Quota Monitor', icon: Activity, path: '/quota' },
  { id: 'config', label: 'Configurations', icon: Sliders, path: '/config' },
];

export default function Sidebar({ onLogout, username }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile drawer on escape
  useEffect(() => {
    if (!mobileOpen) return undefined;
    const handler = (e) => {
      if (e.key === 'Escape') setMobileOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [mobileOpen]);

  const sidebarContent = (
    <>
      <div className="flex flex-col gap-8">
        {/* Brand Header */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-gradient-to-tr from-[hsl(var(--accent-primary))] to-[hsl(var(--accent-secondary))] text-white shadow-md">
              <Compass size={22} className="animate-spin-slow" aria-hidden="true" />
            </div>
            <div>
              <h1 className="font-extrabold text-[17px] text-gradient-purple tracking-wide leading-tight">ULTIMATE BOUN</h1>
              <p className="text-[10px] text-[hsl(var(--text-muted))] uppercase tracking-wider font-semibold">Admin Panel</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            className="lg:hidden p-1.5 rounded-md text-[hsl(var(--text-secondary))] hover:bg-[hsla(var(--bg-tertiary)/0.5)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-primary))]"
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        {/* Navigation Menu */}
        <nav role="navigation" aria-label="Primary" className="flex flex-col gap-1.5">
          <p className="text-[10px] text-[hsl(var(--text-muted))] uppercase font-bold tracking-wider mb-2 px-3" id="sidebar-section-label">
            Core Utilities
          </p>
          <ul aria-labelledby="sidebar-section-label" className="flex flex-col gap-1.5 list-none p-0 m-0">
            {MENU_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.id}>
                  <NavLink
                    to={item.path}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) => 
                      `w-full flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-primary))] ${
                        isActive
                          ? 'bg-[hsla(var(--accent-primary)/0.12)] text-[hsl(var(--text-primary))] border-l-4 border-[hsl(var(--accent-primary))] shadow-sm'
                          : 'text-[hsl(var(--text-secondary))] hover:bg-[hsla(var(--bg-tertiary)/0.5)] hover:text-[hsl(var(--text-primary))]'
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon
                          size={18}
                          aria-hidden="true"
                          className={isActive ? 'text-[hsl(var(--accent-primary))]' : 'text-[hsl(var(--text-muted))]'}
                        />
                        {item.label}
                      </>
                    )}
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>

      {/* Footer Profile & Logout */}
      <div className="flex flex-col gap-4 border-t border-[hsla(var(--glass-border))] pt-6">
        <div className="flex items-center gap-3 px-1">
          <div
            className="w-10 h-10 rounded-xl bg-[hsla(var(--accent-primary)/0.15)] border border-[hsla(var(--accent-primary)/0.3)] flex items-center justify-center font-bold text-[hsl(var(--accent-primary))]"
            aria-hidden="true"
          >
            {username.slice(0, 2).toUpperCase()}
          </div>
          <div className="overflow-hidden">
            <p className="text-sm font-semibold text-[hsl(var(--text-primary))] truncate">{username}</p>
            <span className="flex items-center gap-1.5 text-[10px] text-[hsl(var(--color-success))] font-medium uppercase tracking-wider">
              <span className="pulse-indicator pulse-green w-1.5 h-1.5" aria-hidden="true" />
              Online Session
            </span>
          </div>
        </div>

        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-[hsla(var(--glass-border))] text-sm font-medium text-[hsl(var(--text-secondary))] hover:bg-[hsla(var(--color-danger)/0.1)] hover:text-[hsl(var(--color-danger))] hover:border-[hsla(var(--color-danger)/0.2)] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-primary))]"
        >
          <LogOut size={16} aria-hidden="true" />
          End Session
        </button>
      </div>
    </>
  );

  return (
    <>
      {/* Mobile menu trigger */}
      <button
        type="button"
        onClick={() => setMobileOpen(true)}
        aria-label="Open navigation"
        aria-expanded={mobileOpen}
        className="lg:hidden fixed top-4 left-4 z-30 p-2 rounded-lg glass-panel text-[hsl(var(--text-primary))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-primary))]"
      >
        <Menu size={18} />
      </button>

      {/* Desktop sidebar */}
      <aside
        aria-label="Sidebar navigation"
        className="hidden lg:flex w-64 min-h-screen bg-[hsl(var(--bg-secondary))] border-r border-[hsla(var(--glass-border))] flex-col justify-between p-6 z-20"
      >
        {sidebarContent}
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside
            aria-label="Sidebar navigation"
            className="relative w-72 max-w-[85vw] min-h-screen bg-[hsl(var(--bg-secondary))] border-r border-[hsla(var(--glass-border))] flex flex-col justify-between p-6 animate-fade-in"
          >
            {sidebarContent}
          </aside>
        </div>
      )}
    </>
  );
}
