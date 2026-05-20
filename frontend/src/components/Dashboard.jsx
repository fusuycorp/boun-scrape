import React, { useEffect, useState } from 'react';
import { 
  Database, 
  Clock, 
  FolderOpen, 
  MapPin, 
  ShieldCheck, 
  FileText, 
  ExternalLink,
  ChevronRight,
  Sparkles
} from 'lucide-react';

export default function Dashboard({ setActiveTab, token }) {
  const [stats, setStats] = useState({
    total_courses: 0,
    total_slots: 0,
    total_departments: 0,
    total_terms: 0,
  });
  const [config, setConfig] = useState({
    cookie_loaded: false,
    cookie_masked: '',
    seed_html_loaded: false,
    seed_html_size: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        
        // Fetch DB Stats
        const statsRes = await fetch('http://localhost:8000/api/stats', { headers });
        const statsData = await statsRes.json();
        setStats(statsData);

        // Fetch Configurations
        const configRes = await fetch('/api/config', { headers });
        const configData = await configRes.json();
        setConfig(configData);
      } catch (err) {
        console.error('Error loading dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [token]);

  const statCards = [
    { label: 'Total Courses', value: stats.total_courses, icon: Database, color: 'var(--accent-primary)' },
    { label: 'Time Slots Indexed', value: stats.total_slots, icon: Clock, color: 'var(--color-info)' },
    { label: 'Semesters Covered', value: stats.total_terms, icon: FolderOpen, color: 'var(--color-success)' },
    { label: 'Departments Listed', value: stats.total_departments, icon: MapPin, color: 'var(--accent-secondary)' },
  ];

  if (loading) {
    return (
      <div className="flex-1 p-8 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <svg className="animate-spin h-8 w-8 text-[hsl(var(--accent-primary))]" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <span className="text-[hsl(var(--text-secondary))] text-sm">Gathering System Metrics...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 p-8 overflow-y-auto relative space-y-8 animate-fade-in">
      {/* Decorative Glows */}
      <div className="bg-glow-violet top-[5%] right-[10%]" />
      
      {/* Welcome Header */}
      <div className="flex items-center justify-between z-10 relative">
        <div>
          <h1 className="text-3xl font-extrabold text-gradient tracking-tight">System Dashboard</h1>
          <p className="text-[hsl(var(--text-secondary))] text-sm mt-1">Real-time database statistics and scraper configurations</p>
        </div>
        <div className="hidden sm:flex items-center gap-2 bg-[hsla(var(--accent-primary)/0.08)] border border-[hsla(var(--accent-primary)/0.2)] px-4 py-2 rounded-2xl text-xs font-semibold text-[hsl(var(--accent-primary))]">
          <Sparkles size={14} className="animate-pulse" />
          Fullstack Scraper V1.0 Active
        </div>
      </div>

      {/* Grid of Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 relative z-10">
        {statCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div key={idx} className="glass-panel p-6 glass-panel-hover flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-[hsl(var(--text-secondary))] uppercase tracking-wider mb-1">{card.label}</p>
                <h3 className="text-2xl font-bold font-heading">{card.value.toLocaleString()}</h3>
              </div>
              <div 
                className="p-3.5 rounded-2xl flex items-center justify-center"
                style={{ backgroundColor: `hsla(${card.color} / 0.1)`, border: `1px solid hsla(${card.color} / 0.2)` }}
              >
                <Icon style={{ color: `hsl(${card.color})` }} size={24} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Main Grid Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 relative z-10">
        {/* System Health Check */}
        <div className="lg:col-span-2 glass-panel p-6 flex flex-col justify-between">
          <div>
            <h2 className="text-lg font-bold mb-1 flex items-center gap-2">
              <ShieldCheck size={20} className="text-[hsl(var(--color-success))]" />
              Crawler Connectivity & Credentials
            </h2>
            <p className="text-xs text-[hsl(var(--text-secondary))] mb-6">Verify loaded files and cookie tokens required to bypass reCAPTCHA</p>
            
            <div className="space-y-4">
              {/* Cookies row */}
              <div className="flex items-center justify-between p-4 rounded-xl bg-[hsla(var(--bg-tertiary)/0.5)] border border-[hsla(var(--glass-border))]">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-[hsla(var(--accent-primary)/0.1)] text-[hsl(var(--accent-primary))]">
                    <ShieldCheck size={18} />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold">reCAPTCHA Cookies</h4>
                    <p className="text-xs text-[hsl(var(--text-muted))]">Used for scheduling endpoints bypass</p>
                  </div>
                </div>
                <div>
                  {config.cookie_loaded ? (
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
                  <div className="p-2.5 rounded-lg bg-[hsla(var(--accent-secondary)/0.1)] text-[hsl(var(--accent-secondary))]">
                    <FileText size={18} />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold">Seed response.html File</h4>
                    <p className="text-xs text-[hsl(var(--text-muted))]">Entrypoint semester mapping index</p>
                  </div>
                </div>
                <div>
                  {config.seed_html_loaded ? (
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
            <button 
              onClick={() => setActiveTab('config')} 
              className="btn-primary text-xs py-2.5"
            >
              Update Credentials
              <ChevronRight size={14} />
            </button>
            <a 
              href="https://registration.bogazici.edu.tr/buis/General/schedule.aspx?p=semester" 
              target="_blank" 
              rel="noreferrer"
              className="btn-secondary text-xs py-2.5"
            >
              Visit Bogazici Portal
              <ExternalLink size={14} />
            </a>
          </div>
        </div>

        {/* Quick Launchpad Actions */}
        <div className="glass-panel p-6 flex flex-col justify-between">
          <div>
            <h2 className="text-lg font-bold mb-1">Quick Launchpad</h2>
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
                <ChevronRight size={16} className="text-[hsl(var(--text-muted))] group-hover:text-[hsl(var(--accent-primary))] transition-all" />
              </button>

              <button 
                onClick={() => setActiveTab('quota')}
                className="w-full flex items-center justify-between p-3.5 rounded-xl border border-[hsla(var(--glass-border))] bg-[hsla(var(--bg-tertiary)/0.3)] hover:bg-[hsla(var(--accent-secondary)/0.08)] hover:border-[hsla(var(--accent-secondary)/0.2)] transition-all group text-left"
              >
                <div>
                  <h4 className="text-sm font-semibold group-hover:text-[hsl(var(--accent-secondary))] transition-all">Open Quota Watchlist</h4>
                  <p className="text-[11px] text-[hsl(var(--text-muted))]">Check real-time course slots</p>
                </div>
                <ChevronRight size={16} className="text-[hsl(var(--text-muted))] group-hover:text-[hsl(var(--accent-secondary))] transition-all" />
              </button>

              <button 
                onClick={() => setActiveTab('data')}
                className="w-full flex items-center justify-between p-3.5 rounded-xl border border-[hsla(var(--glass-border))] bg-[hsla(var(--bg-tertiary)/0.3)] hover:bg-[hsla(var(--color-info)/0.08)] hover:border-[hsla(var(--color-info)/0.2)] transition-all group text-left"
              >
                <div>
                  <h4 className="text-sm font-semibold group-hover:text-[hsl(var(--color-info))] transition-all">Search Course Database</h4>
                  <p className="text-[11px] text-[hsl(var(--text-muted))]">Advanced filters & export</p>
                </div>
                <ChevronRight size={16} className="text-[hsl(var(--text-muted))] group-hover:text-[hsl(var(--color-info))] transition-all" />
              </button>
            </div>
          </div>
          
          <div className="text-[11px] text-center text-[hsl(var(--text-muted))] mt-6 pt-4 border-t border-[hsla(var(--glass-border))]">
            Designed for Bogazici Registration Tools
          </div>
        </div>
      </div>
    </div>
  );
}
