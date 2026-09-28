import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminSidebar from '../../../components/AdminSidebar';
import AttendanceFilters from '../../../components/attendance/AttendanceFilters';
import AttendanceSheetPanel from '../../../components/attendance/AttendanceSheetPanel';
import SectionReportTable from '../../../components/attendance/SectionReportTable';
import SessionTable from '../../../components/attendance/SessionTable';
import attendanceService, { apiErrorMessage } from '../../../services/attendanceService';

// Changing a level clears everything below it.
const CHAIN = ['department_id', 'course_id', 'semester_id', 'section_id', 'subject_id'];

const emptyFilters = {
  department_id: '',
  course_id: '',
  semester_id: '',
  section_id: '',
  subject_id: '',
  from_date: '',
  to_date: '',
};

const emptyOptions = { courses: [], semesters: [], sections: [], subjects: [] };

export default function Attendance() {
  const navigate = useNavigate();
  const token = localStorage.getItem('smart_college_token');

  const [tab, setTab] = useState('sessions');
  const [departments, setDepartments] = useState([]);
  const [options, setOptions] = useState(emptyOptions);
  const [filters, setFilters] = useState(emptyFilters);

  const [sessions, setSessions] = useState([]);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busyId, setBusyId] = useState(null);

  // The correction modal.
  const [sheet, setSheet] = useState(null);
  const [records, setRecords] = useState([]);
  const [cancelled, setCancelled] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [sheetError, setSheetError] = useState('');
  const [sheetNotice, setSheetNotice] = useState('');

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }
    const load = async () => {
      try {
        const [departmentList, courses] = await Promise.all([
          attendanceService.departments(),
          attendanceService.courses(),
        ]);
        setDepartments(departmentList);
        setOptions((current) => ({ ...current, courses }));
      } catch (err) {
        if (err?.response?.status === 401) {
          navigate('/login');
          return;
        }
        setError(apiErrorMessage(err, 'Unable to load reference data.'));
      }
    };
    load();
  }, [token, navigate]);

  const loadChain = useCallback(async (selection) => {
    const next = { ...emptyOptions };
    try {
      next.courses = await attendanceService.courses(selection.department_id || undefined);
      if (selection.course_id) {
        next.semesters = await attendanceService.semesters(selection.course_id);
      }
      if (selection.semester_id) {
        const [sections, subjects] = await Promise.all([
          attendanceService.sections(selection.semester_id),
          attendanceService.subjects(selection.semester_id),
        ]);
        next.sections = sections;
        next.subjects = subjects;
      }
    } catch (err) {
      setError(apiErrorMessage(err, 'Unable to load academic options.'));
    }
    setOptions(next);
  }, []);

  useEffect(() => {
    if (!token) return;
    loadChain(filters);
  }, [token, loadChain, filters.department_id, filters.course_id, filters.semester_id]);

  const fetchData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      if (tab === 'sessions') {
        setSessions(await attendanceService.sessions(filters));
      } else if (filters.section_id) {
        setReport(
          await attendanceService.sectionReport({
            section_id: filters.section_id,
            subject_id: filters.subject_id,
            from_date: filters.from_date,
            to_date: filters.to_date,
          }),
        );
      } else {
        setReport(null);
      }
      setError('');
    } catch (err) {
      if (err?.response?.status === 401) {
        navigate('/login');
        return;
      }
      setError(apiErrorMessage(err, 'Unable to load attendance.'));
    } finally {
      setLoading(false);
    }
  }, [token, tab, filters, navigate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleFilterChange = (key, value) => {
    setFilters((current) => {
      const next = { ...current, [key]: value };
      const index = CHAIN.indexOf(key);
      if (index !== -1) CHAIN.slice(index + 1).forEach((k) => { next[k] = ''; });
      return next;
    });
  };

  // ------------------------------------------------------------- the sheet

  const applySheet = (data) => {
    setSheet(data);
    setRecords(data.records.map((r) => ({ ...r })));
    setCancelled(data.sheet_state === 'CANCELLED');
    setCancelReason(data.session?.cancel_reason || '');
    setNotes(data.session?.notes || '');
  };

  const openSession = async (item) => {
    setSheetError('');
    setSheetNotice('');
    setBusyId(item.id);
    try {
      applySheet(await attendanceService.session(item.id));
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not open this register.'));
    } finally {
      setBusyId(null);
    }
  };

  const closeSheet = () => {
    setSheet(null);
    setRecords([]);
    setSheetError('');
    setSheetNotice('');
  };

  const handleSave = async () => {
    setSaving(true);
    setSheetError('');
    setSheetNotice('');
    try {
      const saved = await attendanceService.saveSheet({
        timetable_entry_id: sheet.timetable_entry_id,
        class_date: sheet.class_date,
        session_status: cancelled ? 'CANCELLED' : 'HELD',
        cancel_reason: cancelled ? cancelReason : null,
        notes: notes || null,
        records: cancelled
          ? []
          : records.map((r) => ({
              student_id: r.student_id,
              status: r.status,
              remarks: r.remarks || null,
            })),
      });
      applySheet(saved);
      setSheetNotice('Register corrected.');
      fetchData();
    } catch (err) {
      setSheetError(apiErrorMessage(err, 'Could not save this register.'));
    } finally {
      setSaving(false);
    }
  };

  const handleCancelSession = async (item) => {
    const reason = window.prompt(
      `Cancel ${item.subject_code} on ${item.class_date}?\n\n` +
        'Its attendance records will be cleared, and it will count toward nobody.\n\nWhy was it cancelled?',
    );
    if (!reason) return;

    setBusyId(item.id);
    try {
      await attendanceService.setSessionStatus(item.id, 'CANCELLED', reason);
      setNotice(`${item.subject_code} on ${item.class_date} marked cancelled.`);
      fetchData();
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not cancel this class.'));
    } finally {
      setBusyId(null);
    }
  };

  const handleDeleteSession = async (item) => {
    const confirmed = window.confirm(
      `Delete the register for ${item.subject_code} on ${item.class_date}?\n\n` +
        'Every student’s record for this class is destroyed. Cancel it instead to keep the history.',
    );
    if (!confirmed) return;

    setBusyId(item.id);
    try {
      await attendanceService.removeSession(item.id);
      setNotice('Register deleted.');
      fetchData();
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not delete this register.'));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel department-page">
        <header className="topbar page-topbar">
          <div className="welcome-text">
            <strong>Attendance</strong>
            <span className="page-subtitle">
              Every register that has been taken, and how each section is doing against the
              75% minimum.
            </span>
          </div>

          <div className="topbar-right">
            <button
              type="button"
              className={tab === 'sessions' ? 'primary-btn' : 'secondary-btn'}
              onClick={() => setTab('sessions')}
            >
              Registers
            </button>
            <button
              type="button"
              className={tab === 'report' ? 'primary-btn' : 'secondary-btn'}
              onClick={() => setTab('report')}
            >
              Report
            </button>
          </div>
        </header>

        <AttendanceFilters
          filters={filters}
          departments={departments}
          courses={options.courses}
          semesters={options.semesters}
          sections={options.sections}
          subjects={options.subjects}
          requireSection={tab === 'report'}
          onChange={handleFilterChange}
          onReset={() => setFilters(emptyFilters)}
        />

        {error && (
          <div className="error-box dismissable" onClick={() => setError('')} role="alert">
            {error}
          </div>
        )}
        {notice && (
          <div className="success-box dismissable" onClick={() => setNotice('')} role="status">
            {notice}
          </div>
        )}

        {tab === 'report' && report && (
          <section className="mini-stats">
            <div className="mini-stat">
              <span className="mini-stat-label">Classes Held</span>
              <strong className="mini-stat-value tone-green">{report.held_sessions}</strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Cancelled</span>
              <strong className="mini-stat-value tone-gray">{report.cancelled_sessions}</strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Students</span>
              <strong className="mini-stat-value tone-blue">{report.total_students}</strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Below {report.threshold}%</span>
              <strong className="mini-stat-value tone-red">{report.defaulter_count}</strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Section Average</span>
              <strong className="mini-stat-value tone-blue">{report.section_percentage}%</strong>
            </div>
          </section>
        )}

        {tab === 'sessions' ? (
          <SessionTable
            sessions={sessions}
            loading={loading}
            busyId={busyId}
            onOpen={openSession}
            onCancel={handleCancelSession}
            onDelete={handleDeleteSession}
          />
        ) : (
          <SectionReportTable report={report} loading={loading} />
        )}
      </main>

      {sheet && (
        <div className="modal-backdrop" onClick={closeSheet}>
          <div className="modal-card wide" onClick={(e) => e.stopPropagation()}>
            <AttendanceSheetPanel
              sheet={sheet}
              records={records}
              cancelled={cancelled}
              cancelReason={cancelReason}
              notes={notes}
              saving={saving}
              error={sheetError}
              notice={sheetNotice}
              onChange={(studentId, status) =>
                setRecords((current) =>
                  current.map((r) => (r.student_id === studentId ? { ...r, status } : r)),
                )
              }
              onMarkAll={(status) =>
                setRecords((current) => current.map((r) => ({ ...r, status })))
              }
              onToggleCancelled={setCancelled}
              onCancelReasonChange={setCancelReason}
              onNotesChange={setNotes}
              onSave={handleSave}
              onDismissError={() => setSheetError('')}
            />
            <div className="modal-actions">
              <button type="button" className="secondary-btn" onClick={closeSheet}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
