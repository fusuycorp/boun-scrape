import React, { useCallback, useEffect, useState } from 'react';
import {
  Database,
  Clock,
  FolderOpen,
  MapPin,
  ShieldCheck,
  FileText,
  ExternalLink,
  ChevronRight,
  Sparkles,
  AlertTriangle,
  RefreshCw,
  Inbox,
} from 'lucide-react';

const INITIAL_STATS = {
  total_courses: 0,
  total_slots: 0,
  total_departments: 0,
  total_terms: 0,
};

const INITIAL_CONFIG = {
  cookie_loaded: false,
  cookie_masked: '',
  seed_html_loaded: false,
  seed_html_size: 0,
};

export default function Dashboard({ setActiveTab, token }) {
  const [stats, setStats] = useState(INITIAL_STATS);
  const [config, setConfig] = useState(INITIAL_CONFIG);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const headers = { Authorization: `Bearer ${token}` };

      const [statsRes, configRes] = await Promise.all([
        fetch('/api/stats', { headers }),
        fetch('/api/config', { headers }),
      ]);

      if (!statsRes.ok) throw new Error('Failed to load database statistics.');
      if (!configRes.ok) throw new Error('Failed to load configuration status.');

      const statsData = await statsRes.json();
      const configData = await configRes.json();
      setStats(statsData);
      setConfig(configData);
    } catch (err) {
      console.error('Error loading dashboard data:', err);
      setError(err.message || 'Could not load dashboard data.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const statCards = [
    { label: 'Total Courses', value: stats.total_courses, icon: Database, color: 'var(--accent-primary)' },
    { label: 'Time Slots Indexed', value: stats.total_slots, icon: Clock, color: 'var(--color-info)' },
    { label: 'Semesters Covered', value: stats.total_terms, icon: FolderOpen, color: 'var(--color-success)' },
    { label: 'Departments Listed', value: stats.total_departments, icon: MapPin, color: 'var(--accent-secondary)' },
  ];

  const totalRecords =
    (stats.total_courses || 0) +
    (stats.total_slots || 0) +
    (stats.total_terms || 0) +
    (stats.total_departments || 0);
  const isEmpty = !loading && !error && totalRecords === 0;

  return (
    <div className="flex-1 p-8 overflow-y-auto relative space-y-8 animate-fade-in">
      <div className="bg-glow-violet top-[5%] right-[10%]" aria-hidden="true" />

      {/* Welcome Header */}
      <div className="flex items-center justify-between z-10 relative gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-extrabold text-gradient tracking-tight">System Dashboard</h1>
          <p className="text-[hsl(var(--text-secondary))] text-sm mt-1">Real-time database statistics and scraper configurations</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={fetchData}
            disabled={loading}
            className="btn-secondary text-xs py-2 px-3"
            aria-label="Refresh dashboard data"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} aria-hidden="true" />
            Refresh
          </button>
          <div className="hidden sm:flex items-center gap-2 bg-[hsla(var(--accent-primary)/0.08)] border border-[hsla(var(--accent-primary)/0.2)] px-4 py-2 rounded-2xl text-xs font-semibold text-[hsl(var(--accent-primary))]">
            <Sparkles size={14} className="animate-pulse" aria-hidden="true" />
            Fullstack Scraper V1.0 Active
          </div>
        </div>
      </div>

      {/* Status region for screen readers */}
      <div className="sr-only" aria-live="polite">
        {loading
          ? 'Loading dashboard metrics'
          : error
          ? `Dashboard failed to load: ${error}`
          : isEmpty
          ? 'Dashboard loaded with no data yet'
          : 'Dashboard metrics updated'}
      </div>

      {error && !loading && (
        <div
          role="alert"
          className="glass-panel p-5 flex items-start gap-3 border-[hsla(var(--color-danger)/0.3)] bg-[hsla(var(--color-danger)/0.05)]"
        >
          <AlertTriangle size={18} className="text-[hsl(var(--color-danger))] mt-0.5 shrink-0" aria-hidden="true" />
          <div className="flex-1">
            <h2 className="text-sm font-bold text-[hsl(var(--color-danger))]">Unable to load dashboard</h2>
            <p className="text-xs text-[hsl(var(--text-secondary))] mt-1">{error}</p>
          </div>
          <button onClick={fetchData} className="btn-secondary text-xs py-2 px-3 shrink-0">
            <RefreshCw size={14} aria-hidden="true" />
            Retry
          </button>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 relative z-10">
        {statCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div key={idx} className="glass-panel p-6 glass-panel-hover flex items-center justify-between">
              <div className="min-w-0">
                <p className="text-xs font-semibold text-[hsl(var(--text-secondary))] uppercase tracking-wider mb-1">
                  {card.label}
                </p>
                {loading ? (
                  <span className="skeleton h-7 w-20" aria-hidden="true" />
                ) : (
                  <h3 className="text-2xl font-bold font-heading">{(card.value ?? 0).toLocaleString()}</h3>
                )}
              </div>
              <div
                className="p-3.5 rounded-2xl flex items-center justify-center"
                style={{ backgroundColor: `hsla(${card.color} / 0.1)`, border: `1px solid hsla(${card.color} / 0.2)` }}
                aria-hidden="true"
              >
                <Icon style={{ color: `hsl(${card.color})` }} size={24} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Empty state callout */}
      {isEmpty && (
        <div className="glass-panel p-6 flex items-center gap-4 border-[hsla(var(--accent-primary)/0.2)]">
          <div className="p-3 rounded-xl bg-[hsla(var(--accent-primary)/0.1)] text-[hsl(var(--accent-primary))]">
            <Inbox size={22} aria-hidden="true" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-bold">No data scraped yet</h2>
            <p className="text-xs text-[hsl(var(--text-secondary))] mt-1">
              Configure credentials and run the scraper pipeline to populate the database.
            </p>
          </div>
          <button onClick={() => setActiveTab('scraper')} className="btn-primary text-xs py-2 px-3">
            Open Scraper
            <ChevronRight size={14} aria-hidden="true" />
          </button>
        </div>
      )}

      {/* Main Grid Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 relative z-10">
        {/* System Health Check */}
        <section className="lg:col-span-2 glass-panel p-6 flex flex-col justify-between" aria-labelledby="health-heading">
          <div>
            <h2 id="health-heading" className="text-lg font-bold mb-1 flex items-center gap-2">
              <ShieldCheck size={20} className="text-[hsl(var(--color-success))]" aria-hidden="true" />
              Crawler Connectivity & Credentials
            </h2>
            <p className="text-xs text-[hsl(var(--text-secondary))] mb-6">Verify loaded files and cookie tokens required to bypass reCAPTCHA</p>

            <div className="space-y-4">
              {/* Cookies row */}
              <div className="flex items-center justify-between p-4 rounded-xl bg-[hsla(var(--bg-tertiary)/0.5)] border border-[hsla(var(--glass-border))]">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-[hsla(var(--accent-primary)/0.1)] text-[hsl(var(--accent-primary))]" aria-hidden="true">
                    <ShieldCheck size={18} />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold">reCAPTCHA Cookies</h4>
                    <p className="text-xs text-[hsl(var(--text-muted))]">Used for scheduling endpoints bypass</p>
                  </div>
                </div>
                <div>
                  {loading ? (
                    <span className="skeleton h-5 w-24" aria-hidden="true" />
                  ) : config.cookie_loaded ? (
                    <span className="badge badge-success flex items-center gap-1.5">
                      Loaded: {config.cookie_masked}
                    </span>
                  ) : (
                    <span className="badge badge-danger">Not Configured</span>
                  )}
                </div>
              </div>

              {/* Seed HTML row */}
              <div className="flex items-center justify-between p-4 rounded-xl bg-[hsla(var(--bg-tertiary)/0.5)] border border-[hsla(var(--glass-border))]">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-[hsla(var(--accent-secondary)/0.1)] text-[hsl(var(--accent-secondary))]" aria-hidden="true">
                    <FileText size={18} />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold">Seed response.html File</h4>
                    <p className="text-xs text-[hsl(var(--text-muted))]">Entrypoint semester mapping index</p>
                  </div>
                </div>
                <div>
                  {loading ? (
                    <span className="skeleton h-5 w-24" aria-hidden="true" />
                  ) : config.seed_html_loaded ? (
                    <span className="badge badge-success flex items-center gap-1.5">
                      Active: {(config.seed_html_size / 1024).toFixed(1)} KB
                    </span>
                  ) : (
                    <span className="badge badge-danger">Not Found</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <button onClick={() => setActiveTab('config')} className="btn-primary text-xs py-2.5">
              Update Credentials
              <ChevronRight size={14} aria-hidden="true" />
            </button>
            <a
              href="https://registration.bogazici.edu.tr/buis/General/schedule.aspx?p=semester"
              target="_blank"
              rel="noreferrer"
              className="btn-secondary text-xs py-2.5"
            >
              Visit Bogazici Portal
              <ExternalLink size={14} aria-hidden="true" />
            </a>
          </div>
        </section>

        {/* Quick Launchpad Actions */}
        <section className="glass-panel p-6 flex flex-col justify-between" aria-labelledby="launchpad-heading">
          <div>
            <h2 id="launchpad-heading" className="text-lg font-bold mb-1">Quick Launchpad</h2>
            <p className="text-xs text-[hsl(var(--text-secondary))] mb-6">Accelerate daily administrative tasks</p>

            <div className="flex flex-col gap-3">
              <button
                onClick={() => setActiveTab('scraper')}
                className="w-full flex items-center justify-between p-3.5 rounded-xl border border-[hsla(var(--glass-border))] bg-[hsla(var(--bg-tertiary)/0.3)] hover:bg-[hsla(var(--accent-primary)/0.08)] hover:border-[hsla(var(--accent-primary)/0.2)] transition-all group text-left"
              >
                <div>
                  <h4 className="text-sm font-semibold group-hover:text-[hsl(var(--accent-primary))] transition-all">Launch Scraper Control</h4>
                  <p className="text-[11px] text-[hsl(var(--text-muted))]">Trigger stages 1 to 4</p>
                </div>
                <ChevronRight size={16} className="text-[hsl(var(--text-muted))] group-hover:text-[hsl(var(--accent-primary))] transition-all" aria-hidden="true" />
              </button>

              <button
                onClick={() => setActiveTab('quota')}
                className="w-full flex items-center justify-between p-3.5 rounded-xl border border-[hsla(var(--glass-border))] bg-[hsla(var(--bg-tertiary)/0.3)] hover:bg-[hsla(var(--accent-secondary)/0.08)] hover:border-[hsla(var(--accent-secondary)/0.2)] transition-all group text-left"
              >
                <div>
                  <h4 className="text-sm font-semibold group-hover:text-[hsl(var(--accent-secondary))] transition-all">Open Quota Watchlist</h4>
                  <p className="text-[11px] text-[hsl(var(--text-muted))]">Check real-time course slots</p>
                </div>
                <ChevronRight size={16} className="text-[hsl(var(--text-muted))] group-hover:text-[hsl(var(--accent-secondary))] transition-all" aria-hidden="true" />
              </button>

              <button
                onClick={() => setActiveTab('data')}
                className="w-full flex items-center justify-between p-3.5 rounded-xl border border-[hsla(var(--glass-border))] bg-[hsla(var(--bg-tertiary)/0.3)] hover:bg-[hsla(var(--color-info)/0.08)] hover:border-[hsla(var(--color-info)/0.2)] transition-all group text-left"
              >
                <div>
                  <h4 className="text-sm font-semibold group-hover:text-[hsl(var(--color-info))] transition-all">Search Course Database</h4>
                  <p className="text-[11px] text-[hsl(var(--text-muted))]">Advanced filters & export</p>
                </div>
                <ChevronRight size={16} className="text-[hsl(var(--text-muted))] group-hover:text-[hsl(var(--color-info))] transition-all" aria-hidden="true" />
              </button>
            </div>
          </div>

          <div className="text-[11px] text-center text-[hsl(var(--text-muted))] mt-6 pt-4 border-t border-[hsla(var(--glass-border))]">
            Designed for Bogazici Registration Tools
          </div>
        </section>
      </div>
    </div>
  );
}
