import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Play,
  Square,
  Terminal as TerminalIcon,
  RefreshCw,
  Trash2,
  Copy,
  Check,
  Clock,
  Calendar,
  Save,
  PlayCircle,
  StopCircle,
} from 'lucide-react';
import { api } from '../api/client';
import { useMountedRef } from '../hooks/useSafeAsync';
import { useToast } from '../hooks/useToast';
import ConfirmDialog from './ConfirmDialog';

const formatLogEntry = (entry) =>
  `[${new Date(entry.timestamp).toLocaleTimeString('en-GB')}] [${entry.level}] ${entry.message}`;

export default function ScraperControl() {
  const showToast = useToast();
  const isMountedRef = useMountedRef();
  const logTerminalRef = useRef(null);

  // Status & Telemetry
  const [status, setStatus] = useState({ is_scraping: false, is_running: false, current_progress: null });
  const [logs, setLogs] = useState([]);
  const [terms, setTerms] = useState([]);

  // Manual Trigger Settings
  const [selectedTerm, setSelectedTerm] = useState('');
  const [exportArtifacts, setExportArtifacts] = useState(true);
  const [dispatchWebhooks, setDispatchWebhooks] = useState(true);
  const [captureQuota, setCaptureQuota] = useState(false);
  const [skipAlreadyScraped, setSkipAlreadyScraped] = useState(false);

  // Scheduler / Daemon Settings
  const [scheduleConfig, setScheduleConfig] = useState(null);
  const [intervalOption, setIntervalOption] = useState('3600');
  const [customInterval, setCustomInterval] = useState('3600');
  const [cronExpression, setCronExpression] = useState('');
  const [defaultScheduleTerm, setDefaultScheduleTerm] = useState('');
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [togglingDaemon, setTogglingDaemon] = useState(false);

  // Action States
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [copied, setCopied] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const autoScrollRef = useRef(true);

  // Fetch Lookups
  const fetchTerms = useCallback(async () => {
    try {
      const termList = await api.getTerms().catch(() => []);
      if (isMountedRef.current) {
        setTerms(termList || []);
      }
    } catch {
      // Ignore
    }
  }, [isMountedRef]);

  const fetchScheduleConfig = useCallback(async () => {
    try {
      const config = await api.getScheduleConfig().catch(() => null);
      if (isMountedRef.current && config) {
        setScheduleConfig(config);
        const sec = config.interval_seconds;
        if (['1800', '3600', '21600', '43200', '86400'].includes(String(sec))) {
          setIntervalOption(String(sec));
        } else {
          setIntervalOption('custom');
          setCustomInterval(String(sec));
        }
        setCronExpression(config.cron_expression || '');
        setDefaultScheduleTerm(config.default_term || '');
      }
    } catch {
      // Ignore
    }
  }, [isMountedRef]);

  const pollScraper = useCallback(async () => {
    try {
      const statusRes = await api
        .getScrapeStatus()
        .catch(() => ({ is_scraping: false, is_running: false, current_progress: null }));

      let logsRes = null;
      if (statusRes.is_scraping) {
        logsRes = await api.getScrapeLogs().catch(() => []);
      }

      if (isMountedRef.current) {
        setStatus(statusRes);
        if (logsRes) {
          setLogs(logsRes.map(formatLogEntry));
        }
      }
    } catch {
      // Ignore transient polling errors
    }
  }, [isMountedRef]);

  const isRunning = status.is_scraping;
  const isDaemonRunning = status.is_running || scheduleConfig?.is_running;

  useEffect(() => {
    fetchTerms();
    fetchScheduleConfig();
  }, [fetchTerms, fetchScheduleConfig]);

  useEffect(() => {
    let timerId = null;

    const poll = async () => {
      if (document.hidden) return;
      await pollScraper();
    };

    const scheduleNext = () => {
      const intervalMs = isRunning ? 1500 : 8000;
      timerId = setTimeout(async () => {
        await poll();
        scheduleNext();
      }, intervalMs);
    };

    poll();
    scheduleNext();

    const handleVisibilityChange = () => {
      if (!document.hidden) {
        poll();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      if (timerId) clearTimeout(timerId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [isRunning, pollScraper]);

  useEffect(() => {
    if (autoScrollRef.current && logTerminalRef.current) {
      logTerminalRef.current.scrollTop = logTerminalRef.current.scrollHeight;
    }
  }, [logs]);

  const handleStart = async () => {
    setConfirmOpen(false);
    setStarting(true);
    try {
      const payload = {
        term: selectedTerm === 'all' ? null : (selectedTerm || null),
        all_terms: selectedTerm === 'all',
        export: exportArtifacts,
        dispatch_webhooks: dispatchWebhooks,
        capture_quota: captureQuota,
        skip_already_scraped: skipAlreadyScraped,
        background: true,
      };
      await api.startScrape(payload);
      showToast('SCRAPE_CYCLE_LAUNCHED_SUCCESSFULLY', 'success');
      pollScraper();
    } catch (err) {
      showToast(err.message || 'FAILED_TO_LAUNCH_SCRAPE_CYCLE', 'error');
    } finally {
      if (isMountedRef.current) setStarting(false);
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

  const handleToggleDaemon = async () => {
    setTogglingDaemon(true);
    try {
      if (isDaemonRunning) {
        await api.stopSchedulerDaemon();
        if (isMountedRef.current) {
          setScheduleConfig((prev) => (prev ? { ...prev, is_running: false } : { is_running: false }));
          setStatus((prev) => ({ ...prev, is_running: false }));
        }
        showToast('AUTORUN_DAEMON_STOPPED', 'info');
      } else {
        await api.startSchedulerDaemon();
        if (isMountedRef.current) {
          setScheduleConfig((prev) => (prev ? { ...prev, is_running: true } : { is_running: true }));
          setStatus((prev) => ({ ...prev, is_running: true }));
        }
        showToast('AUTORUN_DAEMON_STARTED', 'success');
      }
      await Promise.all([fetchScheduleConfig(), pollScraper()]);
    } catch (err) {
      showToast(err.message || 'FAILED_TO_TOGGLE_DAEMON', 'error');
    } finally {
      if (isMountedRef.current) setTogglingDaemon(false);
    }
  };

  const handleSaveScheduleConfig = async (e) => {
    e.preventDefault();
    setSavingSchedule(true);
    try {
      const finalInterval = intervalOption === 'custom'
        ? parseInt(customInterval, 10) || 3600
        : parseInt(intervalOption, 10) || 3600;

      const res = await api.updateScheduleConfig({
        interval_seconds: finalInterval,
        cron_expression: cronExpression.trim() || null,
        default_term: defaultScheduleTerm.trim() || null,
      });
      setScheduleConfig(res);
      showToast('AUTORUN_SCHEDULE_CONFIG_SAVED', 'success');
    } catch (err) {
      showToast(err.message || 'FAILED_TO_UPDATE_SCHEDULE', 'error');
    } finally {
      if (isMountedRef.current) setSavingSchedule(false);
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
    const logText = logs.join('\n');
    navigator.clipboard.writeText(logText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const progress = status.current_progress;
  const percent = progress?.total
    ? Math.round((progress.completed / progress.total) * 1000) / 10
    : isRunning ? 0 : 100;

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
            Trigger targeted scrape cycles, configure periodic background daemons, and inspect live stdout terminal buffer streams.
          </p>
        </div>

        {/* Global Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
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
                  EXECUTING: {progress?.department ? `DEPT: ${progress.department.toUpperCase()}` : 'SCRAPING'}
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>
                  {progress?.completed && progress?.total
                    ? `Processed ${progress.completed} of ${progress.total} department tasks`
                    : 'Crawling stream active...'}
                </div>
              </div>
            </div>

            <span style={{ color: 'var(--neon-green)', fontSize: '18px', fontWeight: 800, fontFamily: 'var(--font-mono)' }}>
              {`${percent.toFixed(1)}%`}
            </span>
          </div>

          <div className="cyber-progress">
            <div
              className="cyber-progress-fill"
              style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
            />
          </div>
        </div>
      )}

      {/* Grid: Manual Execution & Auto-Run Daemon Panels */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '20px' }}>
        {/* Manual Trigger Control Panel */}
        <div
          className="cyber-card"
          style={{
            border: isRunning ? '2px solid var(--neon-green)' : '1px solid var(--border-hard)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            gap: '16px',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
              <TerminalIcon size={14} style={{ color: 'var(--neon-green)' }} />
              <h3 style={{ fontSize: '12px', margin: 0, color: 'var(--text-primary)', fontWeight: 700 }}>
                [01] MANUAL_SCRAPE_EXECUTION
              </h3>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.4', margin: '0 0 16px' }}>
              Execute an on-demand crawl against university servers for a specific academic term or discover the latest automatically.
            </p>

            {/* Term Selector */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '14px' }}>
              <label style={{ fontSize: '11px', color: 'var(--neon-amber)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Calendar size={13} />
                TARGET_ACADEMIC_TERM:
              </label>
              <select
                value={selectedTerm}
                onChange={(e) => setSelectedTerm(e.target.value)}
                disabled={isRunning}
                className="cyber-input"
                style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}
              >
                <option value="">[AUTO-DISCOVER LATEST TERM]</option>
                <option value="all">[ALL DISCOVERED TERMS]</option>
                {terms.map((t) => (
                  <option key={t} value={t}>
                    TERM: {t}
                  </option>
                ))}
              </select>
            </div>

            {/* Run Options */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px', background: 'var(--bg-primary)', border: '1px solid var(--border-dim)' }}>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.05em' }}>
                EXECUTION_FLAGS:
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-primary)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={exportArtifacts}
                  onChange={(e) => setExportArtifacts(e.target.checked)}
                  disabled={isRunning}
                />
                Export Disk Artifacts (JSON / CSV / SQLite)
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-primary)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={skipAlreadyScraped}
                  onChange={(e) => setSkipAlreadyScraped(e.target.checked)}
                  disabled={isRunning}
                />
                Skip Already-Scraped Departments (Incremental Crawl)
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-primary)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={dispatchWebhooks}
                  onChange={(e) => setDispatchWebhooks(e.target.checked)}
                  disabled={isRunning}
                />
                Dispatch Webhook Notifications
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-primary)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={captureQuota}
                  onChange={(e) => setCaptureQuota(e.target.checked)}
                  disabled={isRunning}
                />
                Capture Section Quotas (Rate-limited live snapshot)
              </label>
            </div>
          </div>

          <button
            onClick={() => setConfirmOpen(true)}
            disabled={isRunning || starting}
            className="btn-cyber btn-cyber-primary"
            style={{ width: '100%', fontSize: '11px', padding: '10px 16px', justifyContent: 'center' }}
          >
            {starting ? (
              <RefreshCw size={14} className="animate-spin" />
            ) : (
              <Play size={14} fill="currentColor" />
            )}
            <span>[EXECUTE_SCRAPE_CYCLE]</span>
          </button>
        </div>

        {/* Auto-Run Background Scheduler Config Panel */}
        <div
          className="cyber-card"
          style={{
            border: '1px solid var(--border-hard)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            gap: '16px',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Clock size={14} style={{ color: 'var(--neon-cyan)' }} />
                <h3 style={{ fontSize: '12px', margin: 0, color: 'var(--text-primary)', fontWeight: 700 }}>
                  [02] PERIODIC_AUTORUN_SCHEDULER
                </h3>
              </div>
              <div>
                {isDaemonRunning ? (
                  <span className="cyber-badge cyber-badge-green">[● ACTIVE: DAEMON]</span>
                ) : (
                  <span className="cyber-badge cyber-badge-amber">[- IDLE / STOPPED]</span>
                )}
              </div>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.4', margin: '0 0 16px' }}>
              Configure scheduled background cycles to scrape, detect deltas, and export data on an automated cadence.
            </p>

            <form onSubmit={handleSaveScheduleConfig} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {/* Interval Preset */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '11px', color: 'var(--neon-cyan)', fontWeight: 700 }}>
                  CADENCE_INTERVAL:
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <select
                    value={intervalOption}
                    onChange={(e) => setIntervalOption(e.target.value)}
                    className="cyber-input"
                    style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}
                  >
                    <option value="1800">Every 30 Minutes</option>
                    <option value="3600">Every 1 Hour (Default)</option>
                    <option value="21600">Every 6 Hours</option>
                    <option value="43200">Every 12 Hours</option>
                    <option value="86400">Every 24 Hours</option>
                    <option value="custom">Custom (Seconds)</option>
                  </select>

                  {intervalOption === 'custom' ? (
                    <input
                      type="number"
                      min="60"
                      value={customInterval}
                      onChange={(e) => setCustomInterval(e.target.value)}
                      placeholder="Seconds (e.g. 7200)"
                      className="cyber-input"
                      style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}
                    />
                  ) : (
                    <input
                      type="text"
                      disabled
                      value={`${(parseInt(intervalOption, 10) / 3600).toFixed(1)}h cycle`}
                      className="cyber-input"
                      style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', opacity: 0.7 }}
                    />
                  )}
                </div>
              </div>

              {/* Cron Expression */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <label style={{ fontSize: '11px', color: 'var(--text-primary)' }}>
                  CRON_EXPRESSION (OPTIONAL):
                </label>
                <input
                  type="text"
                  value={cronExpression}
                  onChange={(e) => setCronExpression(e.target.value)}
                  placeholder="e.g. 0 */2 * * * (Overrides Interval)"
                  className="cyber-input"
                  style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}
                />
              </div>

              {/* Default Term */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <label style={{ fontSize: '11px', color: 'var(--text-primary)' }}>
                  SCHEDULED_DEFAULT_TERM:
                </label>
                <select
                  value={defaultScheduleTerm}
                  onChange={(e) => setDefaultScheduleTerm(e.target.value)}
                  className="cyber-input"
                  style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}
                >
                  <option value="">[AUTO-RESOLVE LATEST TERM]</option>
                  {terms.map((t) => (
                    <option key={t} value={t}>
                      TERM: {t}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                <button
                  type="submit"
                  disabled={savingSchedule}
                  className="btn-cyber"
                  style={{ flex: 1, fontSize: '11px', justifyContent: 'center' }}
                >
                  <Save size={13} />
                  <span>{savingSchedule ? '[SAVING...]' : '[SAVE_CONFIG]'}</span>
                </button>
              </div>
            </form>
          </div>

          {/* Start/Stop Daemon Toggle */}
          <div style={{ paddingTop: '12px', borderTop: '1px solid var(--border-dim)' }}>
            <button
              onClick={handleToggleDaemon}
              disabled={togglingDaemon}
              className={`btn-cyber ${isDaemonRunning ? 'btn-cyber-danger' : 'btn-cyber-primary'}`}
              style={{ width: '100%', fontSize: '11px', padding: '8px 16px', justifyContent: 'center' }}
            >
              {togglingDaemon ? (
                <RefreshCw size={13} className="animate-spin" />
              ) : isDaemonRunning ? (
                <StopCircle size={14} />
              ) : (
                <PlayCircle size={14} />
              )}
              <span>
                {isDaemonRunning ? '[STOP_BACKGROUND_DAEMON]' : '[START_BACKGROUND_DAEMON]'}
              </span>
            </button>
          </div>
        </div>
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
              &gt; AWAITING_PIPELINE_OUTPUT... LAUNCH A SCRAPE CYCLE TO INGEST TELEMETRY.
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
      {confirmOpen && (
        <ConfirmDialog
          open={confirmOpen}
          title="EXECUTE_SCRAPE_CYCLE?"
          description={`Confirm execution trigger for ${selectedTerm === 'all' ? 'ALL TERMS' : (selectedTerm || 'LATEST AUTO-DISCOVERED TERM')}. This will initiate a full background crawl against university registration servers.`}
          confirmLabel="[EXECUTE]"
          cancelLabel="[ABORT]"
          onConfirm={handleStart}
          onCancel={() => setConfirmOpen(false)}
        />
      )}
    </div>
  );
}
