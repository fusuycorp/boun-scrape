import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ToastProvider } from './components/Toast';

import Login from './components/Login';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import ScraperControl from './components/ScraperControl';
import CourseData from './components/CourseData';
import QuotaMonitor from './components/QuotaMonitor';
import ConfigManager from './components/ConfigManager';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

function ProtectedRoute({ children }) {
  const { isAuthenticated, authenticating } = useAuth();
  const location = useLocation();

  if (authenticating) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}

function LoadingScreen() {
  return (
    <div className="min-h-screen w-screen bg-[hsl(var(--bg-primary))] flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <svg className="animate-spin h-9 w-9 text-[hsl(var(--accent-primary))]" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <span className="text-[hsl(var(--text-secondary))] text-xs uppercase tracking-wider font-semibold">Validating Session...</span>
      </div>
    </div>
  );
}

function Layout({ children }) {
  const { logout, username } = useAuth();
  
  return (
    <div className="min-h-screen w-screen flex bg-[hsl(var(--bg-primary))] text-[hsl(var(--text-primary))] overflow-hidden select-none">
      <Sidebar 
        onLogout={logout} 
        username={username || 'Administrator'} 
      />

      <main className="flex-1 flex flex-col min-h-screen overflow-hidden bg-[hsl(var(--bg-primary))]">
        {children}
      </main>
    </div>
  );
}

function AppRoutes() {
  const { token, isAuthenticated, authenticating } = useAuth();

  if (authenticating) {
    return <LoadingScreen />;
  }

  return (
    <Routes>
      <Route path="/login" element={
        isAuthenticated ? <Navigate to="/" replace /> : <Login />
      } />
      
      <Route path="/" element={
        <ProtectedRoute>
          <Layout><Dashboard token={token} /></Layout>
        </ProtectedRoute>
      } />

      <Route path="/scraper" element={
        <ProtectedRoute>
          <Layout><ScraperControl token={token} /></Layout>
        </ProtectedRoute>
      } />

      <Route path="/explorer" element={
        <ProtectedRoute>
          <Layout><CourseData token={token} /></Layout>
        </ProtectedRoute>
      } />

      <Route path="/quota" element={
        <ProtectedRoute>
          <Layout><QuotaMonitor token={token} /></Layout>
        </ProtectedRoute>
      } />

      <Route path="/config" element={
        <ProtectedRoute>
          <Layout><ConfigManager token={token} /></Layout>
        </ProtectedRoute>
      } />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
