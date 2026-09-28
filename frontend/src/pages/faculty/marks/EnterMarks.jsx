import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MarkSheetPanel from '../../../components/marks/MarkSheetPanel';
import assessmentService, { apiErrorMessage, markValue } from '../../../services/assessmentService';
import { clearAuthState } from '../../../components/AdminSidebar';

const toRows = (sheet) =>
  sheet.records.map((record) => ({ ...record, draft: markValue(record) }));

/**
 * A lecturer's marks entry.
 *
 * The picker lists outstanding work first with its progress, so the screen
 * opens onto what is left to do rather than an empty dropdown.
 */
export default function EnterMarks() {
  const navigate = useNavigate();
  const token = localStorage.getItem('smart_college_token');

  const [classes, setClasses] = useState([]);
  const [loadingClasses, setLoadingClasses] = useState(true);
  const [onlyPending, setOnlyPending] = useState(false);
  const [selectedId, setSelectedId] = useState(null);

  const [sheet, setSheet] = useState(null);
  const [rows, setRows] = useState([]);
  const [dirty, setDirty] = useState(false);
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
      setClasses(await assessmentService.myAssessments({ only_pending: onlyPending }));
      setError('');
    } catch (err) {
      if (err?.response?.status === 401) {
        navigate('/login');
        return;
      }
      setClasses([]);
      setError(apiErrorMessage(err, 'Unable to load your assessments.'));
    } finally {
      setLoadingClasses(false);
    }
  }, [token, onlyPending, navigate]);

  useEffect(() => { loadClasses(); }, [loadClasses]);

  const openSheet = async (item) => {
    if (dirty && !window.confirm('You have unsaved marks. Discard them?')) return;
    setSelectedId(item.assessment_id);
    setSheetError('');
    setNotice('');
    setDirty(false);
    try {
      const data = await assessmentService.sheet(item.assessment_id);
      setSheet(data);
      setRows(toRows(data));
    } catch (err) {
      setSheet(null);
      setRows([]);
      setSheetError(apiErrorMessage(err, 'Could not open this mark sheet.'));
    }
  };

  const handleCellChange = (studentId, patch) => {
    setDirty(true);
    setRows((current) =>
      current.map((row) => (row.student_id === studentId ? { ...row, ...patch } : row)),
    );
  };

  const handleSave = async () => {
    setSaving(true);
    setSheetError('');
    setNotice('');
    try {
      const entries = rows.map((row) => ({
        student_id: row.student_id,
        marks_obtained: (row.draft ?? '') === '' ? null : Number(row.draft),
        is_absent: Boolean(row.is_absent),
        is_malpractice: Boolean(row.is_malpractice),
        remarks: row.remarks || null,
      }));
      const saved = await assessmentService.saveSheet(sheet.assessment_id, entries);
      setSheet(saved);
      setRows(toRows(saved));
      setDirty(false);
      setNotice('Marks saved.');
      loadClasses();
    } catch (err) {
      setSheetError(apiErrorMessage(err, 'Could not save these marks.'));
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
            <button className="nav-item" type="button" onClick={() => navigate('/faculty/attendance')}>
              <span className="nav-icon">◑</span>
              <span className="nav-label">Attendance</span>
            </button>
            <button className="nav-item active" type="button">
              <span className="nav-icon">◍</span>
              <span className="nav-label">Marks</span>
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
            <strong>Enter Marks</strong>
            <span className="page-subtitle">
              Pick an assessment and fill the sheet. Enter moves to the next student; a blank
              cell means "not entered", never zero.
            </span>
          </div>
        </header>

        {error && (
          <div className="error-box dismissable" onClick={() => setError('')} role="alert">{error}</div>
        )}

        <div className="timetable-layout attendance-layout">
          <MarkSheetPanel
            sheet={sheet}
            rows={rows}
            dirty={dirty}
            saving={saving}
            error={sheetError}
            notice={notice}
            onChange={handleCellChange}
            onSave={handleSave}
            onReset={() => { setRows(toRows(sheet)); setDirty(false); }}
            onDismissError={() => setSheetError('')}
          />

          <aside className="panel-card picker-card">
            <header className="panel-head">
              <h3>My assessments</h3>
              <label className="inline-check">
                <input
                  type="checkbox"
                  checked={onlyPending}
                  onChange={(event) => setOnlyPending(event.target.checked)}
                />
                Outstanding only
              </label>
            </header>

            {loadingClasses ? (
              <p className="empty-note">Loading…</p>
            ) : !classes.length ? (
              <p className="empty-note">
                Nothing to enter. Assessments appear here once they are created for your classes.
              </p>
            ) : (
              <ul className="class-picker-list">
                {classes.map((item) => (
                  <li key={item.assessment_id}>
                    <button
                      type="button"
                      className={`class-picker-item ${
                        selectedId === item.assessment_id ? 'is-selected' : ''
                      }`}
                      onClick={() => openSheet(item)}
                    >
                      <span className="picker-main">{item.name}</span>
                      <span className="picker-sub">
                        {item.subject_code} · {item.section_name} · out of {item.max_marks}
                      </span>
                      <div className="coverage-bar">
                        <div
                          className="coverage-bar-fill"
                          style={{
                            width: `${item.completion_percent}%`,
                            background:
                              item.state === 'COMPLETE'
                                ? 'var(--chart-series-1)'
                                : 'var(--accent-amber)',
                          }}
                        />
                      </div>
                      <span className="picker-sub">
                        {item.entered_count} of {item.total_students} entered
                        {item.state === 'LOCKED' && ' · locked'}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </aside>
        </div>
      </main>
    </div>
  );
}
