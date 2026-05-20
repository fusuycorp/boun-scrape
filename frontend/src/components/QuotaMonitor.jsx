import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Plus,
  Trash2,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  Layers,
  Sparkles,
  Info,
  Inbox,
} from 'lucide-react';
import ConfirmDialog from './ConfirmDialog';
import { useToast } from '../hooks/useToast';

export default function QuotaMonitor({ token }) {
  const toast = useToast();

  const [abbr, setAbbr] = useState('');
  const [code, setCode] = useState('');
  const [sectionStart, setSectionStart] = useState('1');
  const [sectionEnd, setSectionEnd] = useState('');

  const [watchlist, setWatchlist] = useState(() => {
    const saved = localStorage.getItem('quota_watchlist');
    return saved ? JSON.parse(saved) : [];
  });

  const [quotaData, setQuotaData] = useState({});
  const [loadingMap, setLoadingMap] = useState({});
  const [errorMap, setErrorMap] = useState({});
  const [lastUpdated, setLastUpdated] = useState(null);

  const [removeTarget, setRemoveTarget] = useState(null);

  const getCalculatedSemester = () => {
    let year = new Date().getFullYear() - 1;
    const month = new Date().getMonth() + 1;
    let semester;
    if (month >= 9) { semester = 1; year++; }
    else if (month <= 3) { semester = 2; }
    else { semester = 3; }
    return `${year}/${year + 1}-${semester}`;
  };

  const [term, setTerm] = useState(getCalculatedSemester());
  const [termsList, setTermsList] = useState([]);

  const [autoRefresh, setAutoRefresh] = useState(false);
  const [countdown, setCountdown] = useState(10);

  const countdownTimer = useRef(null);

  useEffect(() => {
    const fetchTerms = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const res = await fetch('/api/terms', { headers });
        if (res.ok) setTermsList(await res.json());
      } catch (err) {
        console.error(err);
      }
    };
    fetchTerms();
  }, [token]);

  useEffect(() => {
    localStorage.setItem('quota_watchlist', JSON.stringify(watchlist));
  }, [watchlist]);

  const fetchQuota = useCallback(async (item) => {
    const courseId = `${item.abbr}${item.code}-${item.section}`;
    setLoadingMap((prev) => ({ ...prev, [courseId]: true }));
    setErrorMap((prev) => ({ ...prev, [courseId]: '' }));

    try {
      const headers = { Authorization: `Bearer ${token}` };
      const params = new URLSearchParams({
        abbr: item.abbr,
        code: item.code,
        section: item.section,
        donem: term,
      });
      const res = await fetch(`/api/quota/check?${params.toString()}`, { headers });
      if (!res.ok) throw new Error('Server connection error.');
      const data = await res.json();
      if (!data.success) {
        setErrorMap((prev) => ({ ...prev, [courseId]: data.message || 'Error loading quotas.' }));
      } else {
        setQuotaData((prev) => ({ ...prev, [courseId]: data.data }));
      }
    } catch (err) {
      setErrorMap((prev) => ({ ...prev, [courseId]: 'Failed to connect to backend.' }));
    } finally {
      setLoadingMap((prev) => ({ ...prev, [courseId]: false }));
    }
  }, [term, token]);

  const refreshAll = useCallback(() => {
    watchlist.forEach((item) => fetchQuota(item));
    setLastUpdated(new Date());
  }, [watchlist, fetchQuota]);

  useEffect(() => {
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [watchlist.length, term]);

  useEffect(() => {
    if (autoRefresh) {
      countdownTimer.current = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            refreshAll();
            return 10;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      clearInterval(countdownTimer.current);
      setCountdown(10);
    }
    return () => clearInterval(countdownTimer.current);
  }, [autoRefresh, refreshAll]);

  const handleAddCourse = (e) => {
    e.preventDefault();
    if (!abbr || !code || !sectionStart) return;

    const itemsToAdd = [];
    const formattedAbbr = abbr.trim().toUpperCase();
    const formattedCode = code.trim().toUpperCase();
    const startSec = parseInt(sectionStart);
    const endSec = sectionEnd ? parseInt(sectionEnd) : startSec;

    if (isNaN(startSec) || (sectionEnd && isNaN(endSec))) {
      toast.error('Section inputs must be numeric.');
      return;
    }
    if (endSec < startSec) {
      toast.error('Section End must be greater than or equal to Section Start.');
      return;
    }

    let duplicates = 0;
    for (let s = startSec; s <= endSec; s++) {
      const formattedSec = s < 10 ? `0${s}` : `${s}`;
      const courseId = `${formattedAbbr}${formattedCode}-${formattedSec}`;
      const exists = watchlist.some((item) => `${item.abbr}${item.code}-${item.section}` === courseId);
      if (!exists) {
        itemsToAdd.push({ abbr: formattedAbbr, code: formattedCode, section: formattedSec });
      } else {
        duplicates++;
      }
    }

    if (itemsToAdd.length > 0) {
      setWatchlist((prev) => [...prev, ...itemsToAdd]);
      toast.success(`Added ${itemsToAdd.length} course${itemsToAdd.length === 1 ? '' : 's'} to watchlist${duplicates ? ` (${duplicates} already tracked)` : ''}.`);
      setAbbr('');
      setCode('');
      setSectionStart('1');
      setSectionEnd('');
    } else if (duplicates > 0) {
      toast.info('All requested sections are already in the watchlist.');
    }
  };

  const confirmDelete = (courseId) => {
    setWatchlist((prev) => prev.filter((item) => `${item.abbr}${item.code}-${item.section}` !== courseId));
    setQuotaData((prev) => {
      const copy = { ...prev };
      delete copy[courseId];
      return copy;
    });
    toast.info('Course removed from watchlist.');
    setRemoveTarget(null);
  };

  const getAggregateMetrics = () => {
    let emptyCount = 0;
    let unlimitedCount = 0;
    let consentCount = 0;
    Object.keys(quotaData).forEach((key) => {
      const rows = quotaData[key] || [];
      if (rows.length > 0) {
        const primary = rows[0];
        if (primary.is_consent) consentCount++;
        else if (primary.is_unlimited) unlimitedCount++;
        else if (primary.available > 0) emptyCount++;
      }
    });
    return { emptyCount, unlimitedCount, consentCount };
  };

  const { emptyCount, unlimitedCount, consentCount } = getAggregateMetrics();

  const formatLastUpdated = (d) => {
    if (!d) return 'Never';
    const diff = Math.floor((Date.now() - d.getTime()) / 1000);
    if (diff < 5) return 'just now';
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return d.toLocaleTimeString();
  };

  return (
    <div className="flex-1 p-8 overflow-y-auto space-y-8 animate-fade-in relative">
      <div className="bg-glow-pink bottom-[10%] left-[10%]" aria-hidden="true" />

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-gradient tracking-tight">Real-time Quota Monitor</h1>
          <p className="text-[hsl(var(--text-secondary))] text-sm mt-1">Track empty quotas, consent requests, and open slots with automatic refreshes</p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex flex-col gap-0.5">
            <label htmlFor="quota-term" className="text-[9px] font-bold text-[hsl(var(--text-muted))] uppercase tracking-wider">Tracking Term</label>
            <select id="quota-term" value={term} onChange={(e) => setTerm(e.target.value)} className="glass-select text-xs py-2 px-3 min-w-[140px]">
              <option value={getCalculatedSemester()}>Calculated Current</option>
              {termsList.map((t) => (<option key={t} value={t}>{t}</option>))}
            </select>
          </div>

          <div className="flex flex-col gap-0.5">
            <span className="text-[9px] font-bold text-[hsl(var(--text-muted))] uppercase tracking-wider">Last Updated</span>
            <span className="text-xs text-[hsl(var(--text-secondary))] font-medium" aria-live="polite">
              {formatLastUpdated(lastUpdated)}
            </span>
          </div>

          <button onClick={refreshAll} className="btn-secondary text-xs py-2.5 px-3 self-end flex items-center gap-1.5">
            <RefreshCw size={14} aria-hidden="true" />
            Refresh All
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-6">
        <div className="glass-panel p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-[hsl(var(--text-secondary))] uppercase mb-0.5">Tracked Courses</p>
            <h3 className="text-2xl font-bold font-heading text-[hsl(var(--text-primary))]">{watchlist.length}</h3>
          </div>
          <div className="p-3 bg-[hsla(var(--glass-border))] rounded-xl text-[hsl(var(--text-secondary))]" aria-hidden="true">
            <Layers size={20} />
          </div>
        </div>

        <div className="glass-panel p-5 flex items-center justify-between border-[hsla(var(--color-success)/0.2)]">
          <div>
            <p className="text-xs font-semibold text-[hsl(var(--text-secondary))] uppercase mb-0.5">Open Quotas</p>
            <h3 className="text-2xl font-bold font-heading text-[hsl(var(--color-success))]">{emptyCount}</h3>
          </div>
          <div className="p-3 bg-[hsla(var(--color-success)/0.1)] rounded-xl text-[hsl(var(--color-success))]" aria-hidden="true">
            <CheckCircle2 size={20} />
          </div>
        </div>

        <div className="glass-panel p-5 flex items-center justify-between border-[hsla(var(--color-info)/0.2)]">
          <div>
            <p className="text-xs font-semibold text-[hsl(var(--text-secondary))] uppercase mb-0.5">Unlimited Slots</p>
            <h3 className="text-2xl font-bold font-heading text-[hsl(var(--color-info))]">{unlimitedCount}</h3>
          </div>
          <div className="p-3 bg-[hsla(var(--color-info)/0.1)] rounded-xl text-[hsl(var(--color-info))]" aria-hidden="true">
            <Sparkles size={20} />
          </div>
        </div>

        <div className="glass-panel p-5 flex items-center justify-between border-[hsla(var(--color-warning)/0.2)]">
          <div>
            <p className="text-xs font-semibold text-[hsl(var(--text-secondary))] uppercase mb-0.5">Needs Consent</p>
            <h3 className="text-2xl font-bold font-heading text-[hsl(var(--color-warning))]">{consentCount}</h3>
          </div>
          <div className="p-3 bg-[hsla(var(--color-warning)/0.1)] rounded-xl text-[hsl(var(--color-warning))]" aria-hidden="true">
            <Info size={20} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 z-10 relative">
        <aside className="xl:col-span-1 space-y-6" aria-label="Watchlist controls">
          <div className="glass-panel p-6 space-y-5">
            <h2 className="text-base font-bold">Add Tracked Course</h2>
            <p className="text-xs text-[hsl(var(--text-secondary))] mb-4">Input course parameters below. You can track a single section or an interval range of sections simultaneously.</p>

            <form onSubmit={handleAddCourse} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="quota-abbr" className="text-[10px] font-bold text-[hsl(var(--text-secondary))] uppercase tracking-wider">Abbreviation</label>
                  <input id="quota-abbr" type="text" placeholder="e.g. CMPE" value={abbr} onChange={(e) => setAbbr(e.target.value)} className="glass-input text-xs py-2.5" required />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="quota-code" className="text-[10px] font-bold text-[hsl(var(--text-secondary))] uppercase tracking-wider">Course Code</label>
                  <input id="quota-code" type="text" placeholder="e.g. 150" value={code} onChange={(e) => setCode(e.target.value)} className="glass-input text-xs py-2.5" required />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="quota-sec-start" className="text-[10px] font-bold text-[hsl(var(--text-secondary))] uppercase tracking-wider">Section Start</label>
                  <input id="quota-sec-start" type="number" min="1" value={sectionStart} onChange={(e) => setSectionStart(e.target.value)} className="glass-input text-xs py-2.5" required />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="quota-sec-end" className="text-[10px] font-bold text-[hsl(var(--text-secondary))] uppercase tracking-wider">Section End (Opt.)</label>
                  <input id="quota-sec-end" type="number" min="1" placeholder="e.g. 5 for range" value={sectionEnd} onChange={(e) => setSectionEnd(e.target.value)} className="glass-input text-xs py-2.5" />
                </div>
              </div>

              <button type="submit" className="w-full btn-primary py-2.5 text-xs flex items-center justify-center gap-1.5 mt-2">
                <Plus size={16} aria-hidden="true" />
                Register to Watchlist
              </button>
            </form>
          </div>

          <div className="glass-panel p-6 space-y-4">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Clock size={16} className="text-[hsl(var(--accent-primary))]" aria-hidden="true" />
              Auto Refresh Configuration
            </h3>

            <label className="flex items-center justify-between p-3 rounded-xl bg-[hsla(var(--bg-tertiary)/0.4)] border border-[hsla(var(--glass-border))] cursor-pointer">
              <span className="text-xs text-[hsl(var(--text-secondary))]">Enable 10s Scheduler</span>
              <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} className="cursor-pointer h-4 w-4 rounded border-gray-300 text-[hsl(var(--accent-primary))] focus:ring-[hsl(var(--accent-primary))]" />
            </label>

            {autoRefresh && (
              <div className="text-center p-3 rounded-xl bg-[hsla(var(--accent-primary)/0.05)] border border-[hsla(var(--accent-primary)/0.15)]" aria-live="polite">
                <span className="text-xs font-semibold text-[hsl(var(--accent-primary))]">
                  Next polling cycle: <strong className="text-sm">{countdown}s</strong>
                </span>
              </div>
            )}
          </div>
        </aside>

        <section className="xl:col-span-2 space-y-6" aria-label="Watchlist">
          <div className="glass-panel p-6 flex flex-col justify-between min-h-[460px]">
            <div>
              <h2 className="text-base font-bold mb-4">Monitored Courses Watchlist</h2>

              {watchlist.length > 0 ? (
                <div className="space-y-6">
                  {watchlist.map((item) => {
                    const courseId = `${item.abbr}${item.code}-${item.section}`;
                    const rows = quotaData[courseId] || [];
                    const isLoading = loadingMap[courseId];
                    const error = errorMap[courseId];

                    let badgeClass = 'badge-info';
                    let badgeLabel = 'Checking';

                    if (error) {
                      badgeClass = 'badge-danger';
                      badgeLabel = 'Error';
                    } else if (rows.length > 0) {
                      const primary = rows[0];
                      if (primary.is_consent) { badgeClass = 'badge-warning'; badgeLabel = 'Consent'; }
                      else if (primary.is_unlimited) { badgeClass = 'badge-info'; badgeLabel = 'Unlimited'; }
                      else if (primary.available > 0) { badgeClass = 'badge-success'; badgeLabel = 'Quota Open'; }
                      else { badgeClass = 'badge-danger'; badgeLabel = 'Closed'; }
                    } else if (isLoading) {
                      badgeLabel = 'Loading...';
                    }

                    return (
                      <div key={courseId} className="p-4 rounded-xl border border-[hsla(var(--glass-border))] bg-[hsla(var(--bg-tertiary)/0.25)] flex flex-col gap-3.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className="font-extrabold text-sm tracking-wide text-gradient">
                              {item.abbr} {item.code} - Section {item.section}
                            </span>
                            <span className={`badge ${badgeClass} text-[10px]`} aria-live="polite">{badgeLabel}</span>
                          </div>

                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => fetchQuota(item)}
                              disabled={isLoading}
                              aria-label={`Refresh ${item.abbr} ${item.code} section ${item.section}`}
                              className="text-[hsl(var(--text-muted))] hover:text-[hsl(var(--text-primary))] p-1 disabled:opacity-50"
                            >
                              <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} aria-hidden="true" />
                            </button>
                            <button
                              type="button"
                              onClick={() => setRemoveTarget(courseId)}
                              aria-label={`Remove ${item.abbr} ${item.code} section ${item.section}`}
                              className="text-[hsl(var(--text-muted))] hover:text-[hsl(var(--color-danger))] p-1"
                            >
                              <Trash2 size={14} aria-hidden="true" />
                            </button>
                          </div>
                        </div>

                        {error ? (
                          <div className="text-xs text-[hsl(var(--color-danger))] flex items-center gap-1.5">
                            <AlertCircle size={14} aria-hidden="true" />
                            {error}
                          </div>
                        ) : isLoading && rows.length === 0 ? (
                          <div className="flex flex-col gap-2">
                            <span className="skeleton h-4 w-full" aria-hidden="true" />
                            <span className="skeleton h-4 w-3/4" aria-hidden="true" />
                          </div>
                        ) : rows.length > 0 ? (
                          <div className="premium-table-container">
                            <table className="premium-table text-xs">
                              <thead>
                                <tr>
                                  <th className="py-2 text-[10px]">Department</th>
                                  <th className="py-2 text-[10px]">Status</th>
                                  <th className="py-2 text-[10px]">Quota Limit</th>
                                  <th className="py-2 text-[10px]">Current Enrolled</th>
                                  <th className="py-2 text-[10px]">Remaining slots</th>
                                </tr>
                              </thead>
                              <tbody>
                                {rows.map((row, rIdx) => {
                                  const remaining = row.quota_numeric - row.current_numeric;
                                  const isOpen = !row.is_consent && !row.is_unlimited && remaining > 0;
                                  return (
                                    <tr key={rIdx} className={isOpen ? 'bg-[hsla(var(--color-success)/0.04)]' : ''}>
                                      <td className="py-2 font-semibold">{row.department}</td>
                                      <td className="py-2">
                                        <span className={row.status === 'Open' ? 'text-[hsl(var(--color-success))]' : 'text-[hsl(var(--text-muted))]'}>{row.status}</span>
                                      </td>
                                      <td className="py-2">{row.quota}</td>
                                      <td className="py-2">{row.current}</td>
                                      <td className="py-2 font-bold">
                                        {row.is_consent ? (
                                          <span className="badge badge-warning">Consent</span>
                                        ) : row.is_unlimited ? (
                                          <span className="badge badge-info">Unlimited</span>
                                        ) : remaining > 0 ? (
                                          <span className="badge badge-success">{remaining} open</span>
                                        ) : (
                                          <span className="badge badge-danger">0</span>
                                        )}
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <div className="text-xs text-[hsl(var(--text-muted))] italic">
                            No quota metrics fetched yet. Click refresh to query Boun tables.
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-[hsl(var(--text-muted))] gap-3 py-16">
                  <Inbox size={40} className="opacity-30" aria-hidden="true" />
                  <p className="text-xs font-medium">Your quota watchlist is empty.</p>
                  <span className="text-[10px] text-center max-w-sm">
                    Register academic courses (abbr, code, section) in the left panel to begin real-time slots tracking.
                  </span>
                </div>
              )}
            </div>
          </div>
        </section>
      </div>

      <ConfirmDialog
        open={!!removeTarget}
        title="Remove course from watchlist?"
        description={removeTarget ? `${removeTarget} will stop being tracked. You can re-add it anytime.` : null}
        confirmLabel="Remove"
        destructive
        onConfirm={() => confirmDelete(removeTarget)}
        onCancel={() => setRemoveTarget(null)}
      />
    </div>
  );
}

