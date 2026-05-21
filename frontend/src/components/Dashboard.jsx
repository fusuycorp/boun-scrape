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
  AlertTriangle,
  RefreshCw,
  Inbox,
} from 'lucide-react';
import EmptyState from './EmptyState';

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

export default function Dashboard({ token }) {
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
    { label: 'Courses', value: stats.total_courses, icon: Database, color: 'var(--accent-primary)' },
    { label: 'Time Slots', value: stats.total_slots, icon: Clock, color: 'var(--color-info)' },
    { label: 'Semesters', value: stats.total_terms, icon: FolderOpen, color: 'var(--color-success)' },
    { label: 'Departments', value: stats.total_departments, icon: MapPin, color: 'var(--accent-secondary)' },
  ];

  const totalRecords =
    (stats.total_courses || 0) +
    (stats.total_slots || 0) +
    (stats.total_terms || 0) +
    (stats.total_departments || 0);
  const isEmpty = !loading && !error && totalRecords === 0;

  return (
    <div className="flex-1 p-4 sm:p-8 overflow-y-auto relative space-y-8 animate-fade-in">
      <div className="bg-glow-violet top-[5%] right-[10%]" aria-hidden="true" />

      {/* Welcome Header */}
      <div className="flex items-center justify-between z-10 relative gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gradient tracking-tight">System Dashboard</h1>
          <p className="text-[hsl(var(--text-secondary))] text-sm mt-1">Status overview and administrative shortcuts</p>
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
            Sync
          </button>
        </div>
      </div>

      {error && !loading && (
        <div
          role="alert"
          className="glass-panel p-5 flex items-start gap-3 border-[hsla(var(--color-danger)/0.3)] bg-[hsla(var(--color-danger)/0.05)]"
        >
          <AlertTriangle size={18} className="text-[hsl(var(--color-danger))] mt-0.5 shrink-0" aria-hidden="true" />
          <div className="flex-1">
            <h2 className="text-sm font-bold text-[hsl(var(--color-danger))]">Sync Failed</h2>
            <p className="text-xs text-[hsl(var(--text-secondary))] mt-1">{error}</p>
          </div>
          <button onClick={fetchData} className="btn-secondary text-xs py-2 px-3 shrink-0">
            Retry
          </button>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 relative z-10">
        {statCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div key={idx} className="glass-panel p-4 sm:p-6 glass-panel-hover flex items-center justify-between">
              <div className="min-w-0">
                <p className="text-[10px] font-bold text-[hsl(var(--text-muted))] uppercase tracking-widest mb-1 truncate">
                  {card.label}
                </p>
                {loading ? (
                  <span className="skeleton h-6 sm:h-7 w-16 sm:w-20" aria-hidden="true" />
                ) : (
                  <h3 className="text-xl sm:text-2xl font-bold font-heading">{(card.value ?? 0).toLocaleString()}</h3>
                )}
              </div>
              <div
                className="hidden sm:flex p-3 rounded-2xl items-center justify-center"
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
        <div className="glass-panel overflow-hidden border-[hsla(var(--accent-primary)/0.2)]">
           <EmptyState 
            title="Database is Empty" 
            description="It looks like you haven't scraped any data yet. Head over to the Scraper Control to begin the discovery and extraction process."
            icon={Inbox}
            action={{
              label: "Open Scraper",
              onClick: () => window.location.hash = '/scraper' // This is a bit hacky since I'm not using navigate here, let's fix that if possible or just use a link
            }}
          />
        </div>
      )}

      {/* Main Grid Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 relative z-10 pb-12">
        {/* System Health Check */}
        <section className="lg:col-span-2 glass-panel p-6 flex flex-col justify-between" aria-labelledby="health-heading">
          <div>
            <h2 id="health-heading" className="text-lg font-bold mb-1 flex items-center gap-2">
              <ShieldCheck size={20} className="text-[hsl(var(--color-success))]" aria-hidden="true" />
              Crawler Connectivity
            </h2>
            <p className="text-xs text-[hsl(var(--text-secondary))] mb-6">Credential status for bypassing reCAPTCHA</p>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-xl bg-[hsla(var(--bg-tertiary)/0.5)] border border-[hsla(var(--glass-border))]">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-[hsla(var(--accent-primary)/0.1)] text-[hsl(var(--accent-primary))]" aria-hidden="true">
                    <ShieldCheck size={18} />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold">reCAPTCHA Cookies</h4>
                    <p className="text-[10px] text-[hsl(var(--text-muted))] uppercase font-bold">Session Token</p>
                  </div>
                </div>
                <div>
                  {loading ? (
                    <span className="skeleton h-5 w-24" aria-hidden="true" />
                  ) : config.cookie_loaded ? (
                    <span className="badge badge-success flex items-center gap-1.5">
                      Active: {config.cookie_masked}
                    </span>
                  ) : (
                    <span className="badge badge-danger">Missing</span>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-between p-4 rounded-xl bg-[hsla(var(--bg-tertiary)/0.5)] border border-[hsla(var(--glass-border))]">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-[hsla(var(--accent-secondary)/0.1)] text-[hsl(var(--accent-secondary))]" aria-hidden="true">
                    <FileText size={18} />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold">Seed Mapping File</h4>
                    <p className="text-[10px] text-[hsl(var(--text-muted))] uppercase font-bold">response.html</p>
                  </div>
                </div>
                <div>
                  {loading ? (
                    <span className="skeleton h-5 w-24" aria-hidden="true" />
                  ) : config.seed_html_loaded ? (
                    <span className="badge badge-success flex items-center gap-1.5">
                      Loaded: {(config.seed_html_size / 1024).toFixed(1)} KB
                    </span>
                  ) : (
                    <span className="badge badge-danger">Missing</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
             <a
              href="/config"
              onClick={(e) => { e.preventDefault(); window.location.pathname = '/config'; }}
              className="btn-primary text-xs py-2.5 px-4"
            >
              Update Credentials
            </a>
            <a
              href="https://registration.bogazici.edu.tr/buis/General/schedule.aspx?p=semester"
              target="_blank"
              rel="noreferrer"
              className="btn-secondary text-xs py-2.5 px-4 flex items-center gap-1.5"
            >
              Bogazici Portal
              <ExternalLink size={14} aria-hidden="true" />
            </a>
          </div>
        </section>

        {/* Quick Launchpad Actions */}
        <section className="glass-panel p-6 flex flex-col justify-between" aria-labelledby="launchpad-heading">
          <div>
            <h2 id="launchpad-heading" className="text-lg font-bold mb-1">Quick Launch</h2>
            <p className="text-xs text-[hsl(var(--text-secondary))] mb-6">Jump to active modules</p>

            <div className="flex flex-col gap-3">
              <LaunchpadButton 
                label="Scraper Control" 
                desc="Run Stage 1-4" 
                path="/scraper" 
                color="var(--accent-primary)" 
              />
              <LaunchpadButton 
                label="Quota Monitor" 
                desc="Real-time slots" 
                path="/quota" 
                color="var(--accent-secondary)" 
              />
              <LaunchpadButton 
                label="Course Explorer" 
                desc="Search database" 
                path="/explorer" 
                color="var(--color-info)" 
              />
            </div>
          </div>

          <div className="text-[10px] text-center text-[hsl(var(--text-muted))] font-bold uppercase tracking-widest mt-6 pt-4 border-t border-[hsla(var(--glass-border))]">
            BOUN Registration Suite
          </div>
        </section>
      </div>
    </div>
  );
}

function LaunchpadButton({ label, desc, path, color }) {
  return (
    <button
      onClick={() => window.location.pathname = path}
      className="w-full flex items-center justify-between p-3.5 rounded-xl border border-[hsla(var(--glass-border))] bg-[hsla(var(--bg-tertiary)/0.3)] hover:border-[hsla(var(--glass-border))] group text-left transition-all relative overflow-hidden"
    >
      <div className="absolute inset-0 bg-gradient-to-r from-transparent to-transparent group-hover:from-[hsla(var(--accent-primary)/0.05)] transition-all" style={{ '--accent-primary': color }} />
      <div className="relative z-10">
        <h4 className="text-sm font-bold group-hover:text-[hsl(var(--text-primary))] transition-all" style={{ color: `hsl(${color})` }}>{label}</h4>
        <p className="text-[10px] text-[hsl(var(--text-muted))] uppercase font-bold tracking-wider">{desc}</p>
      </div>
      <ChevronRight size={16} className="text-[hsl(var(--text-muted))] group-hover:translate-x-1 transition-all" aria-hidden="true" />
    </button>
  );
}
