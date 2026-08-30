import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Layers,
  Clock,
  RefreshCw,
  Search,
  Play,
  RotateCcw,
  Calendar,
  Building2,
  BookOpen,
  Filter,
  AlertTriangle,
  Globe,
  CheckCircle2,
} from 'lucide-react';
import { api } from '../api/client';
import { useMountedRef } from '../hooks/useSafeAsync';
import { useToast } from '../hooks/useToast';
import ConfirmDialog from './ConfirmDialog';

export default function CoverageDashboard() {
  const showToast = useToast();
  const isMountedRef = useMountedRef();

  const [terms, setTerms] = useState([]);
  const [selectedTerm, setSelectedTerm] = useState('');
  const [coverageData, setCoverageData] = useState(null);
  const [masterData, setMasterData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Trigger Action States
  const [triggering, setTriggering] = useState(false);
  const [confirmModal, setConfirmModal] = useState({ open: false, type: '', deptCode: null });

  // Load available terms
  const fetchTerms = useCallback(async (signal) => {
    try {
      const termList = await api.getTerms({ signal }).catch((err) => {
        if (err.name === 'AbortError' || err.name === 'DOMException' || signal?.aborted) return [];
        return [];
      });
      if (isMountedRef.current && !signal?.aborted) {
        setTerms(termList || []);
        if (termList && termList.length > 0 && !selectedTerm) {
          setSelectedTerm(termList[0]);
        }
      }
    } catch (err) {
      if (err.name === 'AbortError' || err.name === 'DOMException' || signal?.aborted) return;
      // Ignore
    }
  }, [isMountedRef, selectedTerm]);

  // Load master and selected term coverage data
  const fetchCoverage = useCallback(async (signalOrOptions) => {
    const signal =
      signalOrOptions instanceof AbortSignal
        ? signalOrOptions
        : signalOrOptions?.signal instanceof AbortSignal
        ? signalOrOptions.signal
        : undefined;

    try {
      setRefreshing(true);
      const [masterRes, termRes] = await Promise.all([
        api.getMasterCoverage({ signal }).catch((err) => {
          if (err.name === 'AbortError' || err.name === 'DOMException' || signal?.aborted) return null;
          return null;
        }),
        selectedTerm
          ? api.getCoverageSummary(selectedTerm, { signal }).catch((err) => {
              if (err.name === 'AbortError' || err.name === 'DOMException' || signal?.aborted) return null;
              throw err;
            })
          : Promise.resolve(null),
      ]);

      if (isMountedRef.current && !signal?.aborted) {
        if (masterRes) setMasterData(masterRes);
        if (termRes) setCoverageData(termRes);
      }
    } catch (err) {
      if (err.name === 'AbortError' || err.name === 'DOMException' || signal?.aborted) {
        return;
      }
      if (isMountedRef.current) {
        showToast(err.message || 'FAILED_TO_LOAD_COVERAGE_DATA', 'error');
      }
    } finally {
      if (isMountedRef.current && !signal?.aborted) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [selectedTerm, isMountedRef, showToast]);

  useEffect(() => {
    const controller = new AbortController();
    fetchTerms(controller.signal);
    return () => {
      controller.abort();
    };
  }, [fetchTerms]);

  useEffect(() => {
    const controller = new AbortController();
    fetchCoverage(controller.signal);
    return () => {
      controller.abort();
    };
  }, [selectedTerm, fetchCoverage]);

  // Filtered department list
  const filteredDepartments = useMemo(() => {
    if (!coverageData?.departments) return [];
    return coverageData.departments.filter((dept) => {
      const matchesSearch =
        dept.code.toLowerCase().includes(search.toLowerCase()) ||
        dept.name.toLowerCase().includes(search.toLowerCase());

      if (!matchesSearch) return false;

      if (statusFilter === 'ALL') return true;
      if (statusFilter === 'COMPLETED') return dept.status === 'COMPLETED';
      if (statusFilter === 'PENDING') return dept.status === 'PENDING';
      if (statusFilter === 'FAILED') return dept.status === 'FAILED';
      return true;
    });
  }, [coverageData, search, statusFilter]);

  const handleTriggerScrape = async (payload) => {
    setTriggering(true);
    setConfirmModal({ open: false, type: '', deptCode: null });
    try {
      await api.startScrape({
        background: true,
        ...payload,
      });
      showToast('CRAWLER_TASK_DISPATCHED', 'success');
      setTimeout(() => fetchCoverage(), 1500);
    } catch (err) {
      showToast(err.message || 'FAILED_TO_DISPATCH_SCRAPE', 'error');
    } finally {
      if (isMountedRef.current) setTriggering(false);
    }
  };

  const handleConfirmAction = () => {
    if (confirmModal.type === 'RESCRAPE_ALL_FAILED_GLOBAL') {
      handleTriggerScrape({ all_terms: true, failed_only: true });
    } else if (confirmModal.type === 'RESCRAPE_FAILED_TERM') {
      handleTriggerScrape({ term: selectedTerm, failed_only: true });
    } else if (confirmModal.type === 'MISSING') {
      handleTriggerScrape({ term: selectedTerm, skip_already_scraped: true });
    } else if (confirmModal.type === 'FORCE_ALL') {
      handleTriggerScrape({ term: selectedTerm, skip_already_scraped: false });
    } else if (confirmModal.type === 'SINGLE_DEPT' && confirmModal.deptCode) {
      handleTriggerScrape({ term: selectedTerm, departments: [confirmModal.deptCode] });
    }
  };

  // Selected term metrics
  const totalDepts = coverageData?.total_departments || 0;
  const completedDepts = coverageData?.completed_departments || 0;
  const pendingDepts = coverageData?.pending_departments || 0;
  const failedDepts = coverageData?.failed_departments || 0;
  const totalCourses = coverageData?.total_courses || 0;
  const percentComplete = coverageData?.percent_complete || 0;

  // Master all-terms metrics
  const masterTermsCount = masterData?.total_terms || terms.length || 0;
  const masterTotalDepts = masterData?.total_departments || 0;
  const masterCompletedDepts = masterData?.completed_departments || 0;
  const masterFailedDepts = masterData?.failed_departments || 0;
  const masterPendingDepts = masterData?.pending_departments || 0;
  const masterTotalCourses = masterData?.total_courses || 0;
  const masterPercent = masterData?.percent_complete || 0;

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header & Term Selector */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span className="led-indicator led-green" />
            <span style={{ color: 'var(--neon-green)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em' }}>
              SYS://COVERAGE_RADAR
            </span>
          </div>
          <h1 className="glow-green" style={{ color: 'var(--neon-green)', fontSize: '20px', margin: 0 }}>
            /// SCRAPING_RESULTS_AND_COVERAGE
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '4px' }}>
            Track ingested departments, course counts, and execution status across all academic terms.
          </p>
        </div>

        {/* Term Switcher & Refresh */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Calendar size={14} style={{ color: 'var(--neon-amber)' }} />
            <select
              value={selectedTerm}
              onChange={(e) => setSelectedTerm(e.target.value)}
              className="cyber-input"
              style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', minWidth: '150px' }}
            >
              {terms.map((t) => (
                <option key={t} value={t}>
                  TERM: {t}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => fetchCoverage()}
            disabled={refreshing}
            className="btn-cyber"
            style={{ fontSize: '11px', padding: '6px 12px' }}
            title="Refresh Coverage"
          >
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
            <span>[REFRESH]</span>
          </button>
        </div>
      </div>

      {/* MASTER TELEMETRY DECK (ALL TERMS AGGREGATE) */}
      <div
        className="cyber-card"
        style={{
          border: '1px solid var(--neon-cyan)',
          background: 'rgba(0, 240, 255, 0.02)',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        {/* Master Header */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Globe size={16} style={{ color: 'var(--neon-cyan)' }} />
            <span style={{ fontSize: '12px', fontWeight: 800, color: 'var(--neon-cyan)', letterSpacing: '0.08em' }}>
              GLOBAL_SCRAPE_RADAR // MASTER_STATISTICS ({masterTermsCount} TERMS)
            </span>
          </div>

          {/* Master Rescrape All Failed Button */}
          <button
            onClick={() => setConfirmModal({ open: true, type: 'RESCRAPE_ALL_FAILED_GLOBAL', deptCode: null })}
            disabled={triggering || masterFailedDepts === 0}
            className="btn-cyber"
            style={{
              fontSize: '11px',
              padding: '6px 14px',
              borderColor: masterFailedDepts > 0 ? 'var(--neon-pink)' : 'var(--border-dim)',
              color: masterFailedDepts > 0 ? 'var(--neon-pink)' : 'var(--text-muted)',
              background: masterFailedDepts > 0 ? 'rgba(255, 0, 85, 0.08)' : 'transparent',
            }}
            title={masterFailedDepts > 0 ? `Rescrape all ${masterFailedDepts} failed departments across all terms` : 'No failed departments across all terms'}
          >
            <AlertTriangle size={13} style={{ color: masterFailedDepts > 0 ? 'var(--neon-pink)' : 'var(--text-muted)' }} />
            <span>[RESCRAPE_ALL_FAILED (GLOBAL: {masterFailedDepts})]</span>
          </button>
        </div>

        {/* Master Stats Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
          {/* Global Completion Rate */}
          <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-dim)', padding: '12px' }}>
            <div style={{ color: 'var(--text-secondary)', fontSize: '10px', fontWeight: 700 }}>
              ALL-TERMS INGESTION
            </div>
            <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--neon-green)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
              {`${masterPercent.toFixed(1)}%`}
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginTop: '2px' }}>
              {masterCompletedDepts} of {masterTotalDepts} depts scraped
            </div>
            <div className="cyber-progress" style={{ marginTop: '8px', height: '3px' }}>
              <div className="cyber-progress-fill" style={{ width: `${masterPercent}%` }} />
            </div>
          </div>

          {/* Global Scraped (Completed) */}
          <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-dim)', padding: '12px' }}>
            <div style={{ color: 'var(--text-secondary)', fontSize: '10px', fontWeight: 700 }}>
              SCRAPED (COMPLETED)
            </div>
            <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--neon-green)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
              {masterCompletedDepts.toLocaleString()}
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginTop: '2px' }}>
              Across {masterTermsCount} academic terms
            </div>
          </div>

          {/* Global Failed */}
          <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-dim)', padding: '12px' }}>
            <div style={{ color: 'var(--text-secondary)', fontSize: '10px', fontWeight: 700 }}>
              FAILED DEPARTMENTS
            </div>
            <div style={{ fontSize: '20px', fontWeight: 800, color: masterFailedDepts > 0 ? 'var(--neon-pink)' : 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
              {masterFailedDepts.toLocaleString()}
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginTop: '2px' }}>
              {masterFailedDepts > 0 ? 'Requires targeted re-scrape' : 'Zero failures detected'}
            </div>
          </div>

          {/* Global Pending */}
          <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-dim)', padding: '12px' }}>
            <div style={{ color: 'var(--text-secondary)', fontSize: '10px', fontWeight: 700 }}>
              PENDING INGESTION
            </div>
            <div style={{ fontSize: '20px', fontWeight: 800, color: masterPendingDepts > 0 ? 'var(--neon-amber)' : 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
              {masterPendingDepts.toLocaleString()}
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginTop: '2px' }}>
              Awaiting crawler execution
            </div>
          </div>

          {/* Global Courses */}
          <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-dim)', padding: '12px' }}>
            <div style={{ color: 'var(--text-secondary)', fontSize: '10px', fontWeight: 700 }}>
              TOTAL COURSES (GLOBAL)
            </div>
            <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--neon-cyan)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
              {masterTotalCourses.toLocaleString()}
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginTop: '2px' }}>
              Total schedule records in DB
            </div>
          </div>
        </div>

        {/* Per-Term Switcher Chips */}
        {masterData?.terms && masterData.terms.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', paddingTop: '4px', borderTop: '1px solid var(--border-dim)' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '10px', fontWeight: 700 }}>
              TERMS:
            </span>
            {masterData.terms.map((t) => {
              const isSelected = t.term === selectedTerm;
              return (
                <button
                  key={t.term}
                  onClick={() => setSelectedTerm(t.term)}
                  style={{
                    background: isSelected ? 'rgba(0, 255, 65, 0.12)' : 'var(--bg-primary)',
                    border: `1px solid ${isSelected ? 'var(--neon-green)' : 'var(--border-dim)'}`,
                    color: isSelected ? 'var(--neon-green)' : 'var(--text-secondary)',
                    padding: '4px 10px',
                    fontSize: '10px',
                    fontFamily: 'var(--font-mono)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <span style={{ fontWeight: isSelected ? 800 : 500 }}>{t.term}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '9px' }}>
                    ({t.completed_departments}/{t.total_departments})
                  </span>
                  {t.failed_departments > 0 ? (
                    <span style={{ color: 'var(--neon-pink)', fontSize: '9px', fontWeight: 700 }}>
                      !{t.failed_departments}
                    </span>
                  ) : t.percent_complete === 100 ? (
                    <CheckCircle2 size={10} style={{ color: 'var(--neon-green)' }} />
                  ) : null}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Selected Term Overview Telemetry Deck */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        {/* Coverage Percentage Card */}
        <div className="cyber-card" style={{ border: '1px solid var(--border-hard)', padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: '11px', fontWeight: 700 }}>
              TERM_INGESTION_COVERAGE ({selectedTerm || 'N/A'})
            </span>
            <Layers size={15} style={{ color: 'var(--neon-green)' }} />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--neon-green)', fontFamily: 'var(--font-mono)' }}>
            {`${percentComplete.toFixed(1)}%`}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginTop: '4px' }}>
            {completedDepts} of {totalDepts} departments ingested
          </div>
          <div className="cyber-progress" style={{ marginTop: '10px', height: '4px' }}>
            <div className="cyber-progress-fill" style={{ width: `${percentComplete}%` }} />
          </div>
        </div>

        {/* Courses Count */}
        <div className="cyber-card" style={{ border: '1px solid var(--border-hard)', padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: '11px', fontWeight: 700 }}>
              TERM_COURSES_INDEXED
            </span>
            <BookOpen size={15} style={{ color: 'var(--neon-cyan)' }} />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--neon-cyan)', fontFamily: 'var(--font-mono)' }}>
            {totalCourses.toLocaleString()}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginTop: '4px' }}>
            Active schedule sections in {selectedTerm || 'term'}
          </div>
        </div>

        {/* Status Distribution */}
        <div className="cyber-card" style={{ border: '1px solid var(--border-hard)', padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: '11px', fontWeight: 700 }}>
              TERM_STATUS_BREAKDOWN
            </span>
            <Building2 size={15} style={{ color: 'var(--neon-amber)' }} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
            <span className="cyber-badge cyber-badge-green">
              {completedDepts} COMPLETED
            </span>
            {pendingDepts > 0 && (
              <span className="cyber-badge cyber-badge-amber">
                {pendingDepts} PENDING
              </span>
            )}
            {failedDepts > 0 && (
              <span className="cyber-badge cyber-badge-pink">
                {failedDepts} FAILED
              </span>
            )}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginTop: '8px' }}>
            {coverageData?.last_scraped_at ? `Last sync: ${coverageData.last_scraped_at}` : 'No scrape records yet'}
          </div>
        </div>
      </div>

      {/* Action Bar & Filters */}
      <div
        className="cyber-card"
        style={{
          border: '1px solid var(--border-hard)',
          padding: '16px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
        }}
      >
        {/* Left: Quick Scrape Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {/* Rescrape Failed Only Button (Term) */}
          <button
            onClick={() => setConfirmModal({ open: true, type: 'RESCRAPE_FAILED_TERM', deptCode: null })}
            disabled={triggering || failedDepts === 0}
            className="btn-cyber"
            style={{
              fontSize: '11px',
              padding: '8px 14px',
              borderColor: failedDepts > 0 ? 'var(--neon-pink)' : 'var(--border-dim)',
              color: failedDepts > 0 ? 'var(--neon-pink)' : 'var(--text-muted)',
              background: failedDepts > 0 ? 'rgba(255, 0, 85, 0.08)' : 'transparent',
            }}
            title={failedDepts > 0 ? `Rescrape ${failedDepts} failed departments in ${selectedTerm}` : 'No failed departments in current term'}
          >
            <AlertTriangle size={13} style={{ color: failedDepts > 0 ? 'var(--neon-pink)' : 'var(--text-muted)' }} />
            <span>[RESCRAPE_FAILED_ONLY ({failedDepts})]</span>
          </button>

          {/* Scrape Missing Only (Pending + Failed) */}
          <button
            onClick={() => setConfirmModal({ open: true, type: 'MISSING', deptCode: null })}
            disabled={triggering || pendingDepts + failedDepts === 0}
            className="btn-cyber btn-cyber-primary"
            style={{ fontSize: '11px', padding: '8px 14px' }}
          >
            <Play size={13} fill="currentColor" />
            <span>[SCRAPE_MISSING_ONLY ({pendingDepts + failedDepts})]</span>
          </button>

          {/* Force Full Rescrape */}
          <button
            onClick={() => setConfirmModal({ open: true, type: 'FORCE_ALL', deptCode: null })}
            disabled={triggering}
            className="btn-cyber"
            style={{ fontSize: '11px', padding: '8px 14px' }}
          >
            <RotateCcw size={13} />
            <span>[FORCE_FULL_RESCRAPE]</span>
          </button>
        </div>

        {/* Right: Search & Status Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {/* Status Filter Buttons */}
          <div style={{ display: 'flex', border: '1px solid var(--border-dim)', background: 'var(--bg-primary)' }}>
            {['ALL', 'COMPLETED', 'PENDING', 'FAILED'].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                style={{
                  background: statusFilter === st ? 'var(--neon-green)' : 'transparent',
                  color: statusFilter === st ? '#000' : 'var(--text-secondary)',
                  border: 'none',
                  fontSize: '10px',
                  fontWeight: 700,
                  padding: '6px 10px',
                  cursor: 'pointer',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div style={{ position: 'relative', minWidth: '180px' }}>
            <Search size={13} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search code/name..."
              className="cyber-input"
              style={{ paddingLeft: '28px', fontSize: '11px', fontFamily: 'var(--font-mono)' }}
            />
          </div>
        </div>
      </div>

      {/* Department Coverage Data Table */}
      <div className="cyber-card" style={{ border: '1px solid var(--border-hard)', padding: '0', overflow: 'hidden' }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border-dim)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Filter size={13} style={{ color: 'var(--neon-green)' }} />
            <span style={{ fontSize: '11px', color: 'var(--text-primary)', fontWeight: 700 }}>
              DEPARTMENT_REGISTRY ({filteredDepartments.length} of {totalDepts}) — TERM: {selectedTerm}
            </span>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
            [LOADING_COVERAGE_DATA...]
          </div>
        ) : filteredDepartments.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
            NO_DEPARTMENTS_FOUND_MATCHING_FILTER
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="cyber-table" style={{ width: '100%', fontSize: '11px' }}>
              <thead>
                <tr>
                  <th style={{ width: '90px' }}>CODE</th>
                  <th>DEPARTMENT NAME</th>
                  <th style={{ width: '110px' }}>COURSES</th>
                  <th style={{ width: '170px' }}>LAST SCRAPED</th>
                  <th style={{ width: '120px' }}>STATUS</th>
                  <th style={{ width: '110px', textAlign: 'right' }}>ACTION</th>
                </tr>
              </thead>
              <tbody>
                {filteredDepartments.map((dept) => (
                  <tr key={dept.code}>
                    <td style={{ fontWeight: 800, color: 'var(--neon-green)', fontFamily: 'var(--font-mono)' }}>
                      {dept.code}
                    </td>
                    <td style={{ color: 'var(--text-primary)' }}>
                      {dept.name}
                      {dept.error_message && (
                        <div style={{ fontSize: '10px', color: 'var(--neon-pink)', marginTop: '2px' }}>
                          Error: {dept.error_message}
                        </div>
                      )}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: dept.course_count > 0 ? 'var(--neon-cyan)' : 'var(--text-muted)' }}>
                      {dept.course_count > 0 ? `${dept.course_count} courses` : '-'}
                    </td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '10px', fontFamily: 'var(--font-mono)' }}>
                      {dept.last_scraped_at ? (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <Clock size={11} />
                          {dept.last_scraped_at}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>Never</span>
                      )}
                    </td>
                    <td>
                      {dept.status === 'COMPLETED' ? (
                        <span className="cyber-badge cyber-badge-green" style={{ fontSize: '9px' }}>
                          ● COMPLETED
                        </span>
                      ) : dept.status === 'FAILED' ? (
                        <span className="cyber-badge cyber-badge-pink" style={{ fontSize: '9px' }}>
                          ! FAILED
                        </span>
                      ) : (
                        <span className="cyber-badge cyber-badge-amber" style={{ fontSize: '9px' }}>
                          - PENDING
                        </span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        onClick={() => setConfirmModal({ open: true, type: 'SINGLE_DEPT', deptCode: dept.code })}
                        disabled={triggering}
                        className="btn-cyber"
                        style={{ fontSize: '9px', padding: '3px 8px' }}
                        title={`Scrape ${dept.code}`}
                      >
                        <Play size={10} fill="currentColor" />
                        <span>SYNC</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      {confirmModal.open && (
        <ConfirmDialog
          open={confirmModal.open}
          title={
            confirmModal.type === 'RESCRAPE_ALL_FAILED_GLOBAL'
              ? 'RESCRAPE_ALL_FAILED_DEPARTMENTS_GLOBALLY?'
              : confirmModal.type === 'RESCRAPE_FAILED_TERM'
              ? `RESCRAPE_FAILED_DEPARTMENTS_IN_${selectedTerm}?`
              : confirmModal.type === 'MISSING'
              ? 'SCRAPE_MISSING_DEPARTMENTS?'
              : confirmModal.type === 'SINGLE_DEPT'
              ? `SCRAPE_DEPARTMENT_${confirmModal.deptCode}?`
              : 'FORCE_FULL_TERM_RESCRAPE?'
          }
          description={
            confirmModal.type === 'RESCRAPE_ALL_FAILED_GLOBAL'
              ? `Initiate a background rescrape cycle across all academic terms for the ${masterFailedDepts} failed department(s). Completed departments will be bypassed.`
              : confirmModal.type === 'RESCRAPE_FAILED_TERM'
              ? `Initiate a targeted background rescrape for the ${failedDepts} failed department(s) in ${selectedTerm}.`
              : confirmModal.type === 'MISSING'
              ? `Initiate an incremental crawl for all ${pendingDepts + failedDepts} missing/failed departments in ${selectedTerm}. Already-scraped departments will be bypassed.`
              : confirmModal.type === 'SINGLE_DEPT'
              ? `Initiate a targeted single-department scrape for ${confirmModal.deptCode} in ${selectedTerm}.`
              : `Initiate a full un-cached scrape of all ${totalDepts} departments in ${selectedTerm}.`
          }
          confirmLabel="[CONFIRM_EXECUTION]"
          cancelLabel="[ABORT]"
          onConfirm={handleConfirmAction}
          onCancel={() => setConfirmModal({ open: false, type: '', deptCode: null })}
        />
      )}
    </div>
  );
}
