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
        showToast(err.message || 'FAILED_TO_LOAD_TELEMETRY', 'error');
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
      code: '01',
      title: 'COURSES_INDEXED',
      value: stats?.total_courses?.toLocaleString() || '0',
      icon: BookOpen,
      color: 'var(--neon-green)',
    },
    {
      code: '02',
      title: 'TIME_SLOTS',
      value: stats?.total_slots?.toLocaleString() || '0',
      icon: Layers,
      color: 'var(--neon-cyan)',
    },
    {
      code: '03',
      title: 'DEPARTMENTS',
      value: stats?.total_departments?.toLocaleString() || '0',
      icon: Building2,
      color: 'var(--neon-amber)',
    },
    {
      code: '04',
      title: 'SEMESTERS',
      value: stats?.total_terms?.toLocaleString() || '0',
      icon: Calendar,
      color: 'var(--neon-pink)',
    },
  ];

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header Banner */}
      <div className="cyber-card" style={{ border: '2px solid var(--border-hard)', padding: '20px' }}>
        <div className="hazard-bar" style={{ marginBottom: '14px' }} />
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span className="led-indicator led-green" />
              <span style={{ color: 'var(--neon-green)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em' }}>
                SYS://CONTROL_MAINFRAME // V2.0
              </span>
            </div>
            <h1 className="glow-green" style={{ color: 'var(--neon-green)', fontSize: '20px', margin: 0 }}>
              /// ADMINISTRATIVE_CONTROL_CENTER
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '6px', maxWidth: '640px' }}>
              Real-time course timetable indexing telemetry, multi-stage crawler execution, and live quota surveillance radar.
            </p>
          </div>

          <button
            onClick={fetchDashboardData}
            disabled={refreshing}
            className="btn-cyber"
            style={{ fontSize: '11px', padding: '8px 16px' }}
          >
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} style={{ color: 'var(--neon-green)' }} />
            <span>{refreshing ? '[...POLLING]' : '[>> RELOAD_TELEMETRY]'}</span>
          </button>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.code}
              className="cyber-card"
              style={{
                border: '1px solid var(--border-hard)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <span style={{ color: 'var(--neon-amber)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em' }}>
                  [{card.code}] {card.title}
                </span>
                <Icon size={16} style={{ color: card.color, opacity: 0.7 }} />
              </div>
              <div>
                {loading ? (
                  <span style={{ color: 'var(--text-muted)', fontSize: '22px', fontWeight: 700 }}>[...]</span>
                ) : (
                  <span
                    style={{
                      color: card.color,
                      fontSize: '28px',
                      fontWeight: 800,
                      letterSpacing: '-0.02em',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {card.value}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Connectivity Status & Operational Launchpad */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Connectivity Status */}
        <div className="cyber-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <ShieldCheck size={16} style={{ color: 'var(--neon-green)' }} />
              <h3 style={{ fontSize: '13px', margin: 0, color: 'var(--text-primary)' }}>
                [+] CRAWLER_CONNECTIVITY_STATUS
              </h3>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '11px', marginBottom: '16px' }}>
              Bypass tokens &amp; ASP.NET ViewState form payload integrity.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {/* Cookie */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 12px',
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border-dim)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Cookie size={14} style={{ color: 'var(--neon-amber)' }} />
                  <span style={{ fontSize: '11px', color: 'var(--text-primary)' }}>KEYRING: ASP.NET_SessionId</span>
                </div>
                {configStatus?.cookie_loaded ? (
                  <span className="cyber-badge cyber-badge-green">[● MOUNTED]</span>
                ) : (
                  <span className="cyber-badge cyber-badge-amber">[! MISSING]</span>
                )}
              </div>

              {/* Seed HTML */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 12px',
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border-dim)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileCode2 size={14} style={{ color: 'var(--neon-pink)' }} />
                  <span style={{ fontSize: '11px', color: 'var(--text-primary)' }}>SEED: response.html</span>
                </div>
                {configStatus?.seed_html_loaded ? (
                  <span className="cyber-badge cyber-badge-green">[● READY]</span>
                ) : (
                  <span className="cyber-badge cyber-badge-amber">[! UNSET]</span>
                )}
              </div>
            </div>
          </div>

          <div style={{ marginTop: '20px', paddingTop: '12px', borderTop: '1px solid var(--border-dim)' }}>
            <Link
              to="/config"
              className="btn-cyber"
              style={{ width: '100%', textDecoration: 'none', fontSize: '10px' }}
            >
              [&gt;&gt; CONFIGURE_SESSION_KEYS]
            </Link>
          </div>
        </div>

        {/* Operational Launchpad */}
        <div className="cyber-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <Terminal size={16} style={{ color: 'var(--neon-green)' }} />
            <h3 style={{ fontSize: '13px', margin: 0, color: 'var(--text-primary)' }}>
              [+] OPERATIONAL_LAUNCHPAD
            </h3>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '11px', marginBottom: '16px' }}>
            Direct execution triggers for ingestion, indexing, and radar systems.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <button
              onClick={() => navigate('/scraper')}
              className="cyber-card"
              style={{
                textAlign: 'left',
                border: '1px solid var(--border-hard)',
                padding: '12px',
                cursor: 'pointer',
                transition: 'border-color 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--neon-green)')}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-hard)')}
            >
              <div style={{ color: 'var(--neon-green)', fontSize: '11px', fontWeight: 700, marginBottom: '4px' }}>
                [EXEC &gt;&gt;] 01_PIPELINE_RUNNER
              </div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>
                Stages 1-4 pipeline execution with live stdout memory buffer.
              </div>
            </button>

            <button
              onClick={() => navigate('/explorer')}
              className="cyber-card"
              style={{
                textAlign: 'left',
                border: '1px solid var(--border-hard)',
                padding: '12px',
                cursor: 'pointer',
                transition: 'border-color 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--neon-cyan)')}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-hard)')}
            >
              <div style={{ color: 'var(--neon-cyan)', fontSize: '11px', fontWeight: 700, marginBottom: '4px' }}>
                [EXEC &gt;&gt;] 02_DATABASE_EXPLORER
              </div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>
                Timetable lookup, day-hour slot filtering, and UTF-8 CSV exports.
              </div>
            </button>

            <button
              onClick={() => navigate('/quota')}
              className="cyber-card"
              style={{
                textAlign: 'left',
                border: '1px solid var(--border-hard)',
                padding: '12px',
                cursor: 'pointer',
                transition: 'border-color 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--neon-pink)')}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-hard)')}
            >
              <div style={{ color: 'var(--neon-pink)', fontSize: '11px', fontWeight: 700, marginBottom: '4px' }}>
                [EXEC &gt;&gt;] 03_LIVE_QUOTA_RADAR
              </div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>
                Real-time 10s auto-polling radar for course section capacities.
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
