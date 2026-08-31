import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  Terminal,
  History,
  RefreshCw,
  Search,
  Filter,
  Trash2,
  Copy,
  Download,
  Check,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Calendar,
  Layers,
  Play,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  ArrowUpDown,
} from 'lucide-react';
import { api } from '../api/client';
import { useMountedRef } from '../hooks/useSafeAsync';
import { useToast } from '../hooks/useToast';
import ConfirmDialog from './ConfirmDialog';

const LOG_LEVEL_COLORS = {
  ERROR: { bg: 'rgba(255,51,102,0.15)', text: '#ff3366', border: '#ff3366' },
  WARNING: { bg: 'rgba(255,170,0,0.15)', text: '#ffaa00', border: '#ffaa00' },
  INFO: { bg: 'rgba(0,255,102,0.1)', text: '#00ff66', border: '#00ff66' },
  DEBUG: { bg: 'rgba(0,240,255,0.1)', text: '#00f0ff', border: '#00f0ff' },
};

const RUN_STATUS_BADGES = {
  completed: { label: 'COMPLETED', color: 'var(--neon-green)', bg: 'rgba(0,255,102,0.12)', border: 'var(--neon-green)' },
  running: { label: 'RUNNING', color: 'var(--neon-cyan)', bg: 'rgba(0,240,255,0.12)', border: 'var(--neon-cyan)' },
  failed: { label: 'FAILED', color: 'var(--neon-magenta)', bg: 'rgba(255,51,102,0.15)', border: 'var(--neon-magenta)' },
  partial: { label: 'PARTIAL', color: 'var(--neon-amber)', bg: 'rgba(255,170,0,0.12)', border: 'var(--neon-amber)' },
  cancelled: { label: 'CANCELLED', color: 'var(--text-muted)', bg: 'rgba(255,255,255,0.05)', border: 'var(--border-hard)' },
};

function formatDuration(startedAt, completedAt) {
  if (!startedAt) return '-';
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const diffMs = Math.max(0, end - start);
  if (diffMs < 1000) return `${diffMs}ms`;
  const sec = (diffMs / 1000).toFixed(1);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const remSec = (sec % 60).toFixed(0);
  return `${min}m ${remSec}s`;
}

export default function LogsView() {
  const showToast = useToast();
  const isMountedRef = useMountedRef();
  const logTerminalRef = useRef(null);

  // Active View Tab: 'console' | 'history'
  const [activeTab, setActiveTab] = useState('console');

  // Telemetry & Data
  const [logs, setLogs] = useState([]);
  const [runs, setRuns] = useState([]);
  const [status, setStatus] = useState({ is_scraping: false, is_running: false, current_progress: null });
  const [terms, setTerms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Live Console Controls
  const [levelFilter, setLevelFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [pollingActive, setPollingActive] = useState(true);
  const [copied, setCopied] = useState(false);
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);

  // Scrape History Controls & Expanded Drilldown
  const [termFilter, setTermFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [expandedRunId, setExpandedRunId] = useState(null);
  const [runCoverageDetails, setRunCoverageDetails] = useState({});
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [retryingDept, setRetryingDept] = useState(null);

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

  // Fetch Logs
  const fetchLogs = useCallback(async () => {
    try {
      const logEntries = await api.getScrapeLogs({ limit: 500 }).catch(() => []);
      if (isMountedRef.current) {
        setLogs(logEntries || []);
      }
    } catch {
      // Ignore
    }
  }, [isMountedRef]);

  // Fetch Scrape Runs
  const fetchRuns = useCallback(async () => {
    try {
      const params = { limit: 100 };
      if (termFilter !== 'ALL') {
        params.term = termFilter;
      }
      const runList = await api.getScrapeRuns(params).catch(() => []);
      if (isMountedRef.current) {
        setRuns(runList || []);
      }
    } catch {
      // Ignore
    }
  }, [isMountedRef, termFilter]);

  // Fetch Scraper Operational Status
  const fetchStatus = useCallback(async () => {
    try {
      const stat = await api.getScrapeStatus().catch(() => null);
      if (isMountedRef.current && stat) {
        setStatus(stat);
      }
    } catch {
      // Ignore
    }
  }, [isMountedRef]);

  // Unified Refresh
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([fetchLogs(), fetchRuns(), fetchStatus()]);
    if (isMountedRef.current) {
      setRefreshing(false);
      setLoading(false);
    }
  }, [fetchLogs, fetchRuns, fetchStatus, isMountedRef]);

  // Initial Load
  useEffect(() => {
    fetchTerms();
    handleRefresh();
  }, [fetchTerms, handleRefresh]);

  // Polling Interval (every 2s for active logs/runs)
  useEffect(() => {
    if (!pollingActive) return;
    const interval = setInterval(() => {
      fetchLogs();
      fetchStatus();
      if (activeTab === 'history') {
        fetchRuns();
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [pollingActive, activeTab, fetchLogs, fetchStatus, fetchRuns]);

  // Auto-scroll terminal when new logs arrive
  useEffect(() => {
    if (autoScroll && logTerminalRef.current) {
      logTerminalRef.current.scrollTop = logTerminalRef.current.scrollHeight;
    }
  }, [logs, autoScroll, levelFilter, searchQuery]);

  // Filtered Logs Memo
  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      if (levelFilter !== 'ALL' && log.level !== levelFilter) {
        return false;
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const msg = (log.message || '').toLowerCase();
        const logger = (log.name || '').toLowerCase();
        return msg.includes(query) || logger.includes(query);
      }
      return true;
    });
  }, [logs, levelFilter, searchQuery]);

  // Log Counts Breakdown
  const logStats = useMemo(() => {
    let errors = 0;
    let warnings = 0;
    let info = 0;
    let debug = 0;
    logs.forEach((l) => {
      if (l.level === 'ERROR') errors++;
      else if (l.level === 'WARNING') warnings++;
      else if (l.level === 'INFO') info++;
      else if (l.level === 'DEBUG') debug++;
    });
    return { errors, warnings, info, debug, total: logs.length };
  }, [logs]);

  // Filtered Runs Memo
  const filteredRuns = useMemo(() => {
    return runs.filter((run) => {
      if (termFilter !== 'ALL' && run.term !== termFilter) {
        return false;
      }
      if (statusFilter !== 'ALL' && run.status?.toLowerCase() !== statusFilter.toLowerCase()) {
        return false;
      }
      return true;
    });
  }, [runs, termFilter, statusFilter]);

  // Lifetime Runs Metrics
  const runMetrics = useMemo(() => {
    const total = runs.length;
    const completed = runs.filter((r) => r.status === 'completed').length;
    const failed = runs.filter((r) => r.status === 'failed').length;
    const successRate = total > 0 ? ((completed / total) * 100).toFixed(1) : '100.0';
    return { total, completed, failed, successRate };
  }, [runs]);

  // Copy Logs to Clipboard
  const handleCopyLogs = () => {
    const text = filteredLogs
      .map((l) => `[${l.timestamp}] [${l.level}] [${l.name || 'app'}] ${l.message}`)
      .join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    showToast('Logs copied to clipboard', 'info');
    setTimeout(() => setCopied(false), 2000);
  };

  // Download Logs as File
  const handleDownloadLogs = () => {
    const text = filteredLogs
      .map((l) => `[${l.timestamp}] [${l.level}] [${l.name || 'app'}] ${l.message}`)
      .join('\n');
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `boun_scrape_logs_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '_')}.log`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('Log file exported successfully', 'success');
  };

  // Clear Logs Buffer
  const handleClearLogs = async () => {
    try {
      await api.getScrapeLogs(true);
      setLogs([]);
      setClearConfirmOpen(false);
      showToast('Log buffer cleared', 'info');
    } catch {
      showToast('Failed to clear log buffer', 'error');
    }
  };

  // Expand Run & Fetch Department Coverage Drilldown
  const handleToggleRun = async (run) => {
    if (expandedRunId === run.run_id) {
      setExpandedRunId(null);
      return;
    }

    setExpandedRunId(run.run_id);
    if (!runCoverageDetails[run.term]) {
      setLoadingDetails(true);
      try {
        const coverage = await api.getCoverageSummary(run.term);
        if (isMountedRef.current) {
          setRunCoverageDetails((prev) => ({ ...prev, [run.term]: coverage }));
        }
      } catch {
        showToast(`Failed to load department details for term ${run.term}`, 'error');
      } finally {
        if (isMountedRef.current) {
          setLoadingDetails(false);
        }
      }
    }
  };

  // Trigger Targeted Re-scrape for Failed Departments
  const handleRetryFailed = async (term, deptCode = null) => {
    try {
      setRetryingDept(deptCode || 'ALL_FAILED');
      const payload = {
        term,
        departments: deptCode ? [deptCode] : null,
        failed_only: !deptCode,
        skip_already_scraped: false,
        background: true,
      };
      await api.startScrape(payload);
      showToast(`Scrape retry triggered for ${deptCode || 'failed departments'} (${term})`, 'success');
      fetchStatus();
      fetchRuns();
    } catch (err) {
      showToast(err.message || 'Failed to trigger scrape retry', 'error');
    } finally {
      if (isMountedRef.current) {
        setRetryingDept(null);
      }
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* View Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Terminal size={18} style={{ color: 'var(--neon-green)' }} />
            <h1 className="text-glow-green" style={{
              fontSize: '18px',
              fontWeight: 700,
              letterSpacing: '0.08em',
              margin: 0,
              color: 'var(--neon-green)',
            }}>
              [07] //_LOGS & SCRAPE_HISTORY
            </h1>
          </div>
          <p style={{ margin: '4px 0 0 0', color: 'var(--text-muted)', fontSize: '11px', letterSpacing: '0.04em' }}>
            Real-time execution telemetry, circular debug logs, and chronological scrape run auditor.
          </p>
        </div>

        {/* Global Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => setPollingActive((prev) => !prev)}
            style={{
              padding: '6px 12px',
              background: pollingActive ? 'rgba(0,255,102,0.1)' : 'var(--bg-secondary)',
              border: `1px solid ${pollingActive ? 'var(--neon-green)' : 'var(--border-hard)'}`,
              color: pollingActive ? 'var(--neon-green)' : 'var(--text-muted)',
              fontSize: '11px',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer',
            }}
          >
            <span className={`led-indicator ${pollingActive ? 'led-green' : 'led-amber'}`} />
            {pollingActive ? 'LIVE_POLL: ON' : 'LIVE_POLL: PAUSED'}
          </button>

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            style={{
              padding: '6px 12px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-hard)',
              color: 'var(--neon-cyan)',
              fontSize: '11px',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              cursor: refreshing ? 'not-allowed' : 'pointer',
            }}
          >
            <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
            REFRESH
          </button>
        </div>
      </div>

      {/* Top Telemetry HUD Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '12px',
      }}>
        {/* Card 1: Total Runs */}
        <div className="retro-card" style={{ padding: '12px 14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '10px', letterSpacing: '0.06em' }}>TOTAL RUNS</span>
            <History size={13} style={{ color: 'var(--neon-cyan)' }} />
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neon-cyan)', marginTop: '4px' }}>
            {runMetrics.total}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Lifetime executed runs
          </div>
        </div>

        {/* Card 2: Success Rate */}
        <div className="retro-card" style={{ padding: '12px 14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '10px', letterSpacing: '0.06em' }}>SUCCESS RATE</span>
            <CheckCircle2 size={13} style={{ color: 'var(--neon-green)' }} />
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neon-green)', marginTop: '4px' }}>
            {runMetrics.successRate}%
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
            {runMetrics.completed} succeeded / {runMetrics.failed} failed
          </div>
        </div>

        {/* Card 3: Buffer Log Counts */}
        <div className="retro-card" style={{ padding: '12px 14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '10px', letterSpacing: '0.06em' }}>BUFFERED LOGS</span>
            <Terminal size={13} style={{ color: 'var(--neon-amber)' }} />
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
            {logStats.total}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px', fontSize: '10px' }}>
            <span style={{ color: '#ff3366', fontWeight: 700 }}>{logStats.errors} ERR</span>
            <span style={{ color: '#ffaa00', fontWeight: 700 }}>{logStats.warnings} WARN</span>
            <span style={{ color: '#00ff66' }}>{logStats.info} INFO</span>
          </div>
        </div>

        {/* Card 4: Live Engine Status */}
        <div className="retro-card" style={{ padding: '12px 14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '10px', letterSpacing: '0.06em' }}>ENGINE STATE</span>
            <span className={`led-indicator ${status.is_scraping ? 'led-cyan animate-pulse' : 'led-green'}`} />
          </div>
          <div style={{
            fontSize: '15px',
            fontWeight: 700,
            color: status.is_scraping ? 'var(--neon-cyan)' : 'var(--neon-green)',
            marginTop: '4px',
            textTransform: 'uppercase',
          }}>
            {status.is_scraping ? 'SCRAPING IN PROGRESS' : 'ENGINE IDLE'}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
            {status.current_progress
              ? `Dept: ${status.current_progress.department} (${status.current_progress.completed}/${status.current_progress.total})`
              : `Daemon: ${status.is_running ? 'RUNNING' : 'STANDBY'}`}
          </div>
        </div>
      </div>

      {/* Tab Switcher */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        borderBottom: '1px solid var(--border-hard)',
        paddingBottom: '2px',
      }}>
        <button
          onClick={() => setActiveTab('console')}
          style={{
            padding: '8px 16px',
            background: activeTab === 'console' ? 'var(--bg-secondary)' : 'transparent',
            border: activeTab === 'console' ? '1px solid var(--border-hard)' : '1px solid transparent',
            borderBottom: activeTab === 'console' ? '2px solid var(--neon-green)' : '2px solid transparent',
            color: activeTab === 'console' ? 'var(--neon-green)' : 'var(--text-muted)',
            fontSize: '11px',
            fontWeight: 700,
            letterSpacing: '0.06em',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
          }}
        >
          <Terminal size={13} />
          [01] //_LIVE_CONSOLE
          <span style={{
            fontSize: '9px',
            padding: '1px 6px',
            background: 'rgba(0,255,102,0.1)',
            border: '1px solid rgba(0,255,102,0.2)',
            borderRadius: '2px',
          }}>
            {logs.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('history')}
          style={{
            padding: '8px 16px',
            background: activeTab === 'history' ? 'var(--bg-secondary)' : 'transparent',
            border: activeTab === 'history' ? '1px solid var(--border-hard)' : '1px solid transparent',
            borderBottom: activeTab === 'history' ? '2px solid var(--neon-cyan)' : '2px solid transparent',
            color: activeTab === 'history' ? 'var(--neon-cyan)' : 'var(--text-muted)',
            fontSize: '11px',
            fontWeight: 700,
            letterSpacing: '0.06em',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
          }}
        >
          <History size={13} />
          [02] //_SCRAPE_HISTORY
          <span style={{
            fontSize: '9px',
            padding: '1px 6px',
            background: 'rgba(0,240,255,0.1)',
            border: '1px solid rgba(0,240,255,0.2)',
            borderRadius: '2px',
          }}>
            {runs.length}
          </span>
        </button>
      </div>

      {/* TAB 1: LIVE CONSOLE */}
      {activeTab === 'console' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* Console Controls Bar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '10px',
            padding: '10px 14px',
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-hard)',
          }}>
            {/* Left: Severity Level Filter Pills */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700 }}>LEVEL:</span>
              {['ALL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'].map((lvl) => {
                const isSelected = levelFilter === lvl;
                const count = lvl === 'ALL' ? logStats.total : logStats[lvl.toLowerCase() + 's'] || logStats[lvl.toLowerCase()] || 0;
                return (
                  <button
                    key={lvl}
                    onClick={() => setLevelFilter(lvl)}
                    style={{
                      padding: '3px 8px',
                      fontSize: '10px',
                      fontWeight: 700,
                      background: isSelected ? 'var(--bg-primary)' : 'transparent',
                      border: `1px solid ${isSelected ? (lvl === 'ERROR' ? '#ff3366' : lvl === 'WARNING' ? '#ffaa00' : 'var(--neon-green)') : 'var(--border-hard)'}`,
                      color: isSelected ? (lvl === 'ERROR' ? '#ff3366' : lvl === 'WARNING' ? '#ffaa00' : 'var(--neon-green)') : 'var(--text-muted)',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    {lvl}
                    <span style={{ opacity: 0.7, fontSize: '9px' }}>({count})</span>
                  </button>
                );
              })}
            </div>

            {/* Right: Search & Action Buttons */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              {/* Search Bar */}
              <div style={{ position: 'relative', minWidth: '180px' }}>
                <input
                  type="text"
                  placeholder="Filter logs (e.g. 500, SCED)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '4px 8px 4px 26px',
                    background: 'var(--bg-void)',
                    border: '1px solid var(--border-hard)',
                    color: 'var(--text-primary)',
                    fontSize: '11px',
                    fontFamily: 'var(--font-mono)',
                    outline: 'none',
                  }}
                />
                <Search size={12} style={{ position: 'absolute', left: '8px', top: '7px', color: 'var(--text-muted)' }} />
              </div>

              {/* Auto Scroll Toggle */}
              <button
                onClick={() => setAutoScroll((prev) => !prev)}
                title={autoScroll ? 'Auto-scroll enabled' : 'Auto-scroll disabled'}
                style={{
                  padding: '4px 8px',
                  background: autoScroll ? 'rgba(0,255,102,0.1)' : 'var(--bg-primary)',
                  border: `1px solid ${autoScroll ? 'var(--neon-green)' : 'var(--border-hard)'}`,
                  color: autoScroll ? 'var(--neon-green)' : 'var(--text-muted)',
                  fontSize: '10px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <ArrowUpDown size={11} />
                AUTO_SCROLL: {autoScroll ? 'ON' : 'OFF'}
              </button>

              {/* Copy Button */}
              <button
                onClick={handleCopyLogs}
                style={{
                  padding: '4px 8px',
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border-hard)',
                  color: 'var(--text-secondary)',
                  fontSize: '10px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                {copied ? <Check size={11} style={{ color: 'var(--neon-green)' }} /> : <Copy size={11} />}
                COPY
              </button>

              {/* Download Button */}
              <button
                onClick={handleDownloadLogs}
                style={{
                  padding: '4px 8px',
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border-hard)',
                  color: 'var(--neon-cyan)',
                  fontSize: '10px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <Download size={11} />
                EXPORT
              </button>

              {/* Clear Button */}
              <button
                onClick={() => setClearConfirmOpen(true)}
                style={{
                  padding: '4px 8px',
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border-hard)',
                  color: '#ff3366',
                  fontSize: '10px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <Trash2 size={11} />
                CLEAR
              </button>
            </div>
          </div>

          {/* Terminal Console Viewport */}
          <div
            ref={logTerminalRef}
            style={{
              height: '540px',
              background: 'var(--bg-void)',
              border: '1px solid var(--border-hard)',
              padding: '12px 14px',
              overflowY: 'auto',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              lineHeight: '1.5',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
            }}
          >
            {filteredLogs.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', marginTop: '180px' }}>
                [CONSOLE_EMPTY] // No log entries match current filters or buffer is clear.
              </div>
            ) : (
              filteredLogs.map((entry, idx) => {
                const style = LOG_LEVEL_COLORS[entry.level] || LOG_LEVEL_COLORS.INFO;
                const timeStr = entry.timestamp
                  ? new Date(entry.timestamp).toISOString().slice(11, 23)
                  : '--:--:--.---';

                return (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                      padding: '2px 4px',
                      borderRadius: '2px',
                      background: entry.level === 'ERROR' ? 'rgba(255,51,102,0.06)' : 'transparent',
                    }}
                  >
                    {/* Timestamp */}
                    <span style={{ color: 'var(--text-muted)', flexShrink: 0, fontSize: '10px' }}>
                      {timeStr}
                    </span>

                    {/* Level Pill */}
                    <span style={{
                      padding: '1px 5px',
                      fontSize: '9px',
                      fontWeight: 700,
                      color: style.text,
                      background: style.bg,
                      border: `1px solid ${style.border}`,
                      borderRadius: '2px',
                      flexShrink: 0,
                      textTransform: 'uppercase',
                    }}>
                      {entry.level}
                    </span>

                    {/* Logger Module Badge */}
                    {entry.name && (
                      <span style={{ color: 'var(--neon-cyan)', opacity: 0.8, flexShrink: 0, fontSize: '10px' }}>
                        [{entry.name.replace('boun_scrape.', '')}]
                      </span>
                    )}

                    {/* Message Body */}
                    <span style={{
                      color: entry.level === 'ERROR' ? '#ff4d79' : entry.level === 'WARNING' ? '#ffbb33' : 'var(--text-primary)',
                      wordBreak: 'break-word',
                      whiteSpace: 'pre-wrap',
                      flex: 1,
                    }}>
                      {entry.message}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* TAB 2: SCRAPE RUNS HISTORY */}
      {activeTab === 'history' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* Filter Bar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '10px',
            padding: '10px 14px',
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-hard)',
          }}>
            {/* Term Filter */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700 }}>ACADEMIC TERM:</span>
              <select
                value={termFilter}
                onChange={(e) => setTermFilter(e.target.value)}
                style={{
                  padding: '4px 8px',
                  background: 'var(--bg-void)',
                  border: '1px solid var(--border-hard)',
                  color: 'var(--text-primary)',
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  outline: 'none',
                }}
              >
                <option value="ALL">ALL TERMS ({terms.length})</option>
                {terms.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>

            {/* Status Filter */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700 }}>STATUS:</span>
              {['ALL', 'COMPLETED', 'RUNNING', 'FAILED', 'PARTIAL'].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  style={{
                    padding: '3px 8px',
                    fontSize: '10px',
                    fontWeight: 700,
                    background: statusFilter === st ? 'var(--bg-primary)' : 'transparent',
                    border: `1px solid ${statusFilter === st ? 'var(--neon-cyan)' : 'var(--border-hard)'}`,
                    color: statusFilter === st ? 'var(--neon-cyan)' : 'var(--text-muted)',
                    cursor: 'pointer',
                  }}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          {/* Runs Table */}
          <div style={{
            background: 'var(--bg-primary)',
            border: '1px solid var(--border-hard)',
            overflowX: 'auto',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
              <thead>
                <tr style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-hard)', textAlign: 'left' }}>
                  <th style={{ padding: '10px 12px', color: 'var(--text-muted)', width: '30px' }} />
                  <th style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>RUN_ID</th>
                  <th style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>TERM</th>
                  <th style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>STATUS</th>
                  <th style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>DEPARTMENTS</th>
                  <th style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>COURSES / SLOTS</th>
                  <th style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>CHANGES</th>
                  <th style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>DURATION</th>
                  <th style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>STARTED_AT</th>
                </tr>
              </thead>
              <tbody>
                {filteredRuns.length === 0 ? (
                  <tr>
                    <td colSpan={9} style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                      [NO_RUNS_FOUND] // No scrape runs match selected filters.
                    </td>
                  </tr>
                ) : (
                  filteredRuns.map((run) => {
                    const isExpanded = expandedRunId === run.run_id;
                    const badge = RUN_STATUS_BADGES[run.status] || RUN_STATUS_BADGES.completed;
                    const deptRatio = run.total_departments > 0
                      ? `${run.completed_departments}/${run.total_departments}`
                      : '0/0';
                    const deptPercent = run.total_departments > 0
                      ? Math.round((run.completed_departments / run.total_departments) * 100)
                      : 0;

                    return (
                      <React.Fragment key={run.run_id}>
                        <tr
                          onClick={() => handleToggleRun(run)}
                          style={{
                            borderBottom: '1px solid var(--border-hard)',
                            background: isExpanded ? 'rgba(0,240,255,0.04)' : 'transparent',
                            cursor: 'pointer',
                            transition: 'background 0.1s ease',
                          }}
                        >
                          {/* Expand Icon */}
                          <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>
                            {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                          </td>

                          {/* Run ID */}
                          <td style={{ padding: '10px 12px', fontWeight: 700, color: 'var(--neon-cyan)' }}>
                            {run.run_id}
                          </td>

                          {/* Term */}
                          <td style={{ padding: '10px 12px', color: 'var(--text-primary)' }}>
                            {run.term}
                          </td>

                          {/* Status Badge */}
                          <td style={{ padding: '10px 12px' }}>
                            <span style={{
                              padding: '2px 6px',
                              fontSize: '9px',
                              fontWeight: 700,
                              color: badge.color,
                              background: badge.bg,
                              border: `1px solid ${badge.border}`,
                              borderRadius: '2px',
                            }}>
                              {badge.label}
                            </span>
                          </td>

                          {/* Department Progress */}
                          <td style={{ padding: '10px 12px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <div style={{
                                width: '60px',
                                height: '6px',
                                background: 'var(--bg-secondary)',
                                border: '1px solid var(--border-hard)',
                                overflow: 'hidden',
                              }}>
                                <div style={{
                                  height: '100%',
                                  width: `${deptPercent}%`,
                                  background: deptPercent === 100 ? 'var(--neon-green)' : 'var(--neon-amber)',
                                }} />
                              </div>
                              <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                                {deptRatio} ({deptPercent}%)
                              </span>
                            </div>
                          </td>

                          {/* Courses / Slots */}
                          <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>
                            {run.total_courses} / {run.total_slots}
                          </td>

                          {/* Changes */}
                          <td style={{ padding: '10px 12px' }}>
                            <span style={{
                              color: run.changes_detected > 0 ? 'var(--neon-amber)' : 'var(--text-muted)',
                              fontWeight: run.changes_detected > 0 ? 700 : 400,
                            }}>
                              {run.changes_detected > 0 ? `+${run.changes_detected}` : '0'}
                            </span>
                          </td>

                          {/* Duration */}
                          <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>
                            {formatDuration(run.started_at, run.completed_at)}
                          </td>

                          {/* Started At */}
                          <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: '10px' }}>
                            {run.started_at ? new Date(run.started_at).toLocaleString('en-GB') : '-'}
                          </td>
                        </tr>

                        {/* Expanded Drilldown Accordion */}
                        {isExpanded && (
                          <tr style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-hard)' }}>
                            <td colSpan={9} style={{ padding: '14px 18px' }}>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                {/* Run Overview & Actions */}
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
                                  <div>
                                    <span style={{ color: 'var(--neon-cyan)', fontWeight: 700 }}>
                                      RUN_DETAILS // {run.run_id} ({run.term})
                                    </span>
                                    {run.error_message && (
                                      <div style={{ color: '#ff3366', fontSize: '11px', marginTop: '4px' }}>
                                        ERROR: {run.error_message}
                                      </div>
                                    )}
                                  </div>

                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleRetryFailed(run.term);
                                      }}
                                      disabled={retryingDept !== null}
                                      style={{
                                        padding: '4px 10px',
                                        background: 'rgba(255,170,0,0.1)',
                                        border: '1px solid var(--neon-amber)',
                                        color: 'var(--neon-amber)',
                                        fontSize: '10px',
                                        fontWeight: 700,
                                        cursor: 'pointer',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '4px',
                                      }}
                                    >
                                      <RotateCcw size={11} />
                                      RETRY_FAILED_DEPTS ({run.term})
                                    </button>
                                  </div>
                                </div>

                                {/* Department Breakdown Table */}
                                {loadingDetails ? (
                                  <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                                    [LOADING_DEPARTMENT_COVERAGE]...
                                  </div>
                                ) : runCoverageDetails[run.term] ? (
                                  <div style={{
                                    maxHeight: '260px',
                                    overflowY: 'auto',
                                    border: '1px solid var(--border-hard)',
                                    background: 'var(--bg-void)',
                                  }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10px' }}>
                                      <thead>
                                        <tr style={{ background: 'var(--bg-primary)', borderBottom: '1px solid var(--border-hard)', textAlign: 'left' }}>
                                          <th style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>CODE</th>
                                          <th style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>DEPARTMENT_NAME</th>
                                          <th style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>STATUS</th>
                                          <th style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>COURSES</th>
                                          <th style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>LAST_SCRAPED</th>
                                          <th style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>DIAGNOSTICS</th>
                                          <th style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>ACTION</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {runCoverageDetails[run.term].departments.map((dept) => {
                                          const isFailed = dept.status === 'FAILED';
                                          const isSuccess = dept.status === 'SUCCESS';

                                          return (
                                            <tr key={dept.code} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                              <td style={{ padding: '6px 10px', fontWeight: 700, color: 'var(--neon-green)' }}>
                                                {dept.code}
                                              </td>
                                              <td style={{ padding: '6px 10px', color: 'var(--text-primary)' }}>
                                                {dept.name}
                                              </td>
                                              <td style={{ padding: '6px 10px' }}>
                                                <span style={{
                                                  padding: '1px 5px',
                                                  fontSize: '9px',
                                                  fontWeight: 700,
                                                  color: isSuccess ? 'var(--neon-green)' : isFailed ? '#ff3366' : 'var(--text-muted)',
                                                  background: isSuccess ? 'rgba(0,255,102,0.1)' : isFailed ? 'rgba(255,51,102,0.1)' : 'transparent',
                                                  border: `1px solid ${isSuccess ? 'var(--neon-green)' : isFailed ? '#ff3366' : 'var(--border-hard)'}`,
                                                  borderRadius: '2px',
                                                }}>
                                                  {dept.status}
                                                </span>
                                              </td>
                                              <td style={{ padding: '6px 10px', color: 'var(--text-secondary)' }}>
                                                {dept.course_count}
                                              </td>
                                              <td style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>
                                                {dept.last_scraped_at ? new Date(dept.last_scraped_at).toLocaleTimeString('en-GB') : '-'}
                                              </td>
                                              <td style={{ padding: '6px 10px', color: isFailed ? '#ff4d79' : 'var(--text-muted)', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={dept.last_error || ''}>
                                                {dept.last_error || (isSuccess ? 'Scraped 200 OK' : '-')}
                                              </td>
                                              <td style={{ padding: '6px 10px' }}>
                                                <button
                                                  onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleRetryFailed(run.term, dept.code);
                                                  }}
                                                  disabled={retryingDept === dept.code}
                                                  style={{
                                                    padding: '2px 6px',
                                                    background: 'transparent',
                                                    border: '1px solid var(--border-hard)',
                                                    color: 'var(--neon-cyan)',
                                                    fontSize: '9px',
                                                    cursor: 'pointer',
                                                  }}
                                                >
                                                  {retryingDept === dept.code ? '...' : 'RETRY'}
                                                </button>
                                              </td>
                                            </tr>
                                          );
                                        })}
                                      </tbody>
                                    </table>
                                  </div>
                                ) : (
                                  <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                                    No department snapshot records available for this term.
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Confirmation Dialog for Clearing Logs */}
      <ConfirmDialog
        open={clearConfirmOpen}
        title="CLEAR_CIRCULAR_LOG_BUFFER"
        message="Are you sure you want to flush all in-memory application log entries? This will delete all buffered messages from memory."
        confirmLabel="FLUSH_BUFFER"
        onConfirm={handleClearLogs}
        onCancel={() => setClearConfirmOpen(false)}
      />
    </div>
  );
}
