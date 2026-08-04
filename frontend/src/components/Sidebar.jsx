import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Terminal,
  Search,
  Activity,
  Sliders,
  LogOut,
  Menu,
  X,
  User,
  ExternalLink,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Sidebar() {
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navItems = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/scraper', label: 'Scraper Controller', icon: Terminal },
    { to: '/explorer', label: 'Course Explorer', icon: Search },
    { to: '/quota', label: 'Quota Monitor', icon: Activity },
    { to: '/config', label: 'Session Config', icon: Sliders },
  ];

  const toggleMobile = () => setMobileOpen((prev) => !prev);
  const closeMobile = () => setMobileOpen(false);

  return (
    <>
      {/* Mobile Top Navigation Bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-16 bg-slate-950/80 backdrop-blur-xl border-b border-white/10 px-4 flex items-center justify-between z-40">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-violet-600 to-pink-500 flex items-center justify-center text-white font-black text-sm shadow-md">
            BS
          </div>
          <span className="font-extrabold text-white text-base tracking-tight">BOUN Scraper</span>
        </div>

        <button
          onClick={toggleMobile}
          aria-label="Toggle navigation menu"
          className="p-2.5 rounded-xl glass-panel text-slate-300 hover:text-white"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Drawer Overlay Backing */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-40 animate-fade-in"
          onClick={closeMobile}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 w-64 bg-slate-950/90 border-r border-white/10 backdrop-blur-2xl z-50 flex flex-col justify-between transition-transform duration-300 ease-in-out md:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div>
          {/* Header Brand */}
          <div className="h-20 px-6 flex items-center gap-3 border-b border-white/5">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-violet-600 to-pink-500 flex items-center justify-center text-white font-extrabold text-lg shadow-lg shadow-violet-500/25">
              B
            </div>
            <div>
              <h2 className="font-extrabold text-white text-base tracking-tight leading-none">
                BOUN Scraper
              </h2>
              <span className="text-[10px] uppercase font-bold text-violet-400 tracking-wider">
                Admin Console
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  onClick={closeMobile}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-4 py-3 rounded-xl font-medium text-sm transition-all duration-200 ${
                      isActive
                        ? 'bg-gradient-to-r from-violet-600/30 to-pink-500/20 text-white border border-violet-500/40 shadow-lg shadow-violet-500/10'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                    }`
                  }
                >
                  <Icon className="w-5 h-5 shrink-0" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Footer Profile & Logout */}
        <div className="p-4 border-t border-white/5 space-y-3">
          {/* University Link */}
          <a
            href="https://registration.bogazici.edu.tr"
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-slate-900/50 hover:bg-slate-900 border border-white/5 text-slate-400 hover:text-slate-200 text-xs transition-colors"
          >
            <span>BOUN Portal</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>

          {/* User Badge & Logout */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/80 border border-white/10">
            <div className="flex items-center gap-2.5 overflow-hidden">
              <div className="w-8 h-8 rounded-lg bg-violet-500/20 text-violet-300 border border-violet-500/30 flex items-center justify-center shrink-0 font-bold text-xs">
                <User className="w-4 h-4" />
              </div>
              <div className="truncate">
                <p className="text-xs font-bold text-white truncate">
                  {user?.username || 'Administrator'}
                </p>
                <span className="text-[10px] text-slate-400 font-medium">Session Active</span>
              </div>
            </div>

            <button
              onClick={logout}
              title="Logout"
              className="p-2 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
