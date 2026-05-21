import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Search,
  Filter,
  Download,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Info,
  Calendar,
  Layers,
  Compass,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
  X,
  Inbox,
  User,
  MapPin,
  Clock,
} from 'lucide-react';
import { useToast } from '../hooks/useToast';
import EmptyState from './EmptyState';

const BOLUM_ARRAY = [
  { code: 'ASIA', name: 'ASIAN STUDIES', val: 'ASIA&bolum=ASIAN+STUDIES' },
  { code: 'ATA', name: 'ATATURK INSTITUTE', val: 'ATA&bolum=ATATURK+INSTITUTE+FOR+MODERN+TURKISH+HISTORY' },
  { code: 'CHE', name: 'CHEMICAL ENGINEERING', val: 'CHE&bolum=CHEMICAL+ENGINEERING' },
  { code: 'CHEM', name: 'CHEMISTRY', val: 'CHEM&bolum=CHEMISTRY' },
  { code: 'CE', name: 'CIVIL ENGINEERING', val: 'CE&bolum=CIVIL+ENGINEERING' },
  { code: 'CMPE', name: 'COMPUTER ENGINEERING', val: 'CMPE&bolum=COMPUTER+ENGINEERING' },
  { code: 'EC', name: 'ECONOMICS', val: 'EC&bolum=ECONOMICS' },
  { code: 'EE', name: 'ELECTRICAL ENGINEERING', val: 'EE&bolum=ELECTRICAL+%26+ELECTRONICS+ENGINEERING' },
  { code: 'HIST', name: 'HISTORY', val: 'HIST&bolum=HISTORY' },
  { code: 'IE', name: 'INDUSTRIAL ENGINEERING', val: 'IE&bolum=INDUSTRIAL+ENGINEERING' },
  { code: 'MATH', name: 'MATHEMATICS', val: 'MATH&bolum=MATHEMATICS' },
  { code: 'ME', name: 'MECHANICAL ENGINEERING', val: 'ME&bolum=MECHANICAL+ENGINEERING' },
  { code: 'BIO', name: 'MOLECULAR BIOLOGY', val: 'BIO&bolum=MOLECULAR+BIOLOGY+%26+GENETICS' },
  { code: 'PHIL', name: 'PHILOSOPHY', val: 'PHIL&bolum=PHILOSOPHY' },
  { code: 'PHYS', name: 'PHYSICS', val: 'PHYS&bolum=PHYSICS' },
  { code: 'POLS', name: 'POLITICAL SCIENCE', val: 'POLS&bolum=POLITICAL+SCIENCE%26INTERNATIONAL+RELATIONS' },
  { code: 'PSY', name: 'PSYCHOLOGY', val: 'PSY&bolum=PSYCHOLOGY' },
  { code: 'SOC', name: 'SOCIOLOGY', val: 'SOC&bolum=SOCIOLOGY' },
  { code: 'SWE', name: 'SOFTWARE ENGINEERING', val: 'SWE&bolum=SOFTWARE+ENGINEERING' },
];

const COLUMNS = [
  { key: 'term', label: 'Semester', width: '12%' },
  { key: 'department', label: 'Dept', width: '8%' },
  { key: 'course_code', label: 'Course Code', width: '12%' },
  { key: 'section', label: 'Sec', width: '8%' },
  { key: 'course_name', label: 'Course Name', width: '25%' },
  { key: 'instructor', label: 'Instructor', width: '18%' },
  { key: 'slots', label: 'Meetings', width: '17%', sortable: false },
];

export default function CourseData({ token }) {
  const toast = useToast();

  // Drop-down data
  const [terms, setTerms] = useState([]);
  const [depts, setDepts] = useState([]);

  // Filters
  const [selectedTerm, setSelectedTerm] = useState('');
  const [selectedDept, setSelectedDept] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDay, setSelectedDay] = useState('');

  // Sorting (client-side)
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState('asc');

  // Data state
  const [courses, setCourses] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit] = useState(50);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedCourse, setExpandedCourse] = useState(null);

  // Link Generator
  const [linkYear, setLinkYear] = useState(new Date().getFullYear() - 1);
  const [linkTerm, setLinkTerm] = useState('1');
  const [linkDeptVal, setLinkDeptVal] = useState(BOLUM_ARRAY[5].val);

  // Debounced search
  const debounceRef = useRef(null);
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearchTerm(searchInput);
      setPage(1);
    }, 250);
    return () => clearTimeout(debounceRef.current);
  }, [searchInput]);

  // Fetch meta
  useEffect(() => {
    const fetchMetaData = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const [termsRes, deptsRes] = await Promise.all([
          fetch('/api/terms', { headers }),
          fetch('/api/departments', { headers }),
        ]);
        if (termsRes.ok) {
          const termsData = await termsRes.json();
          setTerms(termsData);
          if (termsData.length > 0) setSelectedTerm(termsData[0]);
        }
        if (deptsRes.ok) {
          setDepts(await deptsRes.json());
        }
      } catch (err) {
        console.error('Failed to load terms/departments list:', err);
      }
    };
    fetchMetaData();
  }, [token]);

  const fetchCourses = async () => {
    setLoading(true);
    setError('');
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const queryParams = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString(),
      });
      if (selectedTerm) queryParams.append('term', selectedTerm);
      if (selectedDept) queryParams.append('department', selectedDept);
      if (searchTerm) queryParams.append('search', searchTerm);
      if (selectedDay) queryParams.append('day', selectedDay);

      const res = await fetch(`/api/courses?${queryParams.toString()}`, { headers });
      if (!res.ok) throw new Error('Failed to fetch courses.');
      const data = await res.json();
      setCourses(data.courses);
      setTotal(data.total);
      setTotalPages(data.pages);
    } catch (err) {
      setError(err.message || 'Failed to load courses.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCourses();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, limit, selectedTerm, selectedDept, selectedDay, searchTerm, token]);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const sortedCourses = useMemo(() => {
    if (!sortKey) return courses;
    const arr = [...courses];
    arr.sort((a, b) => {
      const av = a[sortKey] ?? '';
      const bv = b[sortKey] ?? '';
      const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return arr;
  }, [courses, sortKey, sortDir]);

  const handleOpenOfficialSchedule = () => {
    const donem = `${linkYear}/${linkYear + 1}-${linkTerm}`;
    const urlString = `https://registration.boun.edu.tr/scripts/sch.asp?donem=${donem}&kisaadi=${linkDeptVal}`;
    window.open(urlString, '_blank');
  };

  const handleLocalSearchSchedule = () => {
    const matchedDept = BOLUM_ARRAY.find((b) => b.val === linkDeptVal);
    const donem = `${linkYear}/${linkYear + 1}-${linkTerm}`;
    setSelectedTerm(donem);
    if (matchedDept) setSelectedDept(matchedDept.code);
    setPage(1);
  };

  const handleExportCSV = () => {
    if (courses.length === 0) {
      toast.info('No data available to export.');
      return;
    }
    let csvContent = 'data:text/csv;charset=utf-8,';
    csvContent += 'Term,Department,Course Code,Section,Course Name,Instructor,Credits,ECTS,Delivery Method,Meeting Day,Meeting Hour,Room\n';
    courses.forEach((c) => {
      const baseInfo = `"${c.term}","${c.department}","${c.course_code}","${c.section}","${c.course_name.replace(/"/g, '""')}","${c.instructor.replace(/"/g, '""')}","${c.credits}","${c.ects}","${c.delivery_method}"`;
      if (c.slots && c.slots.length > 0) {
        c.slots.forEach((s) => {
          csvContent += `${baseInfo},"${s.day}","${s.hour}","${s.room}"\n`;
        });
      } else {
        csvContent += `${baseInfo},"TBA","TBA","TBA"\n`;
      }
    });
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', 'scraped_courses_export.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success(`Exported ${courses.length} courses to CSV.`);
  };

  const years = useMemo(() => {
    const arr = [];
    const currentYear = new Date().getFullYear();
    for (let y = 1970; y <= currentYear; y++) arr.unshift(y);
    return arr;
  }, []);

  const clearSearch = () => {
    setSearchInput('');
  };

  return (
    <div className="flex-1 p-4 sm:p-8 overflow-y-auto space-y-8 animate-fade-in relative">
      <div className="bg-glow-violet top-[15%] right-[5%]" aria-hidden="true" />

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gradient tracking-tight">Course Database Explorer</h1>
          <p className="text-[hsl(var(--text-secondary))] text-sm mt-1">Exhaustively filter, look up, and export historical schedules details</p>
        </div>

        <button onClick={handleExportCSV} className="btn-secondary self-start md:self-auto text-xs py-2.5 flex items-center gap-2">
          <Download size={14} aria-hidden="true" />
          Export CSV
        </button>
      </div>

      {/* Easy Access Generator */}
      <section className="glass-panel p-6 bg-gradient-to-tr from-[hsla(var(--accent-primary)/0.04)] to-transparent border-[hsla(var(--accent-primary)/0.15)] relative" aria-labelledby="easy-access-heading">
        <h2 id="easy-access-heading" className="text-base font-bold mb-1 flex items-center gap-2">
          <Compass size={18} className="text-[hsl(var(--accent-primary))]" aria-hidden="true" />
          Easy Schedule Access Hub
        </h2>
        <p className="text-xs text-[hsl(var(--text-secondary))] mb-6">Jump to live official schedules or search locally</p>

        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-4 gap-4 items-end">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="link-year" className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Academic Year</label>
            <select id="link-year" value={linkYear} onChange={(e) => setLinkYear(parseInt(e.target.value))} className="glass-select text-xs py-2.5">
              {years.map((y) => (
                <option key={y} value={y}>{y} / {y + 1}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="link-term" className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Semester</label>
            <select id="link-term" value={linkTerm} onChange={(e) => setLinkTerm(e.target.value)} className="glass-select text-xs py-2.5">
              <option value="1">1 (Fall)</option>
              <option value="2">2 (Spring)</option>
              <option value="3">3 (Summer)</option>
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="link-dept" className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Department</label>
            <select id="link-dept" value={linkDeptVal} onChange={(e) => setLinkDeptVal(e.target.value)} className="glass-select text-xs py-2.5">
              {BOLUM_ARRAY.map((b) => (
                <option key={b.code} value={b.val}>{b.code} - {b.name}</option>
              ))}
            </select>
          </div>

          <div className="flex gap-2 lg:col-span-1 sm:col-span-3">
            <button onClick={handleLocalSearchSchedule} className="flex-1 btn-primary text-xs py-2.5 px-3">Search Locally</button>
            <button onClick={handleOpenOfficialSchedule} className="flex-1 btn-secondary text-xs py-2.5 px-3 flex items-center justify-center gap-1.5">
              Official Link
              <ExternalLink size={12} aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>

      {/* Advanced Search */}
      <section className="glass-panel p-4 sm:p-6 space-y-6" aria-labelledby="filters-heading">
        <div className="flex items-center justify-between border-b border-[hsla(var(--glass-border))] pb-4">
          <h2 id="filters-heading" className="text-base font-bold flex items-center gap-2">
            <Filter size={18} className="text-[hsl(var(--accent-secondary))]" aria-hidden="true" />
            Database Filters
          </h2>
          <span className="text-xs text-[hsl(var(--text-secondary))] font-medium hidden sm:inline" aria-live="polite">
            Found: <strong className="text-[hsl(var(--text-primary))]">{total.toLocaleString()}</strong>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="filter-search" className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Keyword Search</label>
            <div className="relative flex items-center">
              <span className="absolute left-3 text-[hsl(var(--text-muted))]" aria-hidden="true"><Search size={15} /></span>
              <input
                id="filter-search"
                type="text"
                placeholder="Code, title, instructor..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="glass-input text-xs pl-9 pr-9 w-full py-2.5"
                aria-label="Search courses"
              />
              {searchInput && (
                <button
                  type="button"
                  onClick={clearSearch}
                  aria-label="Clear search"
                  className="absolute right-2 p-1 text-[hsl(var(--text-muted))] hover:text-[hsl(var(--text-primary))] rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-primary))]"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="filter-dept" className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Department</label>
            <select id="filter-dept" value={selectedDept} onChange={(e) => { setSelectedDept(e.target.value); setPage(1); }} className="glass-select text-xs py-2.5">
              <option value="">All Departments</option>
              {depts.map((d) => (<option key={d} value={d}>{d}</option>))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="filter-term" className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Academic Semester</label>
            <select id="filter-term" value={selectedTerm} onChange={(e) => { setSelectedTerm(e.target.value); setPage(1); }} className="glass-select text-xs py-2.5">
              <option value="">All Semesters</option>
              {terms.map((t) => (<option key={t} value={t}>{t}</option>))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="filter-day" className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Meeting Day</label>
            <select id="filter-day" value={selectedDay} onChange={(e) => { setSelectedDay(e.target.value); setPage(1); }} className="glass-select text-xs py-2.5">
              <option value="">All Days</option>
              <option value="M">Monday</option>
              <option value="T">Tuesday</option>
              <option value="W">Wednesday</option>
              <option value="Th">Thursday</option>
              <option value="F">Friday</option>
              <option value="St">Saturday</option>
            </select>
          </div>
        </div>

        {/* Row count summary */}
        <div className="text-[11px] text-[hsl(var(--text-muted))] flex items-center justify-between" aria-live="polite">
          <span>
            {loading
              ? 'Loading rows...'
              : error
              ? error
              : `Showing ${sortedCourses.length} of ${total.toLocaleString()} records`}
          </span>
          {sortKey && (
            <button
              type="button"
              onClick={() => { setSortKey(null); setSortDir('asc'); }}
              className="text-[hsl(var(--text-muted))] hover:text-[hsl(var(--text-primary))] underline"
            >
              Clear sort
            </button>
          )}
        </div>

        {/* Data list / table */}
        <div className="relative min-h-[300px]">
          {loading && (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-[hsla(var(--bg-secondary)/0.5)] backdrop-blur-sm rounded-xl">
              <div className="flex flex-col items-center gap-3" role="status">
                <svg className="animate-spin h-7 w-7 text-[hsl(var(--accent-primary))]" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span className="text-xs text-[hsl(var(--text-secondary))]">Syncing database...</span>
              </div>
            </div>
          )}

          {/* Desktop Table */}
          <div className="hidden lg:block premium-table-container max-h-[60vh] overflow-auto">
            <table className="premium-table">
              <thead className="sticky-header">
                <tr>
                  {COLUMNS.map((col) => {
                    const isSorted = sortKey === col.key;
                    const sortable = col.sortable !== false;
                    return (
                      <th
                        key={col.key}
                        style={{ width: col.width }}
                        className={sortable ? 'sortable' : ''}
                        aria-sort={isSorted ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                      >
                        {sortable ? (
                          <button
                            type="button"
                            onClick={() => handleSort(col.key)}
                            aria-label={`Sort by ${col.label}`}
                          >
                            <span>{col.label}</span>
                            {isSorted ? (
                              sortDir === 'asc' ? (
                                <ArrowUp size={12} aria-hidden="true" />
                              ) : (
                                <ArrowDown size={12} aria-hidden="true" />
                              )
                            ) : (
                              <ArrowUpDown size={12} className="opacity-40" aria-hidden="true" />
                            )}
                          </button>
                        ) : (
                          col.label
                        )}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {sortedCourses.length > 0 ? (
                  sortedCourses.map((course) => (
                    <CourseRow 
                      key={course.id} 
                      course={course} 
                      isExpanded={expandedCourse === course.id} 
                      onToggle={() => setExpandedCourse(expandedCourse === course.id ? null : course.id)} 
                    />
                  ))
                ) : !loading ? (
                  <tr>
                    <td colSpan={7}>
                      <EmptyState 
                        title="No Courses Found" 
                        description="Adjust your filters or try a different keyword to locate the schedule you're looking for."
                        icon={Inbox}
                        action={searchTerm || selectedDay || selectedDept ? {
                          label: "Clear All Filters",
                          onClick: () => { setSearchInput(''); setSelectedDay(''); setSelectedDept(''); }
                        } : null}
                      />
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>

          {/* Mobile Card List */}
          <div className="lg:hidden space-y-4">
            {sortedCourses.length > 0 ? (
              sortedCourses.map((course) => (
                <CourseCard 
                  key={course.id} 
                  course={course} 
                  isExpanded={expandedCourse === course.id} 
                  onToggle={() => setExpandedCourse(expandedCourse === course.id ? null : course.id)} 
                />
              ))
            ) : !loading ? (
              <EmptyState 
                title="No Results Matching Filters" 
                description="We couldn't find any courses matching your search. Try broadening your criteria."
                icon={Inbox}
                action={searchTerm || selectedDay || selectedDept ? {
                  label: "Reset Search",
                  onClick: () => { setSearchInput(''); setSelectedDay(''); setSelectedDept(''); }
                } : null}
              />
            ) : null}
          </div>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-4 border-t border-[hsla(var(--glass-border))]">
            <span className="text-xs text-[hsl(var(--text-secondary))]">
              Page <strong className="text-[hsl(var(--text-primary))]">{page}</strong> of{' '}
              <strong className="text-[hsl(var(--text-primary))]">{totalPages}</strong>
            </span>

            <div className="flex gap-2">
              <button disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1">
                <ChevronLeft size={14} aria-hidden="true" />
                Prev
              </button>
              <button disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1">
                Next
                <ChevronRight size={14} aria-hidden="true" />
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function CourseRow({ course, isExpanded, onToggle }) {
  return (
    <React.Fragment>
      <tr
        onClick={onToggle}
        className={`cursor-pointer transition-all ${isExpanded ? 'bg-[hsla(var(--bg-tertiary)/0.6)]' : ''}`}
      >
        <td className="font-semibold text-xs text-[hsl(var(--text-secondary))]">{course.term}</td>
        <td className="font-bold text-xs text-[hsl(var(--accent-primary))]">{course.department}</td>
        <td className="font-semibold text-xs">{course.course_code}</td>
        <td className="text-xs">{course.section}</td>
        <td className="font-medium text-[13px]">{course.course_name}</td>
        <td className="text-xs text-[hsl(var(--text-secondary))] truncate max-w-[150px]">{course.instructor}</td>
        <td>
          <MeetingBadges slots={course.slots} />
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={7} className="bg-[hsla(var(--bg-tertiary)/0.35)] px-8 py-6 border-b border-[hsla(var(--glass-border))]">
            <ExpandedDetails course={course} />
          </td>
        </tr>
      )}
    </React.Fragment>
  );
}

function CourseCard({ course, isExpanded, onToggle }) {
  return (
    <div className={`glass-panel overflow-hidden transition-all ${isExpanded ? 'ring-1 ring-[hsl(var(--accent-primary))]' : ''}`}>
      <div className="p-4 cursor-pointer" onClick={onToggle}>
        <div className="flex justify-between items-start mb-2">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-[hsl(var(--text-muted))] uppercase tracking-wider mb-0.5">{course.term} • {course.department}</span>
            <h3 className="text-sm font-bold text-[hsl(var(--text-primary))]">{course.course_code}.{course.section}</h3>
          </div>
          <span className="text-[10px] bg-[hsla(var(--accent-primary)/0.1)] text-[hsl(var(--accent-primary))] px-2 py-0.5 rounded font-bold">{course.credits} CR</span>
        </div>
        <p className="text-xs font-medium text-[hsl(var(--text-secondary))] mb-3 leading-snug">{course.course_name}</p>
        <div className="flex items-center gap-2 text-[11px] text-[hsl(var(--text-muted))] mb-4">
          <User size={12} />
          <span className="truncate">{course.instructor}</span>
        </div>
        <MeetingBadges slots={course.slots} />
      </div>
      {isExpanded && (
        <div className="bg-[hsla(var(--bg-tertiary)/0.4)] p-4 border-t border-[hsla(var(--glass-border))]">
          <ExpandedDetails course={course} />
        </div>
      )}
    </div>
  );
}

function MeetingBadges({ slots }) {
  if (!slots || slots.length === 0) {
    return <span className="text-[10px] text-[hsl(var(--text-muted))] uppercase">TBA</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {slots.map((s, idx) => (
        <span
          key={idx}
          className="px-2 py-0.5 text-[10px] font-semibold bg-[hsla(var(--accent-primary)/0.08)] border border-[hsla(var(--accent-primary)/0.15)] text-[hsl(var(--text-primary))] rounded-md"
        >
          {s.day} {s.hour} {s.room && `(${s.room})`}
        </span>
      ))}
    </div>
  );
}

function ExpandedDetails({ course }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-fade-in">
      <div className="space-y-4">
        <h4 className="font-bold text-xs uppercase tracking-widest text-[hsl(var(--text-primary))] flex items-center gap-2">
          <Layers size={14} className="text-[hsl(var(--accent-primary))]" aria-hidden="true" />
          Course Specs
        </h4>
        <div className="space-y-2">
          <DetailItem label="Credits" value={course.credits} />
          <DetailItem label="ECTS" value={course.ects} />
          <DetailItem label="Method" value={course.delivery_method || 'Traditional'} />
          <DetailItem label="SL" value={course.sl} />
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="font-bold text-xs uppercase tracking-widest text-[hsl(var(--text-primary))] flex items-center gap-2">
          <Calendar size={14} className="text-[hsl(var(--accent-secondary))]" aria-hidden="true" />
          Examination
        </h4>
        <div className="space-y-2">
          <DetailItem label="Exam Date" value={course.exam_date} icon={Clock} />
          <DetailItem label="Location" value={course.exam_location} icon={MapPin} />
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="font-bold text-xs uppercase tracking-widest text-[hsl(var(--text-primary))] flex items-center gap-2">
          <Info size={14} className="text-[hsl(var(--color-info))]" aria-hidden="true" />
          Relations
        </h4>
        <div className="space-y-2">
          <DetailItem label="Required For" value={course.required_for} />
          <DetailItem label="Shared With" value={course.departments} />
        </div>
      </div>
    </div>
  );
}

function DetailItem({ label, value, icon: Icon }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] text-[hsl(var(--text-muted))] font-bold uppercase">{label}</span>
      <div className="flex items-center gap-1.5 text-xs text-[hsl(var(--text-secondary))] font-medium">
        {Icon && <Icon size={12} className="opacity-50" />}
        <span>{value || 'Not Specified'}</span>
      </div>
    </div>
  );
}
