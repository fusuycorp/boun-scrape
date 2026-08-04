import React, { useState, useEffect, useRef } from 'react';
import {
  Activity,
  Plus,
  Trash2,
  RefreshCw,
  Clock,
  CheckCircle,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Layers,
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

  // Save watchlist
  useEffect(() => {
    try {
      localStorage.setItem('quota_watchlist', JSON.stringify(watchlist));
    } catch {
      // Ignore
    }
  }, [watchlist]);

  // Load available terms
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

  // Check quota for a single section
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
          [key]: { success: false, error: err.message || 'Check failed' },
        }));
      }
    } finally {
      if (isMountedRef.current) {
        setLoadingMap((prev) => ({ ...prev, [key]: false }));
      }
    }
  };

  // Poll all sections
  const pollAllQuotas = async () => {
    if (watchlist.length === 0) return;
    await Promise.all(watchlist.map((item) => fetchSingleQuota(item)));
  };

  // 10s Interval Poller
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
      showToast('Items already exist in watchlist', 'info');
      return;
    }

    setWatchlist((prev) => [...prev, ...newItems]);
    showToast(`Added ${newItems.length} section(s) to watchlist`, 'success');
  };

  const handleRemove = (key) => {
    setWatchlist((prev) =>
      prev.filter((w) => `${w.abbr}_${w.code}_${w.section}_${w.term}` !== key)
    );
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Real-Time Quota Watchlist
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Monitor live BOUN registration section capacity and enrollment limits with 10s auto polling.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setPollingActive((p) => !p)}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold border transition-colors ${
              pollingActive
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                : 'bg-slate-800 text-slate-400 border-white/10'
            }`}
          >
            <Clock className={`w-4 h-4 ${pollingActive ? 'animate-spin' : ''}`} />
            <span>{pollingActive ? `Auto Polling (${countdown}s)` : 'Polling Paused'}</span>
          </button>

          <button
            onClick={pollAllQuotas}
            disabled={watchlist.length === 0}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold shadow-md transition-colors disabled:opacity-40"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Now</span>
          </button>
        </div>
      </div>

      {/* Watchlist Generator Form */}
      <form onSubmit={handleAddWatchlist} className="p-6 rounded-2xl glass-panel border border-white/10 space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Plus className="w-4 h-4 text-violet-400" />
          Add Course Sections to Watchlist
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div>
            <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">
              Dept Abbr
            </label>
            <input
              type="text"
              value={abbr}
              onChange={(e) => setAbbr(e.target.value)}
              placeholder="CMPE"
              required
              className="w-full px-3.5 py-2 rounded-xl glass-input text-white text-xs font-bold uppercase focus:outline-none focus:ring-2 focus:ring-violet-500/50"
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">
              Course Code
            </label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="150"
              required
              className="w-full px-3.5 py-2 rounded-xl glass-input text-white text-xs font-bold focus:outline-none focus:ring-2 focus:ring-violet-500/50"
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">
              Section Range
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="1"
                max="30"
                value={sectionStart}
                onChange={(e) => setSectionStart(e.target.value)}
                className="w-full px-3 py-2 rounded-xl glass-input text-white text-xs text-center font-bold focus:outline-none focus:ring-2 focus:ring-violet-500/50"
              />
              <span className="text-slate-500 text-xs font-bold">to</span>
              <input
                type="number"
                min="1"
                max="30"
                value={sectionEnd}
                onChange={(e) => setSectionEnd(e.target.value)}
                className="w-full px-3 py-2 rounded-xl glass-input text-white text-xs text-center font-bold focus:outline-none focus:ring-2 focus:ring-violet-500/50"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">
              Semester
            </label>
            <select
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              required
              className="w-full px-3 py-2 rounded-xl glass-select text-white text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-violet-500/50"
            >
              {termsList.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end">
            <button
              type="submit"
              className="w-full py-2 px-4 rounded-xl bg-gradient-to-r from-violet-600 to-pink-600 hover:from-violet-500 hover:to-pink-500 text-white font-bold text-xs shadow-lg transition-all active:scale-95 flex items-center justify-center gap-2"
            >
              <Plus className="w-4 h-4" />
              <span>Track Sections</span>
            </button>
          </div>
        </div>
      </form>

      {/* Watchlist Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {watchlist.length === 0 ? (
          <div className="lg:col-span-3 p-12 text-center text-slate-500 glass-panel rounded-2xl border border-white/10 space-y-2">
            <Activity className="w-10 h-10 mx-auto text-slate-600" />
            <p className="text-sm font-bold text-white">Watchlist is Empty</p>
            <p className="text-xs text-slate-500">
              Use the section range form above to start tracking real-time course capacity.
            </p>
          </div>
        ) : (
          watchlist.map((item) => {
            const key = `${item.abbr}_${item.code}_${item.section}_${item.term}`;
            const res = quotaData[key];
            const isItemLoading = loadingMap[key];

            return (
              <div
                key={key}
                className="rounded-2xl glass-panel p-5 border border-white/10 space-y-4 shadow-lg hover:border-white/20 transition-colors"
              >
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-300 text-[10px] font-extrabold border border-violet-500/30">
                        {item.abbr}
                      </span>
                      <span className="text-[10px] text-slate-400 font-semibold">{item.term}</span>
                    </div>
                    <h3 className="text-lg font-black text-white">
                      {item.abbr} {item.code} - Sec {item.section}
                    </h3>
                  </div>

                  <button
                    onClick={() => handleRemove(key)}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                    title="Remove from Watchlist"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                {/* Status Payload */}
                {isItemLoading ? (
                  <div className="py-6 text-center text-slate-400 flex items-center justify-center gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-violet-400" />
                    <span className="text-xs">Querying BOUN portal...</span>
                  </div>
                ) : res && res.success && res.data ? (
                  <div className="space-y-3">
                    {res.data.map((q, idx) => (
                      <div
                        key={idx}
                        className="p-3.5 rounded-xl bg-slate-900/80 border border-white/5 space-y-2"
                      >
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-bold text-slate-300">{q.department || item.abbr}</span>
                          {q.is_unlimited ? (
                            <span className="px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-400 text-[10px] font-bold border border-sky-500/30">
                              Unlimited
                            </span>
                          ) : q.available > 0 ? (
                            <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-bold border border-emerald-500/30">
                              {q.available} Open Slot(s)
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 text-[10px] font-bold border border-rose-500/30">
                              Full / Closed
                            </span>
                          )}
                        </div>

                        <div className="grid grid-cols-2 gap-2 pt-1 text-[11px] text-slate-400">
                          <div>
                            Quota Limit: <strong className="text-white">{q.quota}</strong>
                          </div>
                          <div>
                            Enrolled: <strong className="text-white">{q.current}</strong>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium space-y-1">
                    <div className="flex items-center gap-2 font-bold text-amber-400">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span>{res?.error || 'Portal Error'}</span>
                    </div>
                    <p className="text-[11px] text-amber-200/80">
                      {res?.message || 'Failed to fetch section capacity.'}
                    </p>
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
