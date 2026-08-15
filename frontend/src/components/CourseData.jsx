import React, { useState, useEffect, useCallback } from 'react';
import {
  Search,
  Download,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  X,
  Clock,
} from 'lucide-react';
import { api } from '../api/client';
import { useMountedRef } from '../hooks/useSafeAsync';
import { useToast } from '../hooks/useToast';

export default function CourseData() {
  const showToast = useToast();
  const isMountedRef = useMountedRef();

  const [courses, setCourses] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedTerm, setSelectedTerm] = useState('');
  const [selectedDept, setSelectedDept] = useState('');
  const [selectedDay, setSelectedDay] = useState('');

  // Lookup options
  const [terms, setTerms] = useState([]);
  const [departments, setDepartments] = useState([]);

  // Detail Modal
  const [activeCourse, setActiveCourse] = useState(null);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [search]);

  // Load lookup options
  useEffect(() => {
    Promise.all([api.getTerms().catch(() => []), api.getDepartments().catch(() => [])]).then(
      ([termsRes, deptsRes]) => {
        if (isMountedRef.current) {
          setTerms(termsRes);
          setDepartments(deptsRes);
        }
      }
    );
  }, [isMountedRef]);

  // Fetch courses
  const fetchCourses = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getCourses({
        term: selectedTerm,
        department: selectedDept,
        search: debouncedSearch,
        day: selectedDay,
        page,
        limit: 50,
      });

      if (isMountedRef.current) {
        setCourses(res.courses || []);
        setTotal(res.total || 0);
        setPages(res.pages || 1);
      }
    } catch (err) {
      if (isMountedRef.current) {
        showToast(err.message || 'FAILED_TO_FETCH_COURSE_RECORDS', 'error');
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [selectedTerm, selectedDept, debouncedSearch, selectedDay, page, isMountedRef, showToast]);

  useEffect(() => {
    fetchCourses();
  }, [fetchCourses]);

  const daysList = ['M', 'T', 'W', 'Th', 'F', 'Sa'];

  // CSV Exporter using Blob with UTF-8 BOM
  const exportCSV = () => {
    if (courses.length === 0) {
      showToast('NO_RECORDS_TO_EXPORT', 'error');
      return;
    }

    const headers = [
      'Term',
      'Department',
      'Course Code',
      'Section',
      'Course Title',
      'Instructor',
      'Credits',
      'ECTS',
      'Exam Location',
      'Exam Date',
    ];

    const rows = courses.map((c) => [
      `"${c.term || ''}"`,
      `"${c.department || ''}"`,
      `"${c.course_code || ''}"`,
      `"${c.section || ''}"`,
      `"${(c.course_name || '').replace(/"/g, '""')}"`,
      `"${(c.instructor || '').replace(/"/g, '""')}"`,
      `"${c.credits || ''}"`,
      `"${c.ects || ''}"`,
      `"${c.exam_location || ''}"`,
      `"${c.exam_date || ''}"`,
    ]);

    const csvContent = '\uFEFF' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `boun_courses_${selectedDept || 'all'}_${selectedTerm || 'all'}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    showToast('CSV_STREAM_DUMPED_SUCCESSFULLY', 'success');
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span className="led-indicator led-green" />
            <span style={{ color: 'var(--neon-green)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em' }}>
              SYS://DATABASE_INDEX
            </span>
          </div>
          <h1 className="glow-green" style={{ color: 'var(--neon-green)', fontSize: '20px', margin: 0 }}>
            /// COURSE_TIMETABLE_EXPLORER
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '4px' }}>
            Query indexed Boğaziçi course records, schedule slots, room assignments, and exam locations.
          </p>
        </div>

        <button
          onClick={exportCSV}
          disabled={courses.length === 0}
          className="btn-cyber btn-cyber-amber"
          style={{ fontSize: '11px', padding: '8px 16px' }}
        >
          <Download size={13} />
          <span>[&gt;&gt; DUMP_CSV_STREAM]</span>
        </button>
      </div>

      {/* Filter Controls Bar */}
      <div className="cyber-card" style={{ border: '1px solid var(--border-hard)', padding: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
          {/* Keyword Search */}
          <div style={{ position: 'relative' }}>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder=">> QUERY: code, name, prof..."
              className="cyber-input"
              style={{ paddingRight: search ? '28px' : '12px' }}
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                style={{
                  position: 'absolute',
                  right: '8px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                }}
              >
                <X size={13} />
              </button>
            )}
          </div>

          {/* Semester Selector */}
          <div>
            <select
              value={selectedTerm}
              onChange={(e) => {
                setSelectedTerm(e.target.value);
                setPage(1);
              }}
              className="cyber-select"
            >
              <option value="">ALL_SEMESTERS</option>
              {terms.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          {/* Department Selector */}
          <div>
            <select
              value={selectedDept}
              onChange={(e) => {
                setSelectedDept(e.target.value);
                setPage(1);
              }}
              className="cyber-select"
            >
              <option value="">ALL_DEPARTMENTS</option>
              {departments.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          {/* Day Filters */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-hard)',
              padding: '2px',
              gap: '2px',
            }}
          >
            <button
              onClick={() => {
                setSelectedDay('');
                setPage(1);
              }}
              style={{
                flex: 1,
                padding: '6px 4px',
                fontSize: '10px',
                fontWeight: 700,
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                background: selectedDay === '' ? 'var(--neon-green)' : 'transparent',
                color: selectedDay === '' ? 'var(--bg-void)' : 'var(--text-muted)',
              }}
            >
              ANY
            </button>
            {daysList.map((day) => (
              <button
                key={day}
                onClick={() => {
                  setSelectedDay(day);
                  setPage(1);
                }}
                style={{
                  padding: '6px 6px',
                  fontSize: '10px',
                  fontWeight: 700,
                  border: 'none',
                  cursor: 'pointer',
                  fontFamily: 'var(--font-mono)',
                  background: selectedDay === day ? 'var(--neon-green)' : 'transparent',
                  color: selectedDay === day ? 'var(--bg-void)' : 'var(--text-muted)',
                }}
              >
                {day}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Courses Data Grid / Table */}
      <div className="cyber-card" style={{ padding: 0, overflow: 'hidden', border: '1px solid var(--border-hard)' }}>
        {loading ? (
          <div style={{ padding: '48px 16px', textAlign: 'center', color: 'var(--neon-green)' }}>
            <span className="cursor-blink" style={{ fontSize: '12px', fontWeight: 700 }}>
              [&gt;&gt;] QUERYING_DATABASE_INDEX
            </span>
          </div>
        ) : courses.length === 0 ? (
          <div style={{ padding: '48px 16px', textAlign: 'center' }}>
            <BookOpen size={32} style={{ color: 'var(--border-hard)', margin: '0 auto 12px auto' }} />
            <div style={{ color: 'var(--text-primary)', fontSize: '12px', fontWeight: 700 }}>
              [STATUS: NO_RECORDS_FOUND]
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: '4px' }}>
              Adjust search query tokens or department filter.
            </div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="cyber-table">
              <thead>
                <tr>
                  <th>CODE / SEC</th>
                  <th>COURSE_TITLE</th>
                  <th>INSTRUCTOR</th>
                  <th>SCHEDULE_SLOTS</th>
                  <th>CREDITS</th>
                  <th style={{ textAlign: 'right' }}>ACTION</th>
                </tr>
              </thead>
              <tbody>
                {courses.map((course) => (
                  <tr
                    key={course.id}
                    onClick={() => setActiveCourse(course)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <span style={{ color: 'var(--neon-green)', fontWeight: 800 }}>
                        {course.course_code}
                      </span>
                      <span className="cyber-badge cyber-badge-cyan" style={{ marginLeft: '6px' }}>
                        .{course.section}
                      </span>
                    </td>
                    <td style={{ maxWidth: '260px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-primary)' }}>
                      {course.course_name}
                    </td>
                    <td style={{ whiteSpace: 'nowrap', color: 'var(--text-secondary)' }}>
                      {course.instructor || 'TBA'}
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {course.slots && course.slots.length > 0 ? (
                          course.slots.map((s, idx) => (
                            <span
                              key={idx}
                              style={{
                                padding: '2px 5px',
                                background: 'var(--bg-primary)',
                                border: '1px solid var(--border-dim)',
                                color: 'var(--neon-amber)',
                                fontSize: '10px',
                              }}
                            >
                              {s.day} {s.hour} ({s.room || 'TBA'})
                            </span>
                          ))
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>--</span>
                        )}
                      </div>
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{course.credits || '-'} Cr</span>
                      {course.ects && <span style={{ color: 'var(--text-muted)', marginLeft: '4px' }}>({course.ects} E)</span>}
                    </td>
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveCourse(course);
                        }}
                        className="btn-cyber"
                        style={{ fontSize: '9px', padding: '4px 8px' }}
                      >
                        [&gt;&gt;]
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        <div
          style={{
            padding: '10px 16px',
            background: 'var(--bg-tertiary)',
            borderTop: '1px solid var(--border-hard)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
            RECORDS: <strong style={{ color: 'var(--text-primary)' }}>{courses.length}</strong> /{' '}
            <strong style={{ color: 'var(--neon-green)' }}>{total.toLocaleString()}</strong>
          </span>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="btn-cyber"
              style={{ padding: '4px 8px', fontSize: '10px' }}
            >
              <ChevronLeft size={12} />
            </button>
            <span style={{ color: 'var(--neon-amber)', fontSize: '11px', fontWeight: 700, padding: '0 4px' }}>
              PAGE {page} / {pages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page >= pages}
              className="btn-cyber"
              style={{ padding: '4px 8px', fontSize: '10px' }}
            >
              <ChevronRight size={12} />
            </button>
          </div>
        </div>
      </div>

      {/* Course Detail Modal Drawer */}
      {activeCourse && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(5, 5, 8, 0.85)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
          }}
        >
          <div
            className="cyber-card animate-fade-in"
            style={{
              width: '100%',
              maxWidth: '600px',
              border: '2px solid var(--neon-green)',
              padding: '24px',
              maxHeight: '90vh',
              overflowY: 'auto',
              boxShadow: '8px 8px 0 rgba(0, 0, 0, 0.9)',
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <span className="cyber-badge cyber-badge-green">{activeCourse.department}</span>
                  <span style={{ color: 'var(--neon-amber)', fontSize: '10px', fontWeight: 700 }}>{activeCourse.term}</span>
                </div>
                <h2 className="glow-green" style={{ color: 'var(--neon-green)', fontSize: '18px', margin: 0 }}>
                  {activeCourse.course_code} - Sec {activeCourse.section}
                </h2>
                <div style={{ color: 'var(--text-primary)', fontSize: '12px', marginTop: '4px' }}>
                  {activeCourse.course_name}
                </div>
              </div>

              <button
                onClick={() => setActiveCourse(null)}
                className="btn-cyber"
                style={{ padding: '4px 8px' }}
              >
                <X size={14} />
              </button>
            </div>

            {/* Course Properties */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                gap: '8px',
                padding: '12px',
                background: 'var(--bg-primary)',
                border: '1px solid var(--border-hard)',
                marginBottom: '16px',
              }}
            >
              <div>
                <span style={{ color: 'var(--neon-amber)', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase' }}>
                  INSTRUCTOR:
                </span>
                <div style={{ fontSize: '11px', color: 'var(--text-primary)', marginTop: '2px' }}>
                  {activeCourse.instructor || 'TBA'}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--neon-amber)', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase' }}>
                  CREDITS / ECTS:
                </span>
                <div style={{ fontSize: '11px', color: 'var(--text-primary)', marginTop: '2px' }}>
                  {activeCourse.credits || '-'} Cr ({activeCourse.ects || '-'} ECTS)
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--neon-amber)', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase' }}>
                  EXAM_LOCATION:
                </span>
                <div style={{ fontSize: '11px', color: 'var(--text-primary)', marginTop: '2px' }}>
                  {activeCourse.exam_location || 'TBA'}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--neon-amber)', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase' }}>
                  DELIVERY_MODE:
                </span>
                <div style={{ fontSize: '11px', color: 'var(--text-primary)', marginTop: '2px' }}>
                  {activeCourse.delivery_method || 'N/A'}
                </div>
              </div>
            </div>

            {/* Slots List */}
            <div style={{ marginBottom: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                <Clock size={13} style={{ color: 'var(--neon-green)' }} />
                <span style={{ color: 'var(--neon-green)', fontSize: '11px', fontWeight: 700 }}>
                  SCHEDULE_TIMETABLE_SLOTS
                </span>
              </div>
              {activeCourse.slots && activeCourse.slots.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '8px' }}>
                  {activeCourse.slots.map((s, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '8px 10px',
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-hard)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ color: 'var(--neon-green)', fontSize: '11px', fontWeight: 700 }}>
                          {s.day} Period {s.hour}
                        </div>
                        <div style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
                          {s.slot_title || 'Lecture'}
                        </div>
                      </div>
                      <span style={{ color: 'var(--neon-amber)', fontSize: '11px', fontWeight: 700 }}>
                        {s.room || 'TBA'}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: 'var(--text-muted)', fontSize: '11px', fontStyle: 'italic' }}>
                  No slot telemetry recorded for this course.
                </div>
              )}
            </div>

            {/* Dismiss Button */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--border-hard)', paddingTop: '12px' }}>
              <button
                onClick={() => setActiveCourse(null)}
                className="btn-cyber btn-cyber-primary"
                style={{ fontSize: '10px', padding: '6px 14px' }}
              >
                [&gt;&gt; DISMISS_INSPECTOR]
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
