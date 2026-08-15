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
      showToast(`LAUNCHED_${phase.toUpperCase()}_SUCCESSFULLY`, 'success');
      pollScraper();
    } catch (err) {
      showToast(err.message || `FAILED_TO_LAUNCH_${phase.toUpperCase()}`, 'error');
    } finally {
      if (isMountedRef.current) setStartingPhase(null);
    }
  };

  const handleStop = async () => {
    setStopping(true);
    try {
      await api.stopScrape();
      showToast('PIPELINE_EXECUTION_TERMINATED', 'info');
      pollScraper();
    } catch (err) {
      showToast(err.message || 'FAILED_TO_HALT_PROCESS', 'error');
    } finally {
      if (isMountedRef.current) setStopping(false);
    }
  };

  const handleClearLogs = async () => {
    try {
      await api.getScrapeLogs(true);
      setLogs([]);
      showToast('TERMINAL_BUFFER_PURGED', 'info');
    } catch (err) {
      showToast(err.message || 'FAILED_TO_CLEAR_LOGS', 'error');
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
      num: '01',
      title: 'STAGE_1: TERM_DISCOVERY',
      script: 'scraper.py',
      description: 'Posts ASP.NET ViewState form requests to discover and download semester index pages.',
      icon: Clock,
      color: 'var(--neon-cyan)',
    },
    {
      id: 'phase2',
      num: '02',
      title: 'STAGE_2: DEPARTMENT_CATALOG',
      script: 'parse_responses.py',
      description: 'Extracts department links and outputs deduplicated catalog into departments_all.json.',
      icon: Layers,
      color: 'var(--neon-green)',
    },
    {
      id: 'phase3',
      num: '03',
      title: 'STAGE_3: SCHEDULE_CRAWLER',
      script: 'scrape_all_schedules.py',
      description: 'Multi-threaded downloader (10 workers) fetching raw department HTML schedule files.',
      icon: TerminalIcon,
      color: 'var(--neon-pink)',
    },
    {
      id: 'phase4',
      num: '04',
      title: 'STAGE_4: SQLITE_DATABASE_ETL',
      script: 'parse_schedules_to_db.py',
      description: 'Parallel parser compiling HTML tables into SQLite with atomic batch transactions.',
      icon: Database,
      color: 'var(--neon-amber)',
    },
  ];

  const isRunning = status.status === 'running';

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span className="led-indicator led-green" />
            <span style={{ color: 'var(--neon-green)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em' }}>
              SYS://PIPELINE_ORCHESTRATOR
            </span>
          </div>
          <h1 className="glow-green" style={{ color: 'var(--neon-green)', fontSize: '20px', margin: 0 }}>
            /// INGESTION_PIPELINE_CONTROLLER
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '4px' }}>
            Orchestrate background crawling stages and inspect live stdout terminal buffer streams.
          </p>
        </div>

        {/* Global Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <label
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 12px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-hard)',
              color: forceRefresh ? 'var(--neon-amber)' : 'var(--text-muted)',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
              userSelect: 'none',
              fontFamily: 'var(--font-mono)',
            }}
          >
            <input
              type="checkbox"
              checked={forceRefresh}
              onChange={(e) => setForceRefresh(e.target.checked)}
              style={{ accentColor: 'var(--neon-amber)' }}
            />
            <span>[FORCE_REFRESH]</span>
          </label>

          {isRunning && (
            <button
              onClick={handleStop}
              disabled={stopping}
              className="btn-cyber btn-cyber-danger"
              style={{ fontSize: '11px', padding: '6px 14px' }}
            >
              <Square size={13} fill="currentColor" />
              <span>{stopping ? '[...HALTING]' : '[!! EMERGENCY_HALT !!]'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Live Run Progress Banner */}
      {isRunning && (
        <div
          className="cyber-card"
          style={{
            border: '2px solid var(--neon-green)',
            boxShadow: '0 0 16px rgba(0, 255, 102, 0.15)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <RefreshCw size={15} className="animate-spin" style={{ color: 'var(--neon-green)' }} />
              <div>
                <div style={{ color: 'var(--neon-green)', fontSize: '11px', fontWeight: 800, letterSpacing: '0.08em' }}>
                  EXECUTING: {status.phase?.toUpperCase()}
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>
                  {status.progress?.current && status.progress?.total
                    ? `Processed ${status.progress.current} of ${status.progress.total} department tasks`
                    : 'Crawling stream active...'}
                </div>
              </div>
            </div>

            <span style={{ color: 'var(--neon-green)', fontSize: '18px', fontWeight: 800, fontFamily: 'var(--font-mono)' }}>
              {status.progress?.percent !== undefined ? `${status.progress.percent.toFixed(1)}%` : 'ACTIVE'}
            </span>
          </div>

          <div className="cyber-progress">
            <div
              className="cyber-progress-fill"
              style={{ width: `${Math.min(100, Math.max(0, status.progress?.percent || 0))}%` }}
            />
          </div>
        </div>
      )}

      {/* 4 Pipeline Stage Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {phases.map((stage) => {
          const Icon = stage.icon;
          const isCurrentPhase = status.phase === stage.id && isRunning;
          const isPending = startingPhase === stage.id;

          return (
            <div
              key={stage.id}
              className="cyber-card"
              style={{
                border: isCurrentPhase ? '2px solid var(--neon-green)' : '1px solid var(--border-hard)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px', marginBottom: '10px' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ color: stage.color, fontSize: '10px', fontWeight: 700 }}>
                        [{stage.num}]
                      </span>
                      <h3 style={{ fontSize: '12px', margin: 0, color: 'var(--text-primary)' }}>
                        {stage.title}
                      </h3>
                    </div>
                    <code style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      //_{stage.script}
                    </code>
                  </div>

                  <button
                    onClick={() => setConfirmPhase(stage.id)}
                    disabled={isRunning || isPending}
                    className="btn-cyber btn-cyber-primary"
                    style={{ fontSize: '10px', padding: '5px 10px' }}
                  >
                    {isPending ? (
                      <RefreshCw size={11} className="animate-spin" />
                    ) : (
                      <Play size={11} fill="currentColor" />
                    )}
                    <span>[EXEC]</span>
                  </button>
                </div>

                <p style={{ color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.4', margin: 0 }}>
                  {stage.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Server Terminal Stream Log Monitor */}
      <div className="terminal-window" style={{ border: '1px solid var(--border-hard)' }}>
        <div className="terminal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="led-indicator led-green" />
            <span style={{ color: 'var(--neon-green)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em' }}>
              TTY: /dev/pts/0 // STDOUT_RUNNER.LOG
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <button
              onClick={handleCopyLogs}
              disabled={logs.length === 0}
              className="btn-cyber"
              style={{ fontSize: '9px', padding: '3px 8px' }}
              title="Copy Logs"
            >
              {copied ? <Check size={11} style={{ color: 'var(--neon-green)' }} /> : <Copy size={11} />}
              <span>{copied ? 'COPIED' : 'DUMP'}</span>
            </button>
            <button
              onClick={handleClearLogs}
              disabled={logs.length === 0}
              className="btn-cyber"
              style={{ fontSize: '9px', padding: '3px 8px', color: 'var(--neon-pink)', borderColor: 'var(--border-hard)' }}
              title="Clear Logs"
            >
              <Trash2 size={11} />
              <span>PURGE</span>
            </button>
          </div>
        </div>

        <div
          ref={logTerminalRef}
          onScroll={(e) => {
            const el = e.target;
            autoScrollRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
          }}
          className="terminal-body"
          style={{ height: '320px', fontSize: '11px' }}
        >
          {logs.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px 0' }}>
              &gt; AWAITING_PIPELINE_OUTPUT... LAUNCH A STAGE TO INGEST TELEMETRY.
            </div>
          ) : (
            logs.map((line, i) => (
              <div key={i} style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                {line}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Confirmation Modal */}
      {confirmPhase && (
        <ConfirmDialog
          open={Boolean(confirmPhase)}
          title={`EXECUTE_${confirmPhase.toUpperCase()}?`}
          description={`Confirm execution trigger for ${confirmPhase}. This will initiate background crawling against university registration servers.`}
          confirmLabel="[EXECUTE_STAGE]"
          cancelLabel="[ABORT]"
          onConfirm={() => handleStartPhase(confirmPhase)}
          onCancel={() => setConfirmPhase(null)}
        />
      )}
    </div>
  );
}
