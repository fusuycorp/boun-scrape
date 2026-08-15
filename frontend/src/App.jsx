import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ToastProvider } from './components/Toast';

import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import ScraperControl from './components/ScraperControl';
import CourseData from './components/CourseData';
import QuotaMonitor from './components/QuotaMonitor';
import ConfigManager from './components/ConfigManager';
import Login from './components/Login';

function ProtectedRoute({ children }) {
  const { isAuthenticated, authenticating } = useAuth();
  const location = useLocation();

  if (authenticating) {
    return (
      <div style={{
        minHeight: '100vh',
        width: '100%',
        background: 'var(--bg-void)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: '12px',
      }}>
        <span className="glow-green" style={{
          color: 'var(--neon-green)',
          fontSize: '12px',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
        }}>
          [SYS] VERIFYING_SESSION_KEYS
          <span style={{ animation: 'blink-cursor 1s step-end infinite', marginLeft: '2px' }}>█</span>
        </span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}

function StatusTicker() {
  const now = new Date();
  const timestamp = now.toISOString().slice(0, 19).replace('T', ' ');

  return (
    <>
      {/* Top status ticker */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: '24px',
        background: 'var(--bg-tertiary)',
        borderBottom: '1px solid var(--border-hard)',
        display: 'flex',
        alignItems: 'center',
        paddingLeft: '12px',
        paddingRight: '12px',
        zIndex: 60,
        gap: '16px',
        overflow: 'hidden',
      }}>
        <span style={{ color: 'var(--neon-green)', fontSize: '10px', letterSpacing: '0.08em', whiteSpace: 'nowrap' }}>
          [BOUN://SCRAPER_DAEMON v2.0]
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: '10px', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
          [NODE: ISTANBUL_BOUN]
        </span>
        <span style={{ color: 'var(--neon-green)', fontSize: '10px', display: 'inline-flex', alignItems: 'center', gap: '4px', whiteSpace: 'nowrap' }}>
          <span className="led-indicator led-green" /> ONLINE
        </span>
        <span style={{ color: 'var(--neon-cyan)', fontSize: '10px', letterSpacing: '0.06em', marginLeft: 'auto', whiteSpace: 'nowrap' }}>
          [{timestamp}]
        </span>
      </div>

      {/* Bottom status bar */}
      <div style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: '22px',
        background: 'var(--bg-tertiary)',
        borderTop: '1px solid var(--border-hard)',
        display: 'flex',
        alignItems: 'center',
        paddingLeft: '12px',
        paddingRight: '12px',
        zIndex: 60,
        gap: '16px',
        overflow: 'hidden',
      }}>
        <span style={{ color: 'var(--neon-amber)', fontSize: '9px', letterSpacing: '0.08em', whiteSpace: 'nowrap' }}>
          [HEAP: 640K OK]
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: '9px', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
          [VIEWSTATE: BYPASSED]
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: '9px', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
          [ENC: NONE]
        </span>
        <span style={{ color: 'var(--neon-amber)', fontSize: '9px', letterSpacing: '0.06em', marginLeft: 'auto', whiteSpace: 'nowrap' }}>
          [ASP.NET_SessionId: ACTIVE]
        </span>
      </div>
    </>
  );
}

function MainLayout() {
  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg-void)',
      color: 'var(--text-primary)',
      display: 'flex',
    }}>
      <Sidebar />
      <main style={{
        flex: 1,
        marginLeft: '240px',
        padding: '48px 28px 40px 28px',
        maxWidth: '1200px',
        width: '100%',
      }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/scraper" element={<ScraperControl />} />
          <Route path="/explorer" element={<CourseData />} />
          <Route path="/quota" element={<QuotaMonitor />} />
          <Route path="/config" element={<ConfigManager />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <StatusTicker />
      <div className="crt-overlay" />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <MainLayout />
                </ProtectedRoute>
              }
            />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
