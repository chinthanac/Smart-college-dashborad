import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AttendanceClassPicker from '../../../components/attendance/AttendanceClassPicker';
import AttendanceSheetPanel from '../../../components/attendance/AttendanceSheetPanel';
import attendanceService, {
  apiErrorMessage,
  toDateValue,
} from '../../../services/attendanceService';
import { clearAuthState } from '../../../components/AdminSidebar';

export default function MarkAttendance() {
  const navigate = useNavigate();
  const token = localStorage.getItem('smart_college_token');

  const [classDate, setClassDate] = useState(toDateValue());
  const [classes, setClasses] = useState([]);
  const [loadingClasses, setLoadingClasses] = useState(true);

  const [selected, setSelected] = useState(null);
  const [sheet, setSheet] = useState(null);
  const [records, setRecords] = useState([]);
  const [cancelled, setCancelled] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [notes, setNotes] = useState('');

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [sheetError, setSheetError] = useState('');
  const [notice, setNotice] = useState('');

  const handleLogout = () => {
    clearAuthState();
    navigate('/login');
    window.location.reload();
  };

  const loadClasses = useCallback(async () => {
    if (!token) {
      navigate('/login');
      return;
    }
    setLoadingClasses(true);
    try {
      setClasses(await attendanceService.myClasses(classDate));
      setError('');
    } catch (err) {
      if (err?.response?.status === 401) {
        navigate('/login');
        return;
      }
      setClasses([]);
      setError(apiErrorMessage(err, 'Unable to load your classes.'));
    } finally {
      setLoadingClasses(false);
    }
  }, [token, classDate, navigate]);

  useEffect(() => {
    loadClasses();
  }, [loadClasses]);

  /** Changing the date invalidates the open sheet — the class may not meet. */
  const handleDateChange = (value) => {
    setClassDate(value);
    setSelected(null);
    setSheet(null);
    setRecords([]);
    setSheetError('');
    setNotice('');
  };

  const openSheet = async (item) => {
    setSelected(item);
    setSheetError('');
    setNotice('');
    try {
      const data = await attendanceService.sheet(item.timetable_entry_id, classDate);
      applySheet(data);
    } catch (err) {
      setSheet(null);
      setRecords([]);
      setSheetError(apiErrorMessage(err, 'Could not open this register.'));
    }
  };

  const applySheet = (data) => {
    setSheet(data);
    setRecords(data.records.map((r) => ({ ...r })));
    setCancelled(data.sheet_state === 'CANCELLED');
    setCancelReason(data.session?.cancel_reason || '');
    setNotes(data.session?.notes || '');
  };

  const handleChange = (studentId, status) =>
    setRecords((current) =>
      current.map((r) => (r.student_id === studentId ? { ...r, status } : r)),
    );

  const handleMarkAll = (status) =>
    setRecords((current) => current.map((r) => ({ ...r, status })));

  const handleSave = async () => {
    setSaving(true);
    setSheetError('');
    setNotice('');
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
      setNotice(cancelled ? 'Class marked as cancelled.' : 'Register saved.');
      loadClasses();
    } catch (err) {
      setSheetError(apiErrorMessage(err, 'Could not save this register.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="admin-layout">
      <aside className="sidebar">
        <div className="brand-box">
          <div className="brand-mark">S</div>
          <div className="brand-text">
            <span className="brand-main">SMART COLLEGE</span>
            <span className="brand-sub">FACULTY</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-group">
            <span className="nav-group-title">Overview</span>
            <button className="nav-item" type="button" onClick={() => navigate('/faculty/dashboard')}>
              <span className="nav-icon">◫</span>
              <span className="nav-label">Dashboard</span>
            </button>
          </div>

          <div className="nav-group">
            <span className="nav-group-title">Teaching</span>
            <button className="nav-item active" type="button">
              <span className="nav-icon">◑</span>
              <span className="nav-label">Attendance</span>
            </button>
          </div>

          <div className="nav-group">
            <button className="nav-item logout" type="button" onClick={handleLogout}>
              <span className="nav-icon">⏻</span>
              <span className="nav-label">Logout</span>
            </button>
          </div>
        </nav>
      </aside>

      <main className="content-panel department-page">
        <header className="topbar page-topbar">
          <div className="welcome-text">
            <strong>Mark Attendance</strong>
            <span className="page-subtitle">
              Pick one of your classes and take the register. Saving again corrects it.
            </span>
          </div>
        </header>

        {error && (
          <div className="error-box dismissable" onClick={() => setError('')} role="alert">
            {error}
          </div>
        )}

        <div className="timetable-layout attendance-layout">
          <AttendanceSheetPanel
            sheet={sheet}
            records={records}
            cancelled={cancelled}
            cancelReason={cancelReason}
            notes={notes}
            saving={saving}
            error={sheetError}
            notice={notice}
            onChange={handleChange}
            onMarkAll={handleMarkAll}
            onToggleCancelled={setCancelled}
            onCancelReasonChange={setCancelReason}
            onNotesChange={setNotes}
            onSave={handleSave}
            onDismissError={() => setSheetError('')}
          />

          <AttendanceClassPicker
            classDate={classDate}
            classes={classes}
            loading={loadingClasses}
            selectedEntryId={selected?.timetable_entry_id}
            onDateChange={handleDateChange}
            onSelect={openSheet}
          />
        </div>
      </main>
    </div>
  );
}
