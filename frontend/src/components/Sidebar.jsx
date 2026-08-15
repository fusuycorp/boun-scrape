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
  ExternalLink,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Sidebar() {
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navItems = [
    { to: '/', label: '[01] //_DASHBOARD', icon: LayoutDashboard },
    { to: '/scraper', label: '[02] //_PIPELINE', icon: Terminal },
    { to: '/explorer', label: '[03] //_COURSES', icon: Search },
    { to: '/quota', label: '[04] //_QUOTA', icon: Activity },
    { to: '/config', label: '[05] //_CONFIG', icon: Sliders },
  ];

  const toggleMobile = () => setMobileOpen((prev) => !prev);
  const closeMobile = () => setMobileOpen(false);

  const navLinkStyle = (isActive) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '8px 14px',
    fontSize: '11px',
    fontWeight: 700,
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    fontFamily: 'var(--font-mono)',
    color: isActive ? 'var(--neon-green)' : 'var(--text-muted)',
    background: isActive ? 'rgba(0,255,102,0.05)' : 'transparent',
    borderLeft: isActive ? '2px solid var(--neon-green)' : '2px solid transparent',
    textDecoration: 'none',
    transition: 'all 0.1s ease',
  });

  return (
    <>
      {/* Mobile Top Bar */}
      <div style={{
        display: 'none',
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: '48px',
        background: 'var(--bg-tertiary)',
        borderBottom: '1px solid var(--border-hard)',
        padding: '0 12px',
        alignItems: 'center',
        justifyContent: 'space-between',
        zIndex: 40,
      }}>
        <span style={{ color: 'var(--neon-green)', fontSize: '12px', fontWeight: 700, letterSpacing: '0.08em' }}>
          [BOUN_DECK]
        </span>
        <button
          onClick={toggleMobile}
          aria-label="Toggle navigation menu"
          style={{
            padding: '6px',
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-hard)',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
          }}
        >
          {mobileOpen ? <X size={16} /> : <Menu size={16} />}
        </button>
      </div>

      {/* Sidebar */}
      <aside style={{
        position: 'fixed',
        top: '24px',
        bottom: '22px',
        left: 0,
        width: '240px',
        background: 'var(--bg-primary)',
        borderRight: '1px solid var(--border-hard)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        zIndex: 50,
        overflow: 'hidden',
      }}>
        <div>
          {/* ASCII Header */}
          <div style={{
            padding: '16px 14px',
            borderBottom: '1px solid var(--border-hard)',
          }}>
            <pre className="glow-green" style={{
              color: 'var(--neon-green)',
              fontSize: '10px',
              lineHeight: '1.3',
              margin: 0,
              fontFamily: 'var(--font-mono)',
            }}>
{`┌──────────────────┐
│  BOUN_DECK v2.0  │
└──────────────────┘`}
            </pre>
            <div style={{
              color: 'var(--neon-amber)',
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '0.06em',
              marginTop: '6px',
            }}>
              ROOT@BOUN-CRAWLER:~#
            </div>
          </div>

          {/* Navigation */}
          <nav style={{ padding: '10px 6px' }}>
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  onClick={closeMobile}
                  style={({ isActive }) => navLinkStyle(isActive)}
                >
                  <Icon size={14} style={{ flexShrink: 0, opacity: 0.7 }} />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Footer */}
        <div style={{ padding: '10px', borderTop: '1px solid var(--border-hard)' }}>
          {/* BOUN Portal Link */}
          <a
            href="https://registration.bogazici.edu.tr"
            target="_blank"
            rel="noreferrer"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '6px 10px',
              border: '1px solid var(--border-hard)',
              background: 'var(--bg-secondary)',
              color: 'var(--neon-green)',
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '0.06em',
              textDecoration: 'none',
              marginBottom: '8px',
            }}
          >
            <span>[&gt;&gt; UPLINK: BOUN.EDU.TR]</span>
            <ExternalLink size={10} />
          </a>

          {/* Operator Card */}
          <div style={{
            padding: '8px 10px',
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-hard)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div>
              <div style={{
                color: 'var(--neon-amber)',
                fontSize: '10px',
                fontWeight: 700,
                letterSpacing: '0.06em',
              }}>
                [OPERATOR: {user?.username || 'ADMIN'}]
              </div>
              <div style={{
                color: 'var(--text-muted)',
                fontSize: '9px',
                marginTop: '2px',
              }}>
                SESSION: ACTIVE
              </div>
            </div>

            <button
              onClick={logout}
              title="Logout"
              style={{
                padding: '4px 8px',
                background: 'rgba(255,0,85,0.06)',
                border: '1px solid var(--neon-pink)',
                color: 'var(--neon-pink)',
                fontSize: '9px',
                fontWeight: 700,
                letterSpacing: '0.08em',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
              }}
            >
              [EJECT]
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
