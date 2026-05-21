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
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import ConfirmDialog from './ConfirmDialog';
import EmptyState from './EmptyState';
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
      toast.success(`Added ${itemsToAdd.length} courses to watchlist.`);
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
    toast.info('Course removed.');
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
    <div className="flex-1 p-4 sm:p-8 overflow-y-auto space-y-8 animate-fade-in relative">
      <div className="bg-glow-pink bottom-[10%] left-[10%]" aria-hidden="true" />

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gradient tracking-tight">Quota Monitor</h1>
          <p className="text-[hsl(var(--text-secondary))] text-sm mt-1">Track course slots with automatic refreshes</p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex flex-col gap-0.5">
            <label htmlFor="quota-term" className="text-[9px] font-bold text-[hsl(var(--text-muted))] uppercase tracking-wider">Tracking Term</label>
            <select id="quota-term" value={term} onChange={(e) => setTerm(e.target.value)} className="glass-select text-xs py-2 px-3 min-w-[140px]">
              <option value={getCalculatedSemester()}>Current (Auto)</option>
              {termsList.map((t) => (<option key={t} value={t}>{t}</option>))}
            </select>
          </div>

          <button onClick={refreshAll} className="btn-secondary text-xs py-2.5 px-3 self-end flex items-center gap-1.5">
            <RefreshCw size={14} aria-hidden="true" />
            Sync All
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6">
        <StatItem label="Tracked" value={watchlist.length} icon={Layers} color="var(--text-secondary)" />
        <StatItem label="Open" value={emptyCount} icon={CheckCircle2} color="var(--color-success)" />
        <StatItem label="Unlimited" value={unlimitedCount} icon={Sparkles} color="var(--color-info)" />
        <StatItem label="Consent" value={consentCount} icon={Info} color="var(--color-warning)" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 z-10 relative">
        <aside className="xl:col-span-1 space-y-6">
          <div className="glass-panel p-6 space-y-5">
            <h2 className="text-base font-bold">Add Tracked Course</h2>
            <form onSubmit={handleAddCourse} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="quota-abbr" className="text-[10px] font-bold text-[hsl(var(--text-secondary))] uppercase">Abbr</label>
                  <input id="quota-abbr" type="text" placeholder="CMPE" value={abbr} onChange={(e) => setAbbr(e.target.value)} className="glass-input text-xs py-2.5" required />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="quota-code" className="text-[10px] font-bold text-[hsl(var(--text-secondary))] uppercase">Code</label>
                  <input id="quota-code" type="text" placeholder="150" value={code} onChange={(e) => setCode(e.target.value)} className="glass-input text-xs py-2.5" required />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="quota-sec-start" className="text-[10px] font-bold text-[hsl(var(--text-secondary))] uppercase">Start Sec</label>
                  <input id="quota-sec-start" type="number" min="1" value={sectionStart} onChange={(e) => setSectionStart(e.target.value)} className="glass-input text-xs py-2.5" required />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="quota-sec-end" className="text-[10px] font-bold text-[hsl(var(--text-secondary))] uppercase">End (Opt)</label>
                  <input id="quota-sec-end" type="number" min="1" placeholder="Optional" value={sectionEnd} onChange={(e) => setSectionEnd(e.target.value)} className="glass-input text-xs py-2.5" />
                </div>
              </div>
              <button type="submit" className="w-full btn-primary py-2.5 text-xs flex items-center justify-center gap-1.5">
                <Plus size={16} aria-hidden="true" />
                Add to Watchlist
              </button>
            </form>
          </div>

          <div className="glass-panel p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Clock size={16} className="text-[hsl(var(--accent-primary))]" aria-hidden="true" />
                Auto Refresh
              </h3>
              <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} className="cursor-pointer h-4 w-4 rounded border-gray-300 text-[hsl(var(--accent-primary))] focus:ring-[hsl(var(--accent-primary))]" />
            </div>
            {autoRefresh && (
              <div className="text-center p-3 rounded-xl bg-[hsla(var(--accent-primary)/0.05)] border border-[hsla(var(--accent-primary)/0.15)] animate-fade-in">
                <span className="text-xs font-semibold text-[hsl(var(--accent-primary))]">
                  Next update in: <strong className="text-sm">{countdown}s</strong>
                </span>
              </div>
            )}
            <div className="text-[10px] text-[hsl(var(--text-muted))] flex justify-between">
              <span>Sync Status</span>
              <span aria-live="polite">{formatLastUpdated(lastUpdated)}</span>
            </div>
          </div>
        </aside>

        <section className="xl:col-span-2 space-y-6" aria-label="Watchlist">
          <div className="glass-panel p-4 sm:p-6 min-h-[460px]">
            <h2 className="text-base font-bold mb-4">Course Watchlist</h2>

            {watchlist.length > 0 ? (
              <div className="space-y-4">
                {watchlist.map((item) => {
                  const courseId = `${item.abbr}${item.code}-${item.section}`;
                  return (
                    <WatchlistItem 
                      key={courseId} 
                      item={item} 
                      data={quotaData[courseId]} 
                      loading={loadingMap[courseId]} 
                      error={errorMap[courseId]} 
                      onRefresh={() => fetchQuota(item)} 
                      onRemove={() => setRemoveTarget(courseId)} 
                    />
                  );
                })}
              </div>
            ) : (
              <EmptyState 
                title="Watchlist Empty" 
                description="Start tracking course quotas by adding department abbreviations and course codes in the panel on the left."
                icon={Inbox}
              />
            )}
          </div>
        </section>
      </div>

      <ConfirmDialog
        open={!!removeTarget}
        title="Remove Course?"
        description={removeTarget ? `Are you sure you want to stop tracking ${removeTarget}?` : null}
        confirmLabel="Remove"
        destructive
        onConfirm={() => confirmDelete(removeTarget)}
        onCancel={() => setRemoveTarget(null)}
      />
    </div>
  );
}

function StatItem({ label, value, icon: Icon, color }) {
  return (
    <div className="glass-panel p-4 sm:p-5 flex items-center justify-between border-transparent" style={{ borderColor: `hsla(${color} / 0.15)` }}>
      <div className="min-w-0">
        <p className="text-[10px] font-bold text-[hsl(var(--text-secondary))] uppercase mb-1 truncate">{label}</p>
        <h3 className="text-xl sm:text-2xl font-bold font-heading" style={{ color: `hsl(${color})` }}>{value}</h3>
      </div>
      <div className="hidden sm:flex p-3 bg-[hsla(var(--bg-tertiary)/0.5)] rounded-xl" style={{ color: `hsl(${color})` }}>
        <Icon size={20} />
      </div>
    </div>
  );
}

function WatchlistItem({ item, data, loading, error, onRefresh, onRemove }) {
  const [expanded, setExpanded] = useState(false);
  
  let statusBadge = { label: 'Idle', class: 'badge-info' };
  if (loading) statusBadge = { label: 'Syncing...', class: 'badge-info' };
  else if (error) statusBadge = { label: 'Error', class: 'badge-danger' };
  else if (data && data.length > 0) {
    const primary = data[0];
    if (primary.is_consent) statusBadge = { label: 'Consent', class: 'badge-warning' };
    else if (primary.is_unlimited) statusBadge = { label: 'Unlimited', class: 'badge-info' };
    else if (primary.available > 0) statusBadge = { label: 'Open', class: 'badge-success' };
    else statusBadge = { label: 'Closed', class: 'badge-danger' };
  }

  return (
    <div className={`rounded-xl border border-[hsla(var(--glass-border))] bg-[hsla(var(--bg-tertiary)/0.25)] transition-all ${expanded ? 'ring-1 ring-[hsl(var(--accent-primary))]' : ''}`}>
      <div className="p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-extrabold text-sm tracking-wide text-gradient">
              {item.abbr} {item.code} - {item.section}
            </span>
            <span className={`badge ${statusBadge.class} text-[10px]`}>{statusBadge.label}</span>
          </div>

          <div className="flex items-center gap-2">
            <button onClick={onRefresh} disabled={loading} className="text-[hsl(var(--text-muted))] hover:text-[hsl(var(--text-primary))] p-1">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
            <button onClick={() => setExpanded(!expanded)} className="text-[hsl(var(--text-muted))] hover:text-[hsl(var(--text-primary))] p-1">
              {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            <button onClick={onRemove} className="text-[hsl(var(--text-muted))] hover:text-[hsl(var(--color-danger))] p-1">
              <Trash2 size={14} />
            </button>
          </div>
        </div>

        {error ? (
          <div className="text-xs text-[hsl(var(--color-danger))] flex items-center gap-1.5 bg-[hsla(var(--color-danger)/0.05)] p-2 rounded-lg">
            <AlertCircle size={14} /> {error}
          </div>
        ) : loading && !data ? (
          <div className="flex flex-col gap-2 py-2">
            <span className="skeleton h-3 w-full" />
            <span className="skeleton h-3 w-2/3" />
          </div>
        ) : data && data.length > 0 ? (
          <div className="space-y-3">
            {/* Desktop Table */}
            <div className="hidden sm:block premium-table-container">
              <table className="premium-table text-xs">
                <thead>
                  <tr>
                    <th className="py-2 text-[10px]">Dept</th>
                    <th className="py-2 text-[10px]">Status</th>
                    <th className="py-2 text-[10px]">Limit</th>
                    <th className="py-2 text-[10px]">Current</th>
                    <th className="py-2 text-[10px]">Available</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((row, idx) => (
                    <QuotaRow key={idx} row={row} />
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile Cards (only first one unless expanded) */}
            <div className="sm:hidden space-y-2">
              {data.slice(0, expanded ? undefined : 1).map((row, idx) => (
                <QuotaMobileCard key={idx} row={row} />
              ))}
              {!expanded && data.length > 1 && (
                <button onClick={() => setExpanded(true)} className="w-full py-1 text-[10px] text-[hsl(var(--text-muted))] hover:text-[hsl(var(--text-primary))] font-bold uppercase tracking-widest">
                  + {data.length - 1} more departments
                </button>
              )}
            </div>
          </div>
        ) : (
          <p className="text-[10px] text-[hsl(var(--text-muted))] italic">No data synced yet.</p>
        )}
      </div>
    </div>
  );
}

function QuotaRow({ row }) {
  const remaining = row.quota_numeric - row.current_numeric;
  return (
    <tr className={remaining > 0 && !row.is_consent ? 'bg-[hsla(var(--color-success)/0.04)]' : ''}>
      <td className="py-2 font-semibold">{row.department}</td>
      <td className="py-2">
        <span className={row.status === 'Open' ? 'text-[hsl(var(--color-success))]' : 'text-[hsl(var(--text-muted))]'}>{row.status}</span>
      </td>
      <td className="py-2">{row.quota}</td>
      <td className="py-2">{row.current}</td>
      <td className="py-2 font-bold">
        {row.is_consent ? <span className="text-[hsl(var(--color-warning))]">Consent</span> : 
         row.is_unlimited ? <span className="text-[hsl(var(--color-info))]">Unlimited</span> : 
         remaining > 0 ? <span className="text-[hsl(var(--color-success))]">{remaining} left</span> : 
         <span className="text-[hsl(var(--color-danger))]">0</span>}
      </td>
    </tr>
  );
}

function QuotaMobileCard({ row }) {
  const remaining = row.quota_numeric - row.current_numeric;
  return (
    <div className="bg-[hsla(var(--bg-tertiary)/0.5)] p-3 rounded-lg border border-[hsla(var(--glass-border))] flex flex-col gap-2">
      <div className="flex justify-between items-center">
        <span className="text-xs font-bold text-[hsl(var(--text-primary))]">{row.department}</span>
        <span className={`text-[10px] font-bold ${row.status === 'Open' ? 'text-[hsl(var(--color-success))]' : 'text-[hsl(var(--text-muted))]'}`}>{row.status}</span>
      </div>
      <div className="flex justify-between items-center text-[11px]">
        <span className="text-[hsl(var(--text-muted))]">Quota: <strong className="text-[hsl(var(--text-secondary))]">{row.current} / {row.quota}</strong></span>
        <span className="font-bold">
          {row.is_consent ? <span className="badge badge-warning text-[9px]">Consent</span> : 
           row.is_unlimited ? <span className="badge badge-info text-[9px]">Unlimited</span> : 
           remaining > 0 ? <span className="badge badge-success text-[9px]">{remaining} Slots</span> : 
           <span className="badge badge-danger text-[9px]">Full</span>}
        </span>
      </div>
    </div>
  );
}
