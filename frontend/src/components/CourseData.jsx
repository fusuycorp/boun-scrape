import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Search,
  Filter,
  Download,
  Calendar,
  Building2,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  X,
  User,
  MapPin,
  Clock,
  Info,
  ExternalLink,
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
        showToast(err.message || 'Failed to fetch course records', 'error');
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
      showToast('No course records available to export', 'error');
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

    showToast('CSV dataset exported successfully!', 'success');
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Course Database Explorer
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Search indexed Boğaziçi course records, schedule slots, instructors, and examination schedules.
          </p>
        </div>

        <button
          onClick={exportCSV}
          disabled={courses.length === 0}
          className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-pink-600 hover:from-violet-500 hover:to-pink-500 text-white font-bold text-xs shadow-lg transition-all duration-200 hover:scale-[1.02] disabled:opacity-50"
        >
          <Download className="w-4 h-4" />
          <span>Export CSV</span>
        </button>
      </div>

      {/* Filter Controls Bar */}
      <div className="p-5 rounded-2xl glass-panel border border-white/10 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Keyword Search */}
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3.5 top-3.5 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search code, name, instructor..."
              className="w-full pl-10 pr-4 py-2.5 rounded-xl glass-input text-white text-xs placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-3 top-3 text-slate-400 hover:text-white"
              >
                <X className="w-3.5 h-3.5" />
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
              className="w-full px-3.5 py-2.5 rounded-xl glass-select text-white text-xs focus:outline-none focus:ring-2 focus:ring-violet-500/50"
            >
              <option value="">All Semesters</option>
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
              className="w-full px-3.5 py-2.5 rounded-xl glass-select text-white text-xs focus:outline-none focus:ring-2 focus:ring-violet-500/50"
            >
              <option value="">All Departments</option>
              {departments.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          {/* Day Filters */}
          <div className="flex items-center gap-1 bg-slate-900/60 p-1 rounded-xl border border-white/5">
            <button
              onClick={() => {
                setSelectedDay('');
                setPage(1);
              }}
              className={`flex-1 py-1.5 rounded-lg text-[11px] font-bold transition-colors ${
                selectedDay === '' ? 'bg-violet-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Any Day
            </button>
            {daysList.map((day) => (
              <button
                key={day}
                onClick={() => {
                  setSelectedDay(day);
                  setPage(1);
                }}
                className={`w-7 py-1.5 rounded-lg text-[11px] font-bold transition-colors ${
                  selectedDay === day ? 'bg-violet-600 text-white' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {day}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Courses Data Grid / Table */}
      <div className="rounded-2xl glass-panel border border-white/10 overflow-hidden shadow-xl">
        {loading ? (
          <div className="p-12 text-center text-slate-400 flex flex-col items-center gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin" />
            <span className="text-xs font-medium">Querying course database...</span>
          </div>
        ) : courses.length === 0 ? (
          <div className="p-12 text-center text-slate-400 space-y-2">
            <BookOpen className="w-10 h-10 mx-auto text-slate-600" />
            <p className="text-sm font-bold text-white">No Courses Found</p>
            <p className="text-xs text-slate-500">Try adjusting your filters or search terms.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/80 text-slate-400 font-bold uppercase tracking-wider border-b border-white/10">
                <tr>
                  <th className="py-3.5 px-4">Code / Sec</th>
                  <th className="py-3.5 px-4">Course Title</th>
                  <th className="py-3.5 px-4">Instructor</th>
                  <th className="py-3.5 px-4">Schedule Slots</th>
                  <th className="py-3.5 px-4">Credits</th>
                  <th className="py-3.5 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {courses.map((course) => (
                  <tr
                    key={course.id}
                    className="hover:bg-white/5 transition-colors group cursor-pointer"
                    onClick={() => setActiveCourse(course)}
                  >
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <span className="font-extrabold text-white group-hover:text-violet-300 transition-colors">
                        {course.course_code}
                      </span>
                      <span className="ml-1.5 px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 text-[10px] font-bold border border-violet-500/20">
                        {course.section}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 max-w-xs truncate font-medium text-slate-200">
                      {course.course_name}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap text-slate-400">
                      {course.instructor || 'TBA'}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex flex-wrap gap-1">
                        {course.slots && course.slots.length > 0 ? (
                          course.slots.map((s, idx) => (
                            <span
                              key={idx}
                              className="px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-white/10 text-[10px] font-mono"
                            >
                              {s.day} {s.hour} ({s.room || 'TBA'})
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-500 text-[11px] italic">No slots</span>
                        )}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <span className="font-bold text-slate-300">{course.credits || '-'} Cr</span>
                      {course.ects && <span className="ml-1 text-slate-500">({course.ects} ECTS)</span>}
                    </td>
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveCourse(course);
                        }}
                        className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-violet-600 text-slate-200 hover:text-white font-bold text-[11px] transition-colors"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        <div className="px-5 py-4 bg-slate-950/60 border-t border-white/10 flex items-center justify-between">
          <span className="text-xs text-slate-400">
            Showing <strong className="text-white">{courses.length}</strong> of{' '}
            <strong className="text-white">{total.toLocaleString()}</strong> courses
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-2 rounded-xl glass-panel text-slate-300 hover:text-white disabled:opacity-30"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs font-bold text-slate-300 px-2">
              Page {page} of {pages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page >= pages}
              className="p-2 rounded-xl glass-panel text-slate-300 hover:text-white disabled:opacity-30"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Course Detail Modal Drawer */}
      {activeCourse && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-fade-in">
          <div className="w-full max-w-2xl rounded-3xl glass-panel p-6 sm:p-8 border border-white/10 shadow-2xl space-y-6 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2.5 py-0.5 rounded-full bg-violet-500/20 text-violet-300 text-xs font-bold border border-violet-500/30">
                    {activeCourse.department}
                  </span>
                  <span className="text-xs text-slate-400 font-semibold">{activeCourse.term}</span>
                </div>
                <h2 className="text-2xl font-extrabold text-white">
                  {activeCourse.course_code} - Sec {activeCourse.section}
                </h2>
                <p className="text-sm font-medium text-slate-300 mt-1">{activeCourse.course_name}</p>
              </div>

              <button
                onClick={() => setActiveCourse(null)}
                className="p-2 rounded-xl glass-panel text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Course Properties */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 rounded-2xl bg-slate-900/60 border border-white/5">
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">Instructor</span>
                <p className="text-xs font-bold text-white mt-0.5">{activeCourse.instructor || 'TBA'}</p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">Credits / ECTS</span>
                <p className="text-xs font-bold text-white mt-0.5">
                  {activeCourse.credits || '-'} Cr ({activeCourse.ects || '-'} ECTS)
                </p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">Exam Location</span>
                <p className="text-xs font-bold text-white mt-0.5">{activeCourse.exam_location || 'TBA'}</p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">Delivery</span>
                <p className="text-xs font-bold text-white mt-0.5">{activeCourse.delivery_method || 'N/A'}</p>
              </div>
            </div>

            {/* Slots List */}
            <div>
              <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                <Clock className="w-4 h-4 text-violet-400" />
                Schedule Timetable Slots
              </h3>
              {activeCourse.slots && activeCourse.slots.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {activeCourse.slots.map((s, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-slate-900/80 border border-white/5 flex items-center justify-between"
                    >
                      <div>
                        <span className="text-xs font-extrabold text-violet-300">
                          {s.day} Period {s.hour}
                        </span>
                        <p className="text-[11px] text-slate-400 mt-0.5">{s.slot_title || 'Lecture'}</p>
                      </div>
                      <span className="px-2.5 py-1 rounded-lg bg-slate-800 text-slate-200 text-xs font-mono font-bold">
                        {s.room || 'TBA'}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic">No slot information recorded for this course.</p>
              )}
            </div>

            {/* Close Button */}
            <div className="pt-4 border-t border-white/10 flex justify-end">
              <button
                onClick={() => setActiveCourse(null)}
                className="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold transition-colors"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
