import React, { useState, useEffect } from 'react';
import Login from './components/Login';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import ScraperControl from './components/ScraperControl';
import CourseData from './components/CourseData';
import QuotaMonitor from './components/QuotaMonitor';
import ConfigManager from './components/ConfigManager';
import { ToastProvider } from './components/Toast';

export default function App() {
  return (
    <ToastProvider>
      <AppInner />
    </ToastProvider>
  );
}

function AppInner() {
  const [token, setToken] = useState(() => localStorage.getItem('token') || '');
  const [username, setUsername] = useState('');
  const [activeTab, setActiveTab] = useState('dashboard');
  const [authenticating, setAuthenticating] = useState(true);

  // Validate token on startup or change
  useEffect(() => {
    const validateToken = async () => {
      if (!token) {
        setAuthenticating(false);
        return;
      }

      try {
        const response = await fetch('/api/auth/me', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error('Token validation failed');
        }

        const data = await response.json();
        setUsername(data.username);
      } catch (err) {
        console.warn('Authentication token expired or server offline. Logging out...');
        localStorage.removeItem('token');
        setToken('');
      } finally {
        setAuthenticating(false);
      }
    };

    validateToken();
  }, [token]);

  const handleLoginSuccess = (newToken) => {
    setToken(newToken);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken('');
    setUsername('');
    setActiveTab('dashboard');
  };

  if (authenticating) {
    return (
      <div className="min-h-screen w-screen bg-[hsl(var(--bg-primary))] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <svg className="animate-spin h-9 w-9 text-[hsl(var(--accent-primary))]" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <span className="text-[hsl(var(--text-secondary))] text-xs uppercase tracking-wider font-semibold">Validating Credentials...</span>
        </div>
      </div>
    );
  }

  // Render auth lock screen if no valid session token
  if (!token) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  // Render Portal layout
  return (
    <div className="min-h-screen w-screen flex bg-[hsl(var(--bg-primary))] text-[hsl(var(--text-primary))] overflow-hidden select-none">
      {/* Navigation Sidebar */}
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        onLogout={handleLogout} 
        username={username || 'Administrator'} 
      />

      {/* Main Administrative Dashboard Stage */}
      <main className="flex-1 flex flex-col min-h-screen overflow-hidden bg-[hsl(var(--bg-primary))]">
        {activeTab === 'dashboard' && <Dashboard setActiveTab={setActiveTab} token={token} />}
        {activeTab === 'scraper' && <ScraperControl token={token} />}
        {activeTab === 'data' && <CourseData token={token} />}
        {activeTab === 'quota' && <QuotaMonitor token={token} />}
        {activeTab === 'config' && <ConfigManager token={token} />}
      </main>
    </div>
  );
}
