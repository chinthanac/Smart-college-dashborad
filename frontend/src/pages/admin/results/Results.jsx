import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminSidebar from '../../../components/AdminSidebar';
import GradeDistribution from '../../../components/marks/GradeDistribution';
import assessmentService, { apiErrorMessage, gradeTone, showNumber } from '../../../services/assessmentService';

const emptyChain = { departments: [], courses: [], semesters: [], sections: [], subjects: [] };

/**
 * Results for a section: the full mark sheet, or one subject in depth.
 *
 * Nothing here ever prints a zero for an unknown. Where the API says
 * has_data is false, the screen shows its reason instead.
 */
export default function Results() {
  const navigate = useNavigate();
  const token = localStorage.getItem('smart_college_token');

  const [chain, setChain] = useState(emptyChain);
  const [departmentId, setDepartmentId] = useState('');
  const [courseId, setCourseId] = useState('');
  const [semesterId, setSemesterId] = useState('');
  const [sectionId, setSectionId] = useState('');
  const [subjectId, setSubjectId] = useState('');

  const [tab, setTab] = useState('section');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) navigate('/login');
  }, [token, navigate]);

  useEffect(() => {
    assessmentService.departments().then((departments) =>
      setChain((c) => ({ ...c, departments })),
    ).catch(() => {});
  }, []);

  useEffect(() => {
    assessmentService.courses(departmentId).then((courses) =>
      setChain((c) => ({ ...c, courses })),
    ).catch(() => {});
    setCourseId(''); setSemesterId(''); setSectionId(''); setSubjectId('');
  }, [departmentId]);

  useEffect(() => {
    assessmentService.semesters(courseId).then((semesters) =>
      setChain((c) => ({ ...c, semesters })),
    ).catch(() => {});
    setSemesterId(''); setSectionId(''); setSubjectId('');
  }, [courseId]);

  useEffect(() => {
    Promise.all([
      assessmentService.sections(semesterId),
      assessmentService.subjects(semesterId),
    ]).then(([sections, subjects]) =>
      setChain((c) => ({ ...c, sections, subjects })),
    ).catch(() => {});
    setSectionId(''); setSubjectId('');
  }, [semesterId]);

  const load = useCallback(async () => {
    if (!sectionId) {
      setReport(null);
      return;
    }
    if (tab === 'subject' && !subjectId) {
      setReport(null);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = tab === 'section'
        ? await assessmentService.sectionReport(sectionId)
        : await assessmentService.subjectReport(sectionId, subjectId);
      setReport(data);
    } catch (err) {
      setReport(null);
      setError(apiErrorMessage(err, 'Unable to load this report.'));
    } finally {
      setLoading(false);
    }
  }, [tab, sectionId, subjectId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel department-page">
        <header className="topbar page-topbar">
          <div className="welcome-text">
            <strong>Results</strong>
            <span className="page-subtitle">
              Computed from published marks. A subject with any mark still missing is reported
              as pending rather than scored.
            </span>
          </div>
        </header>

        {error && (
          <div className="error-box dismissable" onClick={() => setError('')} role="alert">{error}</div>
        )}

        <div className="filters-row">
          <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">Select department…</option>
            {chain.departments.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>

          <select value={courseId} onChange={(e) => setCourseId(e.target.value)}>
            <option value="">Select course…</option>
            {chain.courses.map((item) => (
              <option key={item.id} value={item.id}>{item.code} — {item.name}</option>
            ))}
          </select>

          <select value={semesterId} onChange={(e) => setSemesterId(e.target.value)}>
            <option value="">Select semester…</option>
            {chain.semesters.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>

          <select value={sectionId} onChange={(e) => setSectionId(e.target.value)}>
            <option value="">Select section…</option>
            {chain.sections.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>

          {tab === 'subject' && (
            <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
              <option value="">Select subject…</option>
              {chain.subjects.map((item) => (
                <option key={item.id} value={item.id}>{item.subject_code} — {item.name}</option>
              ))}
            </select>
          )}
        </div>

        <div className="tab-row">
          <button
            type="button"
            className={`table-btn ${tab === 'section' ? 'is-selected' : ''}`}
            onClick={() => setTab('section')}
          >
            Section mark sheet
          </button>
          <button
            type="button"
            className={`table-btn ${tab === 'subject' ? 'is-selected' : ''}`}
            onClick={() => setTab('subject')}
          >
            One subject
          </button>
        </div>

        {loading && <p className="empty-note">Loading…</p>}

        {!loading && !report && (
          <p className="empty-note">
            Pick a section{tab === 'subject' ? ' and a subject' : ''} to see its results.
          </p>
        )}

        {!loading && report && !report.has_data && (
          <div className="notice-box" role="status">
            {report.reason || 'Nothing to report yet.'}
          </div>
        )}

        {!loading && report && tab === 'section' && (
          <SectionSheet report={report} />
        )}

        {!loading && report && tab === 'subject' && (
          <SubjectReport report={report} />
        )}
      </main>
    </div>
  );
}

function SectionSheet({ report }) {
  return (
    <>
      <dl className="sheet-summary">
        <div><dt>Students</dt><dd>{report.total_students}</dd></div>
        <div><dt>Complete</dt><dd>{report.complete_students}</dd></div>
        <div><dt>Pending</dt><dd>{report.pending_students}</dd></div>
        <div><dt>Passed</dt><dd>{report.pass_count}</dd></div>
        <div><dt>Failed</dt><dd>{report.fail_count}</dd></div>
        <div><dt>Pass rate</dt><dd>{showNumber(report.pass_percentage, '%')}</dd></div>
        <div><dt>Average SGPA</dt><dd>{showNumber(report.average_sgpa)}</dd></div>
      </dl>

      {report.distribution.length > 0 && (
        <section className="panel-card">
          <header className="panel-head"><h3>Grade distribution</h3></header>
          <GradeDistribution bands={report.distribution} total={report.complete_students} />
        </section>
      )}

      <div className="department-table-wrap scroll-table">
        <table className="department-table">
          <thead>
            <tr>
              <th>Roll No</th>
              <th>Student</th>
              {report.subjects.map((subject) => (
                <th key={subject.subject_id} title={subject.subject_name}>
                  {subject.subject_code}
                  <span className="page-subtitle"> ({subject.credits}cr)</span>
                </th>
              ))}
              <th>SGPA</th>
            </tr>
          </thead>
          <tbody>
            {report.students.map((row) => (
              <tr key={row.student_id}>
                <td className="mono">{row.student_code}</td>
                <td>{row.student_name}</td>
                {report.subjects.map((subject) => {
                  const percent = row.subject_percent[subject.subject_id];
                  const grade = row.subject_grade[subject.subject_id];
                  return (
                    <td key={subject.subject_id}>
                      {grade ? (
                        <>
                          <span className={`grade-chip tone-${gradeTone(grade)}`}>{grade}</span>
                          <span className="page-subtitle"> {percent}%</span>
                        </>
                      ) : (
                        <span className="page-subtitle">Pending</span>
                      )}
                    </td>
                  );
                })}
                <td className="mono">
                  {row.has_data ? row.sgpa : <span className="page-subtitle">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function SubjectReport({ report }) {
  return (
    <>
      <header className="panel-head">
        <div>
          <h3>{report.subject_code} — {report.subject_name}</h3>
          <span className="page-subtitle">
            {report.section_name} · {report.faculty_name} ·{' '}
            {report.allocated_weightage}% of the subject published
          </span>
        </div>
      </header>

      <dl className="sheet-summary">
        <div><dt>Graded</dt><dd>{report.graded_students} of {report.total_students}</dd></div>
        <div><dt>Pass rate</dt><dd>{showNumber(report.pass_percentage, '%')}</dd></div>
        <div><dt>Average</dt><dd>{showNumber(report.average_percent, '%')}</dd></div>
        <div><dt>Highest</dt><dd>{showNumber(report.highest_percent, '%')}</dd></div>
        <div><dt>Lowest</dt><dd>{showNumber(report.lowest_percent, '%')}</dd></div>
        <div><dt>Topper</dt><dd>{report.topper_student_name || '—'}</dd></div>
      </dl>

      <section className="panel-card">
        <header className="panel-head"><h3>Grade distribution</h3></header>
        <GradeDistribution bands={report.distribution} total={report.graded_students} />
      </section>
    </>
  );
}
