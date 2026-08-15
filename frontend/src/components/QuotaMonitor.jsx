import React, { useState, useEffect } from 'react';
import {
  Activity,
  Plus,
  Trash2,
  RefreshCw,
  Clock,
  AlertTriangle,
} from 'lucide-react';
import { api } from '../api/client';
import { useMountedRef } from '../hooks/useSafeAsync';
import { useToast } from '../hooks/useToast';

export default function QuotaMonitor() {
  const showToast = useToast();
  const isMountedRef = useMountedRef();

  const [watchlist, setWatchlist] = useState(() => {
    try {
      const saved = localStorage.getItem('quota_watchlist');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [abbr, setAbbr] = useState('CMPE');
  const [code, setCode] = useState('150');
  const [sectionStart, setSectionStart] = useState('1');
  const [sectionEnd, setSectionEnd] = useState('1');
  const [term, setTerm] = useState('');
  const [termsList, setTermsList] = useState([]);

  const [quotaData, setQuotaData] = useState({});
  const [loadingMap, setLoadingMap] = useState({});
  const [pollingActive, setPollingActive] = useState(true);
  const [countdown, setCountdown] = useState(10);

  useEffect(() => {
    try {
      localStorage.setItem('quota_watchlist', JSON.stringify(watchlist));
    } catch {
      // Ignore
    }
  }, [watchlist]);

  useEffect(() => {
    api
      .getTerms()
      .then((data) => {
        if (isMountedRef.current && data && data.length > 0) {
          setTermsList(data);
          setTerm(data[0]);
        }
      })
      .catch(() => {});
  }, [isMountedRef]);

  const fetchSingleQuota = async (item) => {
    const key = `${item.abbr}_${item.code}_${item.section}_${item.term}`;
    if (isMountedRef.current) {
      setLoadingMap((prev) => ({ ...prev, [key]: true }));
    }

    try {
      const res = await api.checkQuota(item.abbr, item.code, item.section, item.term);
      if (isMountedRef.current) {
        setQuotaData((prev) => ({ ...prev, [key]: res }));
      }
    } catch (err) {
      if (isMountedRef.current) {
        setQuotaData((prev) => ({
          ...prev,
          [key]: { success: false, error: err.message || 'CHECK_FAILED' },
        }));
      }
    } finally {
      if (isMountedRef.current) {
        setLoadingMap((prev) => ({ ...prev, [key]: false }));
      }
    }
  };

  const pollAllQuotas = async () => {
    if (watchlist.length === 0) return;
    await Promise.all(watchlist.map((item) => fetchSingleQuota(item)));
  };

  useEffect(() => {
    if (!pollingActive || watchlist.length === 0) return;

    pollAllQuotas();
    setCountdown(10);

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          pollAllQuotas();
          return 10;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [pollingActive, watchlist]);

  const handleAddWatchlist = (e) => {
    e.preventDefault();
    const start = parseInt(sectionStart, 10) || 1;
    const end = parseInt(sectionEnd, 10) || start;

    const newItems = [];
    for (let s = start; s <= end; s++) {
      const secStr = s.toString().padStart(2, '0');
      const exists = watchlist.some(
        (w) => w.abbr === abbr.toUpperCase() && w.code === code && w.section === secStr && w.term === term
      );

      if (!exists) {
        newItems.push({
          abbr: abbr.toUpperCase().trim(),
          code: code.trim(),
          section: secStr,
          term,
        });
      }
    }

    if (newItems.length === 0) {
      showToast('SECTIONS_ALREADY_LOCKED_IN_WATCHLIST', 'info');
      return;
    }

    setWatchlist((prev) => [...prev, ...newItems]);
    showToast(`ENGAGED_RADAR_LOCK_FOR_${newItems.length}_SECTIONS`, 'success');
  };

  const handleRemove = (key) => {
    setWatchlist((prev) =>
      prev.filter((w) => `${w.abbr}_${w.code}_${w.section}_${w.term}` !== key)
    );
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span className="led-indicator led-green" />
            <span style={{ color: 'var(--neon-green)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em' }}>
              SYS://QUOTA_RADAR // ACTIVE_SURVEILLANCE
            </span>
          </div>
          <h1 className="glow-green" style={{ color: 'var(--neon-green)', fontSize: '20px', margin: 0 }}>
            /// LIVE_QUOTA_SURVEILLANCE_RADAR
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '4px' }}>
            Real-time automated capacity surveillance against Boğaziçi registration quota endpoints.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={() => setPollingActive((p) => !p)}
            className="btn-cyber"
            style={{
              fontSize: '11px',
              padding: '8px 14px',
              color: pollingActive ? 'var(--neon-green)' : 'var(--neon-amber)',
              borderColor: pollingActive ? 'var(--neon-green)' : 'var(--neon-amber)',
            }}
          >
            <Clock size={13} className={pollingActive ? 'animate-spin' : ''} />
            <span>{pollingActive ? `[RADAR: ARMED // ${countdown}s]` : '[RADAR: STANDBY]'}</span>
          </button>

          <button
            onClick={pollAllQuotas}
            disabled={watchlist.length === 0}
            className="btn-cyber btn-cyber-primary"
            style={{ fontSize: '11px', padding: '8px 16px' }}
          >
            <RefreshCw size={13} />
            <span>[&gt;&gt; PING_NOW]</span>
          </button>
        </div>
      </div>

      {/* Watchlist Generator Form */}
      <form onSubmit={handleAddWatchlist} className="cyber-card" style={{ border: '1px solid var(--border-hard)', padding: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <Plus size={14} style={{ color: 'var(--neon-green)' }} />
          <h3 style={{ fontSize: '12px', margin: 0, color: 'var(--neon-green)' }}>
            [+] ENGAGE_NEW_RADAR_TARGETS
          </h3>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', color: 'var(--neon-amber)', fontSize: '9px', fontWeight: 700, marginBottom: '4px' }}>
              DEPT_CODE:
            </label>
            <input
              type="text"
              value={abbr}
              onChange={(e) => setAbbr(e.target.value)}
              placeholder="CMPE"
              required
              className="cyber-input"
              style={{ textTransform: 'uppercase', fontWeight: 700 }}
            />
          </div>

          <div>
            <label style={{ display: 'block', color: 'var(--neon-amber)', fontSize: '9px', fontWeight: 700, marginBottom: '4px' }}>
              COURSE_NO:
            </label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="150"
              required
              className="cyber-input"
              style={{ fontWeight: 700 }}
            />
          </div>

          <div>
            <label style={{ display: 'block', color: 'var(--neon-amber)', fontSize: '9px', fontWeight: 700, marginBottom: '4px' }}>
              SECTION_RANGE:
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <input
                type="number"
                min="1"
                max="30"
                value={sectionStart}
                onChange={(e) => setSectionStart(e.target.value)}
                className="cyber-input"
                style={{ textAlign: 'center', fontWeight: 700 }}
              />
              <span style={{ color: 'var(--neon-green)', fontSize: '11px', fontWeight: 800 }}>&gt;&gt;</span>
              <input
                type="number"
                min="1"
                max="30"
                value={sectionEnd}
                onChange={(e) => setSectionEnd(e.target.value)}
                className="cyber-input"
                style={{ textAlign: 'center', fontWeight: 700 }}
              />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', color: 'var(--neon-amber)', fontSize: '9px', fontWeight: 700, marginBottom: '4px' }}>
              SEMESTER:
            </label>
            <select
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              required
              className="cyber-select"
            >
              {termsList.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div>
            <button
              type="submit"
              className="btn-cyber btn-cyber-primary"
              style={{ width: '100%', padding: '9px 12px', fontSize: '11px' }}
            >
              [+ LOCK_TARGET]
            </button>
          </div>
        </div>
      </form>

      {/* Watchlist Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {watchlist.length === 0 ? (
          <div className="cyber-card" style={{ gridColumn: '1 / -1', padding: '48px 16px', textAlign: 'center' }}>
            <Activity size={32} style={{ color: 'var(--border-hard)', margin: '0 auto 12px auto' }} />
            <div style={{ color: 'var(--text-primary)', fontSize: '12px', fontWeight: 700 }}>
              [STATUS: RADAR_WATCHLIST_EMPTY]
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: '4px' }}>
              Enter department and course section range above to lock radar targets.
            </div>
          </div>
        ) : (
          watchlist.map((item) => {
            const key = `${item.abbr}_${item.code}_${item.section}_${item.term}`;
            const res = quotaData[key];
            const isItemLoading = loadingMap[key];

            return (
              <div
                key={key}
                className="cyber-card"
                style={{
                  border: '1px solid var(--border-hard)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '12px',
                }}
              >
                {/* Card Header */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                      <span className="cyber-badge cyber-badge-green">{item.abbr}</span>
                      <span style={{ color: 'var(--neon-amber)', fontSize: '9px', fontWeight: 700 }}>{item.term}</span>
                    </div>
                    <div style={{ color: 'var(--neon-green)', fontSize: '16px', fontWeight: 800 }}>
                      {item.abbr} {item.code} <span style={{ color: 'var(--neon-cyan)' }}>.{item.section}</span>
                    </div>
                  </div>

                  <button
                    onClick={() => handleRemove(key)}
                    className="btn-cyber"
                    style={{ padding: '3px 8px', fontSize: '9px', color: 'var(--neon-pink)', borderColor: 'var(--border-hard)' }}
                    title="Remove target"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>

                {/* Status Payload */}
                {isItemLoading ? (
                  <div style={{ padding: '16px 0', textAlign: 'center', color: 'var(--neon-green)', fontSize: '11px' }}>
                    <span className="cursor-blink">[...] PINGING_PORTAL</span>
                  </div>
                ) : res && res.success && res.data ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {res.data.map((q, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '10px',
                          background: 'var(--bg-primary)',
                          border: '1px solid var(--border-dim)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '6px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ color: 'var(--text-primary)', fontSize: '11px', fontWeight: 700 }}>
                            {q.department || item.abbr}
                          </span>
                          {q.is_unlimited ? (
                            <span className="cyber-badge cyber-badge-cyan">[UNLIMITED]</span>
                          ) : q.available > 0 ? (
                            <span className="cyber-badge cyber-badge-green">[OPEN: {q.available} SLOTS]</span>
                          ) : (
                            <span className="cyber-badge cyber-badge-pink">[FULL / ZERO]</span>
                          )}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted)' }}>
                          <span>LIMIT: <strong style={{ color: 'var(--text-primary)' }}>{q.quota}</strong></span>
                          <span>ENROLLED: <strong style={{ color: 'var(--text-primary)' }}>{q.current}</strong></span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div
                    style={{
                      padding: '10px',
                      background: 'rgba(255, 0, 85, 0.06)',
                      border: '1px solid var(--neon-pink)',
                      color: 'var(--neon-pink)',
                      fontSize: '11px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700 }}>
                      <AlertTriangle size={13} />
                      <span>{res?.error || 'RADAR_PORTAL_TIMEOUT'}</span>
                    </div>
                    <div style={{ fontSize: '10px', marginTop: '2px', color: 'var(--text-secondary)' }}>
                      {res?.message || 'Failed to resolve capacity.'}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
