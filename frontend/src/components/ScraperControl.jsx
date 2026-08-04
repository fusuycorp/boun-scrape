import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Square,
  Terminal as TerminalIcon,
  RefreshCw,
  Clock,
  Layers,
  Database,
  Trash2,
  Copy,
  Check,
  AlertTriangle,
} from 'lucide-react';
import { api } from '../api/client';
import { useMountedRef } from '../hooks/useSafeAsync';
import { useToast } from '../hooks/useToast';
import ConfirmDialog from './ConfirmDialog';

export default function ScraperControl() {
  const showToast = useToast();
  const isMountedRef = useMountedRef();
  const logTerminalRef = useRef(null);

  const [status, setStatus] = useState({ phase: null, status: 'idle', progress: null });
  const [logs, setLogs] = useState([]);
  const [terms, setTerms] = useState([]);
  const [forceRefresh, setForceRefresh] = useState(false);

  const [startingPhase, setStartingPhase] = useState(null);
  const [stopping, setStopping] = useState(false);
  const [copied, setCopied] = useState(false);
  const [confirmPhase, setConfirmPhase] = useState(null);

  const autoScrollRef = useRef(true);

  // Poll status & logs
  const pollScraper = async () => {
    try {
      const [statusRes, logsRes] = await Promise.all([
        api.getScrapeStatus().catch(() => ({ phase: null, status: 'idle', progress: null })),
        api.getScrapeLogs().catch(() => ({ logs: [] })),
      ]);

      if (isMountedRef.current) {
        setStatus(statusRes);
        if (logsRes.logs) {
          setLogs(logsRes.logs);
        }
      }
    } catch {
      // Ignore transient polling errors
    }
  };

  const fetchTerms = async () => {
    try {
      const data = await api.getScrapeTerms();
      if (isMountedRef.current && data.terms) {
        setTerms(data.terms);
      }
    } catch {
      // Ignore
    }
  };

  useEffect(() => {
    pollScraper();
    fetchTerms();

    const interval = setInterval(() => {
      pollScraper();
    }, 1500);

    return () => clearInterval(interval);
  }, []);

  // Auto-scroll terminal log window
  useEffect(() => {
    if (autoScrollRef.current && logTerminalRef.current) {
      logTerminalRef.current.scrollTop = logTerminalRef.current.scrollHeight;
    }
  }, [logs]);

  const handleStartPhase = async (phase) => {
    setConfirmPhase(null);
    setStartingPhase(phase);
    try {
      await api.startScrape(phase, forceRefresh);
      showToast(`Launched ${phase.toUpperCase()} successfully!`, 'success');
      pollScraper();
    } catch (err) {
      showToast(err.message || `Failed to launch ${phase}`, 'error');
    } finally {
      if (isMountedRef.current) setStartingPhase(null);
    }
  };

  const handleStop = async () => {
    setStopping(true);
    try {
      await api.stopScrape();
      showToast('Scraping process terminated.', 'info');
      pollScraper();
    } catch (err) {
      showToast(err.message || 'Failed to stop scraping', 'error');
    } finally {
      if (isMountedRef.current) setStopping(false);
    }
  };

  const handleClearLogs = async () => {
    try {
      await api.getScrapeLogs(true);
      setLogs([]);
      showToast('Terminal logs cleared', 'info');
    } catch (err) {
      showToast(err.message || 'Failed to clear logs', 'error');
    }
  };

  const handleCopyLogs = () => {
    const logText = logs.join('');
    navigator.clipboard.writeText(logText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const phases = [
    {
      id: 'phase1',
      title: 'Stage 1: Term Discovery',
      script: 'scraper.py',
      description: 'Posts ASP.NET ViewState form requests to discover and download semester index pages.',
      icon: Clock,
      color: 'from-sky-500/20 to-blue-500/20 border-sky-500/30 text-sky-400',
    },
    {
      id: 'phase2',
      title: 'Stage 2: Department Catalog',
      script: 'parse_responses.py',
      description: 'Extracts department links and outputs deduplicated catalog into departments_all.json.',
      icon: Layers,
      color: 'from-violet-500/20 to-purple-500/20 border-violet-500/30 text-violet-400',
    },
    {
      id: 'phase3',
      title: 'Stage 3: Schedule Crawler',
      script: 'scrape_all_schedules.py',
      description: 'Multi-threaded downloader (10 workers) fetching raw department HTML schedule files.',
      icon: TerminalIcon,
      color: 'from-pink-500/20 to-rose-500/20 border-pink-500/30 text-pink-400',
    },
    {
      id: 'phase4',
      title: 'Stage 4: SQLite Database ETL',
      script: 'parse_schedules_to_db.py',
      description: 'Parallel multi-process parser compiling HTML tables into SQLite with batch transactions.',
      icon: Database,
      color: 'from-emerald-500/20 to-teal-500/20 border-emerald-500/30 text-emerald-400',
    },
  ];

  const isRunning = status.status === 'running';

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Scraper Pipeline Controller
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Orchestrate background multi-stage crawling processes and inspect stdout log streams.
          </p>
        </div>

        {/* Global Action Controls */}
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-semibold text-slate-300 cursor-pointer select-none bg-slate-900/60 px-3 py-2 rounded-xl border border-white/10">
            <input
              type="checkbox"
              checked={forceRefresh}
              onChange={(e) => setForceRefresh(e.target.checked)}
              className="rounded bg-slate-800 border-slate-700 text-violet-600 focus:ring-violet-500/40"
            />
            <span>Force Refresh</span>
          </label>

          {isRunning && (
            <button
              onClick={handleStop}
              disabled={stopping}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 text-xs font-bold transition-colors disabled:opacity-50"
            >
              <Square className="w-4 h-4 text-rose-400 fill-current" />
              <span>{stopping ? 'Stopping...' : 'Stop Active Run'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Live Run Progress Banner */}
      {isRunning && (
        <div className="rounded-2xl p-6 bg-gradient-to-r from-violet-900/40 to-pink-900/40 border border-violet-500/40 backdrop-blur-xl shadow-xl">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-violet-500/20 text-violet-300 animate-spin">
                <RefreshCw className="w-4 h-4" />
              </div>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-violet-300">
                  Executing Pipeline: {status.phase?.toUpperCase()}
                </span>
                <p className="text-xs text-slate-300 font-medium">
                  {status.progress?.current && status.progress?.total
                    ? `Processed ${status.progress.current} of ${status.progress.total} tasks`
                    : 'Process active...'}
                </p>
              </div>
            </div>

            <span className="text-lg font-black text-white">
              {status.progress?.percent !== undefined ? `${status.progress.percent.toFixed(1)}%` : 'Active'}
            </span>
          </div>

          {/* Progress Bar */}
          <div className="w-full h-3 bg-slate-900/80 rounded-full overflow-hidden p-0.5 border border-white/10">
            <div
              className="h-full bg-gradient-to-r from-violet-500 to-pink-500 rounded-full transition-all duration-300 shadow-lg shadow-violet-500/50"
              style={{ width: `${Math.min(100, Math.max(0, status.progress?.percent || 0))}%` }}
            />
          </div>
        </div>
      )}

      {/* 4 Pipeline Stages Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {phases.map((stage) => {
          const Icon = stage.icon;
          const isCurrentPhase = status.phase === stage.id && isRunning;
          const isPending = startingPhase === stage.id;

          return (
            <div
              key={stage.id}
              className={`relative overflow-hidden rounded-2xl p-6 glass-panel border transition-all duration-200 ${
                isCurrentPhase ? 'border-violet-500 shadow-xl shadow-violet-500/10' : 'border-white/10 hover:border-white/20'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className={`p-3 rounded-xl bg-gradient-to-br ${stage.color}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white text-base">{stage.title}</h3>
                    <code className="text-[11px] text-slate-400 font-mono">{stage.script}</code>
                  </div>
                </div>

                <button
                  onClick={() => setConfirmPhase(stage.id)}
                  disabled={isRunning || isPending}
                  className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-bold shadow-md transition-all active:scale-95"
                >
                  {isPending ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Play className="w-3.5 h-3.5 fill-current" />
                  )}
                  <span>Run Stage</span>
                </button>
              </div>

              <p className="mt-4 text-xs text-slate-400 leading-relaxed">
                {stage.description}
              </p>
            </div>
          );
        })}
      </div>

      {/* Server Terminal Stream Log Monitor */}
      <div className="rounded-2xl glass-panel border border-white/10 overflow-hidden shadow-2xl">
        {/* Terminal Titlebar */}
        <div className="px-5 py-3.5 bg-slate-950/80 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-rose-500/80" />
              <div className="w-3 h-3 rounded-full bg-amber-500/80" />
              <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
            </div>
            <span className="text-xs font-mono font-bold text-slate-300 ml-2">stdout_runner.log</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyLogs}
              disabled={logs.length === 0}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-30"
              title="Copy Logs"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
            <button
              onClick={handleClearLogs}
              disabled={logs.length === 0}
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors disabled:opacity-30"
              title="Clear Logs"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Terminal Content Window */}
        <div
          ref={logTerminalRef}
          onScroll={(e) => {
            const el = e.target;
            autoScrollRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
          }}
          className="h-80 p-4 bg-slate-950/90 font-mono text-xs text-emerald-400/90 overflow-y-auto space-y-1 select-text"
        >
          {logs.length === 0 ? (
            <div className="h-full flex items-center justify-center text-slate-600">
              No logs buffered. Launch a pipeline stage to monitor real-time stdout streams.
            </div>
          ) : (
            logs.map((line, i) => (
              <div key={i} className="leading-relaxed whitespace-pre-wrap break-all">
                {line}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Confirmation Modal */}
      {confirmPhase && (
        <ConfirmDialog
          title={`Launch ${confirmPhase.toUpperCase()}?`}
          message={`Are you sure you want to execute ${confirmPhase}? This will launch Python background subprocesses to crawl BOUN servers.`}
          confirmLabel="Execute Stage"
          onConfirm={() => handleStartPhase(confirmPhase)}
          onCancel={() => setConfirmPhase(null)}
        />
      )}
    </div>
  );
}
