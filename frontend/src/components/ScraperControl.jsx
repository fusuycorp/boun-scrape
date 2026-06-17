import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Play,
  Square,
  Trash2,
  Terminal as ConsoleIcon,
  Clock,
  RefreshCw,
  Inbox,
  Copy,
} from 'lucide-react';
import ConfirmDialog from './ConfirmDialog';
import EmptyState from './EmptyState';
import { useToast } from '../hooks/useToast';

const PHASES = [
  { id: 'phase1', name: 'Stage 1: Term Discovery', desc: 'Queries responses index and registers all historical semesters/academic terms.', script: 'scraper.py' },
  { id: 'phase2', name: 'Stage 2: Extract Departments', desc: 'Extracts the master deduplicated list of active departments across all semesters.', script: 'parse_responses.py' },
  { id: 'phase3', name: 'Stage 3: Exhaustive Scraper', desc: 'Downloads schedule HTML pages for every department across every semester. Bypasses reCAPTCHA using cookies.', script: 'scrape_all_schedules.py', destructive: true },
  { id: 'phase4', name: 'Stage 4: DB Compiler', desc: 'Parses all schedules HTML pages, normalizes times, and compiles records into SQLite tables.', script: 'parse_schedules_to_db.py', destructive: true },
];

export default function ScraperControl({ token }) {
  const toast = useToast();
  const [activeStep, setActiveStep] = useState('phase1');
  const [status, setStatus] = useState({
    phase: null,
    status: 'idle',
    progress: { total: 0, current: 0, percent: 0.0 },
  });
  const [logs, setLogs] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [forceRefresh, setForceRefresh] = useState(false);
  const [confirm, setConfirm] = useState(null); // { type: 'start'|'stop'|'clear', phaseId }

  const [terms, setTerms] = useState([]);
  const [termsLoading, setTermsLoading] = useState(true);
  const [termsError, setTermsError] = useState(null);

  const terminalEndRef = useRef(null);
  const logInterval = useRef(null);
  const statusInterval = useRef(null);
  
  const isMountedRef = useRef(true);

  // Mount tracking
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const fetchTerms = useCallback(async () => {
    try {
      if (isMountedRef.current) setTermsError(null);
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch('/api/scrape/terms', { headers });
      if (!res.ok) throw new Error('Failed to load term cache.');
      const data = await res.json();
      
      if (isMountedRef.current) {
        setTerms(data.terms || []);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setTermsError(err.message || 'Failed to load term cache.');
      }
    } finally {
      if (isMountedRef.current) {
        setTermsLoading(false);
      }
    }
  }, [token]);

  const fetchStatus = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch('/api/scrape/status', { headers });
      if (res.ok) {
        const data = await res.json();
        if (isMountedRef.current) setStatus(data);
      }
    } catch (err) {
      console.error('Error fetching scraper status:', err);
    }
  };

  const fetchLogs = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch('/api/scrape/logs?limit=500', { headers });
      if (res.ok) {
        const data = await res.json();
        if (isMountedRef.current) setLogs(data.logs.join(''));
      }
    } catch (err) {
      console.error('Error fetching logs:', err);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchLogs();
    fetchTerms();
    statusInterval.current = setInterval(fetchStatus, 2000);
    logInterval.current = setInterval(fetchLogs, 1500);
    return () => {
      clearInterval(statusInterval.current);
      clearInterval(logInterval.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const wasRunningRef = useRef(false);
  useEffect(() => {
    if (wasRunningRef.current && status.status !== 'running') {
      fetchTerms();
    }
    wasRunningRef.current = status.status === 'running';
  }, [status.status, fetchTerms]);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const runStart = async () => {
    if (isMountedRef.current) setActionLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
      const res = await fetch('/api/scrape/start', {
        method: 'POST',
        headers,
        body: JSON.stringify({ phase: activeStep, force_refresh: forceRefresh }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to trigger scraping task.');
      }
      toast.success(`Stage started: ${PHASES.find((p) => p.id === activeStep)?.name || activeStep}`);
      if (isMountedRef.current) setForceRefresh(false);
      fetchStatus();
      fetchLogs();
    } catch (err) {
      toast.error(err.message || 'Failed to start scraper.');
    } finally {
      if (isMountedRef.current) {
        setActionLoading(false);
        setConfirm(null);
      }
    }
  };

  const runStop = async () => {
    if (isMountedRef.current) setActionLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch('/api/scrape/stop', { method: 'POST', headers });
      if (!res.ok) throw new Error('Failed to cancel scraping task.');
      toast.info('Scraper termination signal sent.');
      fetchStatus();
    } catch (err) {
      toast.error(err.message || 'Failed to cancel scraping task.');
    } finally {
      if (isMountedRef.current) {
        setActionLoading(false);
        setConfirm(null);
      }
    }
  };

  const runClearLogs = async () => {
    if (isMountedRef.current) setActionLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await fetch('/api/scrape/logs?clear=true', { headers });
      if (isMountedRef.current) setLogs('');
      toast.success('Console history cleared.');
    } catch (err) {
      toast.error('Failed to clear logs.');
    } finally {
      if (isMountedRef.current) {
        setActionLoading(false);
        setConfirm(null);
      }
    }
  };

  const copyLogsToClipboard = () => {
    if (!logs) return;
    navigator.clipboard.writeText(logs);
    toast.success('Logs copied to clipboard!');
  };

  const isRunning = status.status === 'running';
  const runningPhase = status.phase;
  const activePhaseObj = PHASES.find((p) => p.id === activeStep);

  const handleStartClick = () => {
    if (activePhaseObj?.destructive) {
      setConfirm({ type: 'start' });
    } else {
      runStart();
    }
  };

  const confirmConfig = (() => {
    if (!confirm) return null;
    if (confirm.type === 'start') {
      return {
        title: `Run ${activePhaseObj?.name}?`,
        description:
          'This stage performs a heavy, long-running operation that may rewrite database tables or download many pages. Make sure no other job is in flight.',
        confirmLabel: 'Execute Stage',
        destructive: true,
        onConfirm: runStart,
      };
    }
    if (confirm.type === 'stop') {
      return {
        title: 'Terminate the running scraper?',
        description: 'In-flight downloads will be aborted. Already-saved data will not be rolled back.',
        confirmLabel: 'Terminate',
        destructive: true,
        onConfirm: runStop,
      };
    }
    if (confirm.type === 'clear') {
      return {
        title: 'Clear console history?',
        description: 'All buffered log lines will be deleted from the server. This cannot be undone.',
        confirmLabel: 'Clear Logs',
        destructive: true,
        onConfirm: runClearLogs,
      };
    }
    return null;
  })();

  return (
    <div className="flex-1 p-4 sm:p-8 overflow-y-auto space-y-8 animate-fade-in relative">
      <div className="bg-glow-pink top-[10%] left-[5%]" aria-hidden="true" />

      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-gradient tracking-tight">Scraper Control Room</h1>
        <p className="text-[hsl(var(--text-secondary))] text-sm mt-1">Configure and run scraping routines as background tasks</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 z-10 relative">
        <div className="xl:col-span-1 space-y-6 flex flex-col">
          <div className="glass-panel p-6 space-y-5">
            <h2 className="text-lg font-bold">Pipeline Steps</h2>

            <div className="flex flex-col gap-3" role="radiogroup" aria-label="Scraping stage">
              {PHASES.map((p) => {
                const isActive = activeStep === p.id;
                const isThisRunning = runningPhase === p.id;
                return (
                  <button
                    key={p.id}
                    type="button"
                    role="radio"
                    aria-checked={isActive}
                    disabled={isRunning || actionLoading}
                    onClick={() => setActiveStep(p.id)}
                    className={`w-full text-left p-4 rounded-xl border transition-all flex flex-col gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-primary))] ${
                      isActive
                        ? 'bg-[hsla(var(--accent-primary)/0.08)] border-[hsl(var(--accent-primary))] shadow-sm'
                        : 'border-[hsla(var(--glass-border))] bg-[hsla(var(--bg-tertiary)/0.3)] hover:bg-[hsla(var(--bg-tertiary)/0.6)]'
                    } ${isRunning ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm">{p.name}</span>
                      {isThisRunning && (
                        <span className="flex items-center gap-1 text-[10px] text-[hsl(var(--accent-primary))] font-bold uppercase tracking-wider">
                          <span className="pulse-indicator pulse-purple w-1.5 h-1.5" aria-hidden="true" />
                          Active
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] text-[hsl(var(--text-muted))] leading-relaxed">{p.desc}</span>
                  </button>
                );
              })}
            </div>

            {(activeStep === 'phase1' || activeStep === 'phase3') && (
              <label className="flex items-start gap-2.5 pt-4 border-t border-[hsla(var(--glass-border))] cursor-pointer select-none text-xs text-[hsl(var(--text-secondary))]">
                <input
                  type="checkbox"
                  checked={forceRefresh}
                  onChange={(e) => setForceRefresh(e.target.checked)}
                  disabled={isRunning || actionLoading}
                  className="mt-0.5 accent-[hsl(var(--accent-primary))] cursor-pointer disabled:cursor-not-allowed"
                />
                <span>
                  <strong className="text-[hsl(var(--text-primary))]">Force refresh</strong> — ignore disk cache and re-download every term.
                </span>
              </label>
            )}

            <div className="pt-4 border-t border-[hsla(var(--glass-border))] flex gap-3">
              {isRunning ? (
                <button
                  type="button"
                  onClick={() => setConfirm({ type: 'stop' })}
                  disabled={actionLoading}
                  className="w-full btn-secondary text-sm flex items-center justify-center gap-2 py-3 text-[hsl(var(--color-danger))] border-[hsla(var(--color-danger)/0.2)] hover:bg-[hsla(var(--color-danger)/0.1)]"
                >
                  <Square size={16} fill="currentColor" aria-hidden="true" />
                  Terminate
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleStartClick}
                  disabled={actionLoading}
                  className="w-full btn-primary text-sm flex items-center justify-center gap-2 py-3"
                >
                  <Play size={16} fill="currentColor" aria-hidden="true" />
                  Start Execution
                </button>
              )}
            </div>
          </div>

          {isRunning && (
            <div className="glass-panel p-6 bg-gradient-to-tr from-[hsla(var(--accent-primary)/0.05)] to-[hsla(var(--accent-secondary)/0.02)] border-[hsla(var(--accent-primary)/0.2)] flex flex-col gap-4 animate-pulse">
              <div className="flex items-center gap-2">
                <span className="pulse-indicator pulse-purple w-2 h-2" aria-hidden="true" />
                <h3 className="text-sm font-semibold">Compiling Data Streams...</h3>
              </div>

              <div className="space-y-2" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(status.progress.percent || 0)}>
                <div className="flex justify-between text-[10px] font-bold uppercase tracking-wider text-[hsl(var(--text-muted))]">
                  <span>Current: {status.progress.current} / {status.progress.total > 0 ? status.progress.total : '?'}</span>
                  <span className="text-[hsl(var(--accent-primary))]">{status.progress.percent}%</span>
                </div>
                <div className="w-full h-2 bg-[hsl(var(--bg-tertiary))] rounded-full overflow-hidden border border-[hsla(var(--glass-border))]">
                  <div
                    className="h-full bg-gradient-to-r from-[hsl(var(--accent-primary))] to-[hsl(var(--accent-secondary))] transition-all duration-300"
                    style={{ width: `${status.progress.percent}%` }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="xl:col-span-2 flex flex-col gap-6">
          <div className="glass-panel p-6 flex flex-col h-[500px]">
            <div className="flex items-center justify-between border-b border-[hsla(var(--glass-border))] pb-4 mb-4">
              <div className="flex items-center gap-2.5">
                <div className="flex gap-1.5" aria-hidden="true">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500 opacity-60" />
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500 opacity-60" />
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 opacity-60" />
                </div>
                <span className="text-xs font-bold text-[hsl(var(--text-muted))] uppercase tracking-widest ml-2">Terminal Output</span>
              </div>

              <div className="flex gap-4">
                {logs && (
                  <button
                    type="button"
                    onClick={copyLogsToClipboard}
                    className="text-[10px] font-bold uppercase tracking-wider text-[hsl(var(--text-muted))] hover:text-[hsl(var(--text-primary))] flex items-center gap-1.5"
                  >
                    <Copy size={12} />
                    Copy
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setConfirm({ type: 'clear' })}
                  disabled={actionLoading}
                  className="text-[10px] font-bold uppercase tracking-wider text-[hsl(var(--text-muted))] hover:text-[hsl(var(--color-danger))] flex items-center gap-1.5"
                >
                  <Trash2 size={12} />
                  Clear
                </button>
              </div>
            </div>

            <div className="flex-1 bg-[hsl(var(--bg-tertiary))] border border-[hsla(var(--glass-border))] rounded-xl p-4 overflow-y-auto font-mono text-[13px] leading-relaxed text-emerald-400 select-all shadow-inner" aria-label="Scraper console output" role="log">
              {logs ? (
                <pre className="whitespace-pre-wrap font-mono">
                  {logs}
                  <div ref={terminalEndRef} />
                </pre>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-[hsl(var(--text-muted))] font-sans gap-3">
                  <ConsoleIcon size={32} className="opacity-20" aria-hidden="true" />
                  <p className="text-xs font-medium">No log data buffered from server.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <section aria-labelledby="cached-terms-heading" className="glass-panel p-6 flex flex-col gap-4">
        <header className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h2 id="cached-terms-heading" className="text-sm font-bold flex items-center gap-2">
              <Clock size={16} className="text-[hsl(var(--accent-primary))]" aria-hidden="true" />
              Cached Semester Data
            </h2>
            <p className="text-[10px] text-[hsl(var(--text-muted))] uppercase tracking-wider mt-1 font-semibold">
              Term mapping status and local file counts
            </p>
          </div>
          <button
            type="button"
            onClick={fetchTerms}
            disabled={termsLoading}
            className="btn-secondary text-xs py-2 px-3 inline-flex items-center gap-1.5"
          >
            <RefreshCw size={14} className={termsLoading ? 'animate-spin-slow' : ''} />
            Refresh Cache
          </button>
        </header>

        {termsError ? (
          <div className="text-xs text-[hsl(var(--color-danger))] bg-[hsla(var(--color-danger)/0.05)] border border-[hsla(var(--color-danger)/0.2)] rounded-lg px-3 py-2">
            {termsError}
          </div>
        ) : termsLoading ? (
          <div className="flex gap-2 p-4">
             <span className="skeleton h-4 w-full animate-pulse bg-[hsla(var(--text-muted)/0.15)] rounded" />
          </div>
        ) : terms.length === 0 ? (
          <EmptyState 
            title="No Cached Terms" 
            description="Run Stage 1 to discover available semesters and academic terms from the Bogazici index."
            icon={Inbox}
          />
        ) : (
          <div className="premium-table-container max-h-80 overflow-auto">
            <table className="premium-table">
              <thead className="sticky top-0">
                <tr>
                  <th>Term</th>
                  <th>Stage 1</th>
                  <th>Stage 3</th>
                  <th className="text-right">Files</th>
                </tr>
              </thead>
              <tbody>
                {terms.map((t) => (
                  <tr key={t.term}>
                    <td className="font-mono text-xs font-bold text-[hsl(var(--accent-primary))]">{t.term}</td>
                    <td className="text-xs text-[hsl(var(--text-secondary))]">{formatTimestamp(t.phase1_at)}</td>
                    <td className="text-xs text-[hsl(var(--text-secondary))]">{formatTimestamp(t.phase3_at)}</td>
                    <td className="text-xs text-right tabular-nums font-semibold">{t.schedule_count || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <ConfirmDialog
        open={!!confirmConfig}
        title={confirmConfig?.title}
        description={confirmConfig?.description}
        confirmLabel={confirmConfig?.confirmLabel}
        destructive={confirmConfig?.destructive}
        busy={actionLoading}
        onConfirm={confirmConfig?.onConfirm}
        onCancel={() => !actionLoading && setConfirm(null)}
      />
    </div>
  );
}

function formatTimestamp(unixSeconds) {
  if (!unixSeconds) return <span className="text-[hsl(var(--text-muted))] italic">Never</span>;
  const d = new Date(unixSeconds * 1000);
  const now = Date.now();
  const diffMs = now - d.getTime();
  const diffMin = Math.round(diffMs / 60000);
  let relative;
  if (diffMin < 1) relative = 'now';
  else if (diffMin < 60) relative = `${diffMin}m ago`;
  else if (diffMin < 60 * 24) relative = `${Math.round(diffMin / 60)}h ago`;
  else relative = `${Math.round(diffMin / (60 * 24))}d ago`;
  const absolute = d.toLocaleDateString();
  return (
    <span title={d.toLocaleString()}>
      {absolute} <span className="text-[10px] text-[hsl(var(--text-muted))] font-bold uppercase ml-1">({relative})</span>
    </span>
  );
}
