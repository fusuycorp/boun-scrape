import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  BookOpen,
  Calendar,
  Layers,
  Building2,
  Terminal,
  Search,
  Activity,
  ShieldCheck,
  AlertTriangle,
  Play,
  RefreshCw,
  Cookie,
  FileCode2,
} from 'lucide-react';
import { api } from '../api/client';
import { useMountedRef } from '../hooks/useSafeAsync';
import { useToast } from '../hooks/useToast';

export default function Dashboard() {
  const navigate = useNavigate();
  const showToast = useToast();
  const isMountedRef = useMountedRef();

  const [stats, setStats] = useState(null);
  const [configStatus, setConfigStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchDashboardData = async () => {
    try {
      setRefreshing(true);
      const [statsRes, configRes] = await Promise.all([
        api.getStats().catch(() => ({ total_courses: 0, total_slots: 0, total_departments: 0, total_terms: 0 })),
        api.getScraperConfig().catch(() => ({ cookie_loaded: false, seed_html_loaded: false })),
      ]);

      if (isMountedRef.current) {
        setStats(statsRes);
        setConfigStatus(configRes);
      }
    } catch (err) {
      if (isMountedRef.current) {
        showToast(err.message || 'Failed to load dashboard statistics', 'error');
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const statCards = [
    {
      title: 'Total Courses',
      value: stats?.total_courses?.toLocaleString() || '0',
      icon: BookOpen,
      color: 'from-violet-500/20 to-purple-500/20 border-violet-500/30 text-violet-400',
    },
    {
      title: 'Time Slots',
      value: stats?.total_slots?.toLocaleString() || '0',
      icon: Layers,
      color: 'from-pink-500/20 to-rose-500/20 border-pink-500/30 text-pink-400',
    },
    {
      title: 'Departments',
      value: stats?.total_departments?.toLocaleString() || '0',
      icon: Building2,
      color: 'from-sky-500/20 to-blue-500/20 border-sky-500/30 text-sky-400',
    },
    {
      title: 'Semesters Indexed',
      value: stats?.total_terms?.toLocaleString() || '0',
      icon: Calendar,
      color: 'from-emerald-500/20 to-teal-500/20 border-emerald-500/30 text-emerald-400',
    },
  ];

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-2xl glass-panel p-8 border border-white/10 shadow-2xl">
        <div className="absolute top-0 right-0 -mt-12 -mr-12 w-64 h-64 bg-violet-600/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-1/3 -mb-12 w-64 h-64 bg-pink-600/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-xs font-semibold text-violet-300 mb-3">
              <Activity className="w-3.5 h-3.5 animate-pulse text-violet-400" />
              BOUN Registration Crawler System v2.0
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Administrative Control Center
            </h1>
            <p className="mt-2 text-slate-400 max-w-xl text-sm sm:text-base">
              Monitor real-time course registration schedule indexing, manage web crawler background stages, inspect section quotas, and search class timetables.
            </p>
          </div>

          <button
            onClick={fetchDashboardData}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl glass-panel hover:border-violet-500/50 text-slate-200 text-sm font-medium transition-all duration-200 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-violet-400' : ''}`} />
            Refresh Data
          </button>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {statCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div
              key={idx}
              className={`relative overflow-hidden rounded-2xl p-6 bg-gradient-to-br ${card.color} border backdrop-blur-xl transition-all duration-300 hover:scale-[1.02] shadow-lg`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold tracking-wider uppercase text-slate-300">
                  {card.title}
                </span>
                <div className="p-2.5 rounded-xl bg-slate-900/40 border border-white/10">
                  <Icon className="w-5 h-5" />
                </div>
              </div>
              <div className="mt-4">
                {loading ? (
                  <div className="h-8 w-24 bg-white/10 rounded animate-pulse" />
                ) : (
                  <span className="text-3xl font-extrabold text-white tracking-tight">
                    {card.value}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* System Status & Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Connection & Auth Health */}
        <div className="lg:col-span-1 rounded-2xl glass-panel p-6 border border-white/10 flex flex-col justify-between">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2.5">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              Crawler Connectivity Status
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Validates reCAPTCHA bypass session credentials stored on disk.
            </p>

            <div className="mt-6 space-y-4">
              <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-900/60 border border-white/5">
                <div className="flex items-center gap-3">
                  <Cookie className="w-4 h-4 text-violet-400" />
                  <span className="text-sm font-medium text-slate-200">Session Cookie</span>
                </div>
                {configStatus?.cookie_loaded ? (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-semibold border border-emerald-500/20">
                    Active
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 text-xs font-semibold border border-amber-500/20">
                    Missing
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-900/60 border border-white/5">
                <div className="flex items-center gap-3">
                  <FileCode2 className="w-4 h-4 text-pink-400" />
                  <span className="text-sm font-medium text-slate-200">Seed Form HTML</span>
                </div>
                {configStatus?.seed_html_loaded ? (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-semibold border border-emerald-500/20">
                    Ready
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 text-xs font-semibold border border-amber-500/20">
                    Unset
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-white/5">
            <Link
              to="/config"
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 transition-colors"
            >
              Configure Credentials
            </Link>
          </div>
        </div>

        {/* Quick Launchpad Shortcuts */}
        <div className="lg:col-span-2 rounded-2xl glass-panel p-6 border border-white/10">
          <h3 className="text-lg font-bold text-white flex items-center gap-2.5 mb-1">
            <Play className="w-5 h-5 text-violet-400" />
            Operational Launchpad
          </h3>
          <p className="text-xs text-slate-400 mb-6">
            Direct shortcuts to core system operations and indexing tasks.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <button
              onClick={() => navigate('/scraper')}
              className="p-5 rounded-2xl bg-gradient-to-br from-violet-900/30 to-purple-900/30 border border-violet-500/30 hover:border-violet-400 text-left transition-all duration-200 hover:scale-[1.02] group"
            >
              <div className="p-3 rounded-xl bg-violet-500/20 text-violet-300 w-fit mb-3 group-hover:bg-violet-500 group-hover:text-white transition-colors">
                <Terminal className="w-5 h-5" />
              </div>
              <h4 className="font-bold text-white text-sm">Pipeline Runner</h4>
              <p className="text-xs text-slate-400 mt-1">
                Execute stages 1 to 4 and monitor server terminal logs.
              </p>
            </button>

            <button
              onClick={() => navigate('/explorer')}
              className="p-5 rounded-2xl bg-gradient-to-br from-sky-900/30 to-blue-900/30 border border-sky-500/30 hover:border-sky-400 text-left transition-all duration-200 hover:scale-[1.02] group"
            >
              <div className="p-3 rounded-xl bg-sky-500/20 text-sky-300 w-fit mb-3 group-hover:bg-sky-500 group-hover:text-white transition-colors">
                <Search className="w-5 h-5" />
              </div>
              <h4 className="font-bold text-white text-sm">Database Explorer</h4>
              <p className="text-xs text-slate-400 mt-1">
                Filter courses, slots, instructors, and export UTF-8 CSV datasets.
              </p>
            </button>

            <button
              onClick={() => navigate('/quota')}
              className="p-5 rounded-2xl bg-gradient-to-br from-pink-900/30 to-rose-900/30 border border-pink-500/30 hover:border-pink-400 text-left transition-all duration-200 hover:scale-[1.02] group"
            >
              <div className="p-3 rounded-xl bg-pink-500/20 text-pink-300 w-fit mb-3 group-hover:bg-pink-500 group-hover:text-white transition-colors">
                <Activity className="w-5 h-5" />
              </div>
              <h4 className="font-bold text-white text-sm">Live Quota Watchlist</h4>
              <p className="text-xs text-slate-400 mt-1">
                Real-time 10s auto polling for course registration capacity.
              </p>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
