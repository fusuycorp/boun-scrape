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

import './App.css';

function ProtectedRoute({ children }) {
  const { isAuthenticated, authenticating } = useAuth();
  const location = useLocation();

  if (authenticating) {
    return (
      <div className="min-h-screen w-full bg-slate-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-full border-2 border-violet-500 border-t-transparent animate-spin" />
          <span className="text-xs font-bold text-slate-400">Verifying session...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}

function MainLayout() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col md:flex-row font-sans selection:bg-violet-500 selection:text-white">
      <Sidebar />
      <main className="flex-1 md:ml-64 p-4 sm:p-8 pt-20 md:pt-8 max-w-7xl mx-auto w-full">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/scraper" element={<ScraperControl />} />
          <Route path="/explorer" element={<CourseData />} />
          <Route path="/quota" element={<QuotaMonitor />} />
          <Route path="/config" element={<ConfigManager />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
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
