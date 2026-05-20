import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Square,
  Trash2,
  Terminal as ConsoleIcon,
} from 'lucide-react';
import ConfirmDialog from './ConfirmDialog';
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
  const [confirm, setConfirm] = useState(null); // { type: 'start'|'stop'|'clear', phaseId }

  const terminalEndRef = useRef(null);
  const logInterval = useRef(null);
  const statusInterval = useRef(null);

  const fetchStatus = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch('/api/scrape/status', { headers });
      if (res.ok) setStatus(await res.json());
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
        setLogs(data.logs.join(''));
      }
    } catch (err) {
      console.error('Error fetching logs:', err);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchLogs();
    statusInterval.current = setInterval(fetchStatus, 2000);
    logInterval.current = setInterval(fetchLogs, 1500);
    return () => {
      clearInterval(statusInterval.current);
      clearInterval(logInterval.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const runStart = async () => {
    setActionLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
      const res = await fetch('/api/scrape/start', {
        method: 'POST',
        headers,
        body: JSON.stringify({ phase: activeStep }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to trigger scraping task.');
      }
      toast.success(`Stage started: ${PHASES.find((p) => p.id === activeStep)?.name || activeStep}`);
      fetchStatus();
      fetchLogs();
    } catch (err) {
      toast.error(err.message || 'Failed to start scraper.');
    } finally {
      setActionLoading(false);
      setConfirm(null);
    }
  };

  const runStop = async () => {
    setActionLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch('/api/scrape/stop', { method: 'POST', headers });
      if (!res.ok) throw new Error('Failed to cancel scraping task.');
      toast.info('Scraper termination signal sent.');
      fetchStatus();
    } catch (err) {
      toast.error(err.message || 'Failed to cancel scraping task.');
    } finally {
      setActionLoading(false);
      setConfirm(null);
    }
  };

  const runClearLogs = async () => {
    setActionLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await fetch('/api/scrape/logs?clear=true', { headers });
      setLogs('');
      toast.success('Console history cleared.');
    } catch (err) {
      toast.error('Failed to clear logs.');
    } finally {
      setActionLoading(false);
      setConfirm(null);
    }
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
    <div className="flex-1 p-8 overflow-y-auto space-y-8 animate-fade-in relative">
      <div className="bg-glow-pink top-[10%] left-[5%]" aria-hidden="true" />

      <div>
        <h1 className="text-3xl font-extrabold text-gradient tracking-tight">Scraper Control Room</h1>
        <p className="text-[hsl(var(--text-secondary))] text-sm mt-1">Configure parameters and run scraping routines as async background threads</p>
      </div>

      {/* SR live region for state changes */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {isRunning
          ? `Scraper running ${runningPhase || ''} at ${status.progress.percent}%`
          : `Scraper ${status.status}`}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 z-10 relative">
        <div className="xl:col-span-1 space-y-6 flex flex-col justify-between">
          <div className="glass-panel p-6 space-y-5">
            <h2 className="text-lg font-bold">Scraping Pipeline Steps</h2>

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
                          Running
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] text-[hsl(var(--text-muted))] leading-relaxed">{p.desc}</span>
                  </button>
                );
              })}
            </div>

            <div className="pt-4 border-t border-[hsla(var(--glass-border))] flex gap-3">
              {isRunning ? (
                <button
                  type="button"
                  onClick={() => setConfirm({ type: 'stop' })}
                  disabled={actionLoading}
                  className="w-full btn-secondary text-sm flex items-center justify-center gap-2 py-3 text-[hsl(var(--color-danger))] border-[hsla(var(--color-danger)/0.2)] hover:bg-[hsla(var(--color-danger)/0.1)] hover:border-[hsla(var(--color-danger)/0.3)]"
                >
                  {actionLoading ? (
                    <Spinner />
                  ) : (
                    <Square size={16} fill="currentColor" aria-hidden="true" />
                  )}
                  Terminate Scraper
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleStartClick}
                  disabled={actionLoading}
                  className="w-full btn-primary text-sm flex items-center justify-center gap-2 py-3"
                >
                  {actionLoading ? (
                    <Spinner />
                  ) : (
                    <Play size={16} fill="currentColor" aria-hidden="true" />
                  )}
                  Execute Stage
                </button>
              )}
            </div>
          </div>

          {isRunning && (
            <div className="glass-panel p-6 bg-gradient-to-tr from-[hsla(var(--accent-primary)/0.05)] to-[hsla(var(--accent-secondary)/0.02)] border-[hsla(var(--accent-primary)/0.2)] flex flex-col gap-4">
              <div>
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <span className="pulse-indicator pulse-purple w-2 h-2" aria-hidden="true" />
                  Active Background Job
                </h3>
                <p className="text-xs text-[hsl(var(--text-muted))] mt-1">Currently compiling data streams</p>
              </div>

              <div className="space-y-2" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(status.progress.percent || 0)}>
                <div className="flex justify-between text-xs font-semibold">
                  <span className="text-[hsl(var(--text-secondary))]">
                    Progress: {status.progress.current} / {status.progress.total > 0 ? status.progress.total : '?'}
                  </span>
                  <span className="text-[hsl(var(--accent-primary))]">{status.progress.percent}%</span>
                </div>
                <div className="w-full h-2.5 bg-[hsl(var(--bg-tertiary))] rounded-full overflow-hidden border border-[hsla(var(--glass-border))]">
                  <div
                    className="h-full bg-gradient-to-r from-[hsl(var(--accent-primary))] to-[hsl(var(--accent-secondary))] rounded-full transition-all duration-300"
                    style={{ width: `${status.progress.percent}%` }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="xl:col-span-2 glass-panel p-6 flex flex-col h-[580px] justify-between">
          <div className="flex items-center justify-between border-b border-[hsla(var(--glass-border))] pb-4 mb-4">
            <div className="flex items-center gap-2.5">
              <div className="flex gap-1.5" aria-hidden="true">
                <span className="w-3 h-3 rounded-full bg-rose-500 opacity-80" />
                <span className="w-3 h-3 rounded-full bg-amber-500 opacity-80" />
                <span className="w-3 h-3 rounded-full bg-emerald-500 opacity-80" />
              </div>
              <div className="h-4 w-px bg-[hsl(var(--border-color))]" aria-hidden="true" />
              <span className="text-xs font-medium text-[hsl(var(--text-secondary))] flex items-center gap-2">
                <ConsoleIcon size={14} className="text-[hsl(var(--text-muted))]" aria-hidden="true" />
                stdout_logs.log
              </span>
            </div>

            <button
              type="button"
              onClick={() => setConfirm({ type: 'clear' })}
              disabled={actionLoading}
              className="text-xs text-[hsl(var(--text-muted))] hover:text-[hsl(var(--color-danger))] flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-transparent hover:border-[hsla(var(--color-danger)/0.15)] hover:bg-[hsla(var(--color-danger)/0.05)] transition-all"
            >
              <Trash2 size={13} aria-hidden="true" />
              Clear Console
            </button>
          </div>

          <div className="flex-1 bg-[hsl(var(--bg-tertiary))] border border-[hsla(var(--glass-border))] rounded-xl p-4 overflow-y-auto font-mono text-[13px] leading-relaxed text-emerald-400 select-all shadow-inner" aria-label="Scraper console output" role="log">
            {logs ? (
              <pre className="whitespace-pre-wrap font-mono">
                {logs}
                <div ref={terminalEndRef} />
              </pre>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-[hsl(var(--text-muted))] font-sans gap-2">
                <ConsoleIcon size={32} className="opacity-30" aria-hidden="true" />
                <p className="text-xs">No active terminal data. Triggers logs by starting a phase.</p>
              </div>
            )}
          </div>
        </div>
      </div>

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

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  );
}
