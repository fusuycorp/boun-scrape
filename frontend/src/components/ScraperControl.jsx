import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Square, 
  Trash2, 
  Terminal as ConsoleIcon, 
  AlertTriangle,
  CheckCircle,
  HelpCircle
} from 'lucide-react';

export default function ScraperControl({ token }) {
  const [activeStep, setActiveStep] = useState('phase1');
  const [status, setStatus] = useState({
    phase: null,
    status: 'idle', // idle, running, completed, failed, cancelled
    progress: { total: 0, current: 0, percent: 0.0 }
  });
  const [logs, setLogs] = useState('');
  const terminalEndRef = useRef(null);
  const logInterval = useRef(null);
  const statusInterval = useRef(null);

  const phases = [
    { id: 'phase1', name: 'Stage 1: Term Discovery', desc: 'Queries responses index and registers all historical semesters/academic terms.', script: 'scraper.py' },
    { id: 'phase2', name: 'Stage 2: Extract Departments', desc: 'Extracts the master deduplicated list of active departments across all semesters.', script: 'parse_responses.py' },
    { id: 'phase3', name: 'Stage 3: Exhaustive Scraper', desc: 'Downloads schedule HTML pages for every department across every semester. Bypasses reCAPTCHA using cookies.', script: 'scrape_all_schedules.py' },
    { id: 'phase4', name: 'Stage 4: DB Compiler', desc: 'Parses all schedules HTML pages, normalizes times, and compiles records into SQLite tables.', script: 'parse_schedules_to_db.py' }
  ];

  // Fetch status & logs regularly
  const fetchStatus = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch('http://localhost:8000/api/scrape/status', { headers });
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (err) {
      console.error('Error fetching scraper status:', err);
    }
  };

  const fetchLogs = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch('http://localhost:8000/api/scrape/logs?limit=500', { headers });
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs.join(''));
      }
    } catch (err) {
      console.error('Error fetching logs:', err);
    }
  };

  // Start polling when active
  useEffect(() => {
    fetchStatus();
    fetchLogs();

    statusInterval.current = setInterval(fetchStatus, 2000);
    logInterval.current = setInterval(fetchLogs, 1500);

    return () => {
      clearInterval(statusInterval.current);
      clearInterval(logInterval.current);
    };
  }, [token]);

  // Keep terminal scrolled to bottom
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const handleStart = async () => {
    try {
      const headers = { 
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json'
      };
      
      const res = await fetch('http://localhost:8000/api/scrape/start', {
        method: 'POST',
        headers,
        body: JSON.stringify({ phase: activeStep })
      });

      if (!res.ok) {
        const errData = await res.json();
        alert(errData.detail || 'Failed to trigger scraping task.');
      } else {
        fetchStatus();
        fetchLogs();
      }
    } catch (err) {
      alert('Network request failed.');
    }
  };

  const handleStop = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch('http://localhost:8000/api/scrape/stop', {
        method: 'POST',
        headers
      });
      if (res.ok) {
        fetchStatus();
      }
    } catch (err) {
      alert('Failed to cancel scraping task.');
    }
  };

  const handleClearLogs = async () => {
    if (window.confirm('Are you sure you want to clear console history?')) {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        await fetch('/api/scrape/logs?clear=true', { headers });
        setLogs('');
      } catch (err) {
        console.error('Failed to clear logs:', err);
      }
    }
  };

  const isRunning = status.status === 'running';
  const runningPhase = status.phase;

  return (
    <div className="flex-1 p-8 overflow-y-auto space-y-8 animate-fade-in relative">
      <div className="bg-glow-pink top-[10%] left-[5%]" />
      
      {/* Title */}
      <div>
        <h1 className="text-3xl font-extrabold text-gradient tracking-tight">Scraper Control Room</h1>
        <p className="text-[hsl(var(--text-secondary))] text-sm mt-1">Configure parameters and run scraping routines as async background threads</p>
      </div>

      {/* Scraper Panel Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 z-10 relative">
        {/* Left Control Panel */}
        <div className="xl:col-span-1 space-y-6 flex flex-col justify-between">
          <div className="glass-panel p-6 space-y-5">
            <h2 className="text-lg font-bold">Scraping Pipeline Steps</h2>
            
            <div className="flex flex-col gap-3">
              {phases.map((p) => {
                const isActive = activeStep === p.id;
                const isThisRunning = runningPhase === p.id;
                return (
                  <button
                    key={p.id}
                    disabled={isRunning}
                    onClick={() => setActiveStep(p.id)}
                    className={`w-full text-left p-4 rounded-xl border transition-all flex flex-col gap-1.5 ${
                      isActive 
                        ? 'bg-[hsla(var(--accent-primary)/0.08)] border-[hsl(var(--accent-primary))] shadow-sm'
                        : 'border-[hsla(var(--glass-border))] bg-[hsla(var(--bg-tertiary)/0.3)] hover:bg-[hsla(var(--bg-tertiary)/0.6)]'
                    } ${isRunning ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm">{p.name}</span>
                      {isThisRunning && (
                        <span className="flex items-center gap-1 text-[10px] text-[hsl(var(--accent-primary))] font-bold uppercase tracking-wider">
                          <span className="pulse-indicator pulse-purple w-1.5 h-1.5" />
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
                  onClick={handleStop}
                  className="w-full btn-secondary text-sm flex items-center justify-center gap-2 py-3 text-[hsl(var(--color-danger))] border-[hsla(var(--color-danger)/0.2)] hover:bg-[hsla(var(--color-danger)/0.1)] hover:border-[hsla(var(--color-danger)/0.3)]"
                >
                  <Square size={16} fill="currentColor" />
                  Terminate Scraper
                </button>
              ) : (
                <button 
                  onClick={handleStart}
                  className="w-full btn-primary text-sm flex items-center justify-center gap-2 py-3"
                >
                  <Play size={16} fill="currentColor" />
                  Execute Stage
                </button>
              )}
            </div>
          </div>

          {/* Active Job Progress Card */}
          {isRunning && (
            <div className="glass-panel p-6 bg-gradient-to-tr from-[hsla(var(--accent-primary)/0.05)] to-[hsla(var(--accent-secondary)/0.02)] border-[hsla(var(--accent-primary)/0.2)] flex flex-col gap-4">
              <div>
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <span className="pulse-indicator pulse-purple w-2 h-2" />
                  Active Background Job
                </h3>
                <p className="text-xs text-[hsl(var(--text-muted))] mt-1">Currently compiling data streams</p>
              </div>

              {/* Progress Gauge */}
              <div className="space-y-2">
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

        {/* Right Console Log Panel */}
        <div className="xl:col-span-2 glass-panel p-6 flex flex-col h-[580px] justify-between">
          <div className="flex items-center justify-between border-b border-[hsla(var(--glass-border))] pb-4 mb-4">
            <div className="flex items-center gap-2.5">
              <div className="flex gap-1.5">
                <span className="w-3 h-3 rounded-full bg-rose-500 opacity-80" />
                <span className="w-3 h-3 rounded-full bg-amber-500 opacity-80" />
                <span className="w-3 h-3 rounded-full bg-emerald-500 opacity-80" />
              </div>
              <div className="h-4 w-px bg-[hsl(var(--border-color))]" />
              <span className="text-xs font-medium text-[hsl(var(--text-secondary))] flex items-center gap-2">
                <ConsoleIcon size={14} className="text-[hsl(var(--text-muted))]" />
                stdout_logs.log
              </span>
            </div>

            <button 
              onClick={handleClearLogs}
              className="text-xs text-[hsl(var(--text-muted))] hover:text-[hsl(var(--color-danger))] flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-transparent hover:border-[hsla(var(--color-danger)/0.15)] hover:bg-[hsla(var(--color-danger)/0.05)] transition-all"
            >
              <Trash2 size={13} />
              Clear Console
            </button>
          </div>

          {/* Console Text Frame */}
          <div className="flex-1 bg-[hsl(var(--bg-tertiary))] border border-[hsla(var(--glass-border))] rounded-xl p-4 overflow-y-auto font-mono text-[13px] leading-relaxed text-emerald-400 select-all shadow-inner">
            {logs ? (
              <pre className="whitespace-pre-wrap font-mono">
                {logs}
                <div ref={terminalEndRef} />
              </pre>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-[hsl(var(--text-muted))] font-sans gap-2">
                <ConsoleIcon size={32} className="opacity-30" />
                <p className="text-xs">No active terminal data. Triggers logs by starting a phase.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
