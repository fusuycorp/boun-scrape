import React, { useEffect, useState } from 'react';
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
  MapPin,
  Clock,
  Compass
} from 'lucide-react';

export default function CourseData({ token }) {
  // Lists for drop-downs
  const [terms, setTerms] = useState([]);
  const [depts, setDepts] = useState([]);
  
  // Dynamic filter state
  const [selectedTerm, setSelectedTerm] = useState('');
  const [selectedDept, setSelectedDept] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDay, setSelectedDay] = useState('');
  
  // Data state
  const [courses, setCourses] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(50);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [expandedCourse, setExpandedCourse] = useState(null);

  // Link Generator Helper lists
  const bolumArray = [
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
    { code: 'SWE', name: 'SOFTWARE ENGINEERING', val: 'SWE&bolum=SOFTWARE+ENGINEERING' }
  ];

  // Helper variables for Link Generator
  const [linkYear, setLinkYear] = useState(new Date().getFullYear() - 1);
  const [linkTerm, setLinkTerm] = useState('1');
  const [linkDeptVal, setLinkDeptVal] = useState(bolumArray[5].val); // CMPE default

  // Populate drop-downs on component mount
  useEffect(() => {
    const fetchMetaData = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        
        const termsRes = await fetch('http://localhost:8000/api/terms', { headers });
        const termsData = await termsRes.json();
        setTerms(termsData);
        if (termsData.length > 0) setSelectedTerm(termsData[0]);

        const deptsRes = await fetch('http://localhost:8000/api/departments', { headers });
        const deptsData = await deptsRes.json();
        setDepts(deptsData);
      } catch (err) {
        console.error('Failed to load terms/departments list:', err);
      }
    };
    fetchMetaData();
  }, [token]);

  // Query database when parameters shift
  const fetchCourses = async () => {
    setLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const queryParams = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString()
      });
      
      if (selectedTerm) queryParams.append('term', selectedTerm);
      if (selectedDept) queryParams.append('department', selectedDept);
      if (searchTerm) queryParams.append('search', searchTerm);
      if (selectedDay) queryParams.append('day', selectedDay);

      const res = await fetch(`/api/courses?${queryParams.toString()}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setCourses(data.courses);
        setTotal(data.total);
        setTotalPages(data.pages);
      }
    } catch (err) {
      console.error('Error fetching courses list:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCourses();
  }, [page, limit, selectedTerm, selectedDept, selectedDay, token]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    fetchCourses();
  };

  // Launch official Bogazici Registration schedule URL
  const handleOpenOfficialSchedule = () => {
    const donem = `${linkYear}/${linkYear + 1}-${linkTerm}`;
    const urlString = `https://registration.boun.edu.tr/scripts/sch.asp?donem=${donem}&kisaadi=${linkDeptVal}`;
    window.open(urlString, '_blank');
  };

  // Auto search inside local grid matching the Link Generator choices
  const handleLocalSearchSchedule = () => {
    const matchedDept = bolumArray.find(b => b.val === linkDeptVal);
    const donem = `${linkYear}/${linkYear + 1}-${linkTerm}`;
    
    setSelectedTerm(donem);
    if (matchedDept) {
      setSelectedDept(matchedDept.code);
    }
    setPage(1);
  };

  // Export search results as CSV
  const handleExportCSV = () => {
    if (courses.length === 0) {
      alert('No data available to export.');
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
    link.setAttribute('download', `scraped_courses_export.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const years = [];
  const currentYear = new Date().getFullYear();
  for (let y = 1970; y <= currentYear; y++) {
    years.unshift(y);
  }

  return (
    <div className="flex-1 p-8 overflow-y-auto space-y-8 animate-fade-in relative">
      <div className="bg-glow-violet top-[15%] right-[5%]" />
      
      {/* Title */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-gradient tracking-tight">Course Database Explorer</h1>
          <p className="text-[hsl(var(--text-secondary))] text-sm mt-1">Exhaustively filter, look up, and export historical schedules details</p>
        </div>
        
        <button 
          onClick={handleExportCSV}
          className="btn-secondary self-start md:self-auto text-xs py-2.5 flex items-center gap-2"
        >
          <Download size={14} />
          Export Flattened CSV
        </button>
      </div>

      {/* SECTION 1: Upgraded Easy Access Schedule Link & Search Generator */}
      <div className="glass-panel p-6 bg-gradient-to-tr from-[hsla(var(--accent-primary)/0.04)] to-transparent border-[hsla(var(--accent-primary)/0.15)] relative">
        <h2 className="text-base font-bold mb-1 flex items-center gap-2">
          <Compass size={18} className="text-[hsl(var(--accent-primary))]" />
          Easy Schedule Access Hub
        </h2>
        <p className="text-xs text-[hsl(var(--text-secondary))] mb-6">Select parameters to search in our local database or jump directly to the live official schedules page</p>

        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-4 gap-4 items-end">
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Academic Year</label>
            <select 
              value={linkYear}
              onChange={(e) => setLinkYear(parseInt(e.target.value))}
              className="glass-select text-xs py-2.5"
            >
              {years.map(y => (
                <option key={y} value={y}>{y} / {y + 1}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Semester</label>
            <select 
              value={linkTerm}
              onChange={(e) => setLinkTerm(e.target.value)}
              className="glass-select text-xs py-2.5"
            >
              <option value="1">1 (Fall)</option>
              <option value="2">2 (Spring)</option>
              <option value="3">3 (Summer)</option>
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Department</label>
            <select 
              value={linkDeptVal}
              onChange={(e) => setLinkDeptVal(e.target.value)}
              className="glass-select text-xs py-2.5"
            >
              {bolumArray.map(b => (
                <option key={b.code} value={b.val}>{b.code} - {b.name}</option>
              ))}
            </select>
          </div>

          <div className="flex gap-2 lg:col-span-1 sm:col-span-3">
            <button 
              onClick={handleLocalSearchSchedule}
              className="flex-1 btn-primary text-xs py-2.5 px-3"
            >
              Search Locally
            </button>
            <button 
              onClick={handleOpenOfficialSchedule}
              className="flex-1 btn-secondary text-xs py-2.5 px-3 flex items-center justify-center gap-1.5"
            >
              Go Official Link
              <ExternalLink size={12} />
            </button>
          </div>
        </div>
      </div>

      {/* SECTION 2: Advanced Search Filter Panel */}
      <div className="glass-panel p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-[hsla(var(--glass-border))] pb-4">
          <h2 className="text-base font-bold flex items-center gap-2">
            <Filter size={18} className="text-[hsl(var(--accent-secondary))]" />
            Database Filters
          </h2>
          <span className="text-xs text-[hsl(var(--text-secondary))] font-medium">Matching courses found: <strong className="text-[hsl(var(--text-primary))]">{total.toLocaleString()}</strong></span>
        </div>

        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
          {/* Keyword Search */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Keyword Search</label>
            <div className="relative flex items-center">
              <span className="absolute left-3 text-[hsl(var(--text-muted))]">
                <Search size={15} />
              </span>
              <input
                type="text"
                placeholder="Code, title, instructor..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="glass-input text-xs pl-9 w-full py-2.5"
              />
            </div>
          </div>

          {/* Department Filter */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Department</label>
            <select
              value={selectedDept}
              onChange={(e) => { setSelectedDept(e.target.value); setPage(1); }}
              className="glass-select text-xs py-2.5"
            >
              <option value="">All Departments</option>
              {depts.map(d => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>

          {/* Term Filter */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Academic Semester</label>
            <select
              value={selectedTerm}
              onChange={(e) => { setSelectedTerm(e.target.value); setPage(1); }}
              className="glass-select text-xs py-2.5"
            >
              <option value="">All Semesters</option>
              {terms.map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          {/* Day Filter */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">Meeting Day</label>
            <select
              value={selectedDay}
              onChange={(e) => { setSelectedDay(e.target.value); setPage(1); }}
              className="glass-select text-xs py-2.5"
            >
              <option value="">All Days</option>
              <option value="M">Monday</option>
              <option value="T">Tuesday</option>
              <option value="W">Wednesday</option>
              <option value="Th">Thursday</option>
              <option value="F">Friday</option>
              <option value="St">Saturday</option>
            </select>
          </div>
        </form>

        {/* Data Grid Table */}
        <div className="premium-table-container relative">
          {loading ? (
            <div className="h-64 w-full flex items-center justify-center bg-[hsla(var(--bg-secondary)/0.5)] absolute inset-0 z-10 backdrop-blur-sm rounded-lg">
              <div className="flex flex-col items-center gap-3">
                <svg className="animate-spin h-7 w-7 text-[hsl(var(--accent-primary))]" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span className="text-xs text-[hsl(var(--text-secondary))]">Fetching records...</span>
              </div>
            </div>
          ) : null}

          <table className="premium-table">
            <thead>
              <tr>
                <th className="w-[12%]">Semester</th>
                <th className="w-[8%]">Dept</th>
                <th className="w-[12%]">Course Code</th>
                <th className="w-[8%]">Sec</th>
                <th className="w-[25%]">Course Name</th>
                <th className="w-[18%]">Instructor</th>
                <th className="w-[17%]">Meetings (Day / Hour / Room)</th>
              </tr>
            </thead>
            <tbody>
              {courses.length > 0 ? (
                courses.map((course) => {
                  const isExpanded = expandedCourse === course.id;
                  return (
                    <React.Fragment key={course.id}>
                      <tr 
                        onClick={() => setExpandedCourse(isExpanded ? null : course.id)}
                        className={`cursor-pointer transition-all ${isExpanded ? 'bg-[hsla(var(--bg-tertiary)/0.6)]' : ''}`}
                      >
                        <td className="font-semibold text-xs text-[hsl(var(--text-secondary))]">{course.term}</td>
                        <td className="font-bold text-xs text-[hsl(var(--accent-primary))]">{course.department}</td>
                        <td className="font-semibold text-xs">{course.course_code}</td>
                        <td className="text-xs">{course.section}</td>
                        <td className="font-medium text-[13px]">{course.course_name}</td>
                        <td className="text-xs text-[hsl(var(--text-secondary))] truncate max-w-[150px]">{course.instructor}</td>
                        <td>
                          <div className="flex flex-wrap gap-1">
                            {course.slots && course.slots.length > 0 ? (
                              course.slots.map((s, sIdx) => (
                                <span 
                                  key={sIdx} 
                                  className="px-2 py-0.5 text-[10px] font-semibold bg-[hsla(var(--accent-primary)/0.08)] border border-[hsla(var(--accent-primary)/0.15)] text-[hsl(var(--text-primary))] rounded-md"
                                >
                                  {s.day} {s.hour} {s.room && `(${s.room})`}
                                </span>
                              ))
                            ) : (
                              <span className="text-[10px] text-[hsl(var(--text-muted))] uppercase">TBA</span>
                            )}
                          </div>
                        </td>
                      </tr>
                      
                      {/* Expanded Row Detail Drawer */}
                      {isExpanded && (
                        <tr>
                          <td colSpan={7} className="bg-[hsla(var(--bg-tertiary)/0.35)] px-8 py-6 border-b border-[hsla(var(--glass-border))]">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-fade-in text-xs text-[hsl(var(--text-secondary))]">
                              <div className="space-y-2">
                                <h4 className="font-bold text-sm text-[hsl(var(--text-primary))] flex items-center gap-1.5">
                                  <Layers size={14} className="text-[hsl(var(--accent-primary))]" />
                                  Course Specifications
                                </h4>
                                <p><strong>Credits:</strong> {course.credits || 'TBA'}</p>
                                <p><strong>ECTS:</strong> {course.ects || 'TBA'}</p>
                                <p><strong>Delivery Method:</strong> {course.delivery_method || 'Traditional'}</p>
                                <p><strong>SL:</strong> {course.sl || 'TBA'}</p>
                              </div>

                              <div className="space-y-2">
                                <h4 className="font-bold text-sm text-[hsl(var(--text-primary))] flex items-center gap-1.5">
                                  <Calendar size={14} className="text-[hsl(var(--accent-secondary))]" />
                                  Examination Particulars
                                </h4>
                                <p><strong>Exam Date:</strong> {course.exam_date || 'TBA'}</p>
                                <p><strong>Exam Location:</strong> {course.exam_location || 'TBA'}</p>
                              </div>

                              <div className="space-y-2">
                                <h4 className="font-bold text-sm text-[hsl(var(--text-primary))] flex items-center gap-1.5">
                                  <Info size={14} className="text-[hsl(var(--color-info))]" />
                                  Departmental Relations
                                </h4>
                                <p><strong>Required For:</strong> {course.required_for || 'None specified'}</p>
                                <p><strong>Shared Departments:</strong> {course.departments || 'None'}</p>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} className="text-center text-[hsl(var(--text-muted))] py-12">
                    No course records matched these active search parameters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Panel */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-4 border-t border-[hsla(var(--glass-border))]">
            <span className="text-xs text-[hsl(var(--text-secondary))]">
              Showing page <strong className="text-[hsl(var(--text-primary))]">{page}</strong> of <strong className="text-[hsl(var(--text-primary))]">{totalPages}</strong>
            </span>

            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage(prev => Math.max(1, prev - 1))}
                className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1"
              >
                <ChevronLeft size={14} />
                Previous
              </button>
              
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(prev => Math.min(totalPages, prev + 1))}
                className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1"
              >
                Next
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
