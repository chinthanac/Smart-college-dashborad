import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminSidebar from '../../../components/AdminSidebar';
import AssessmentFilters from '../../../components/assessments/AssessmentFilters';
import AssessmentForm from '../../../components/assessments/AssessmentForm';
import AssessmentTable from '../../../components/assessments/AssessmentTable';
import MarkSheetPanel from '../../../components/marks/MarkSheetPanel';
import assessmentService, { apiErrorMessage, markValue } from '../../../services/assessmentService';

// Changing a level clears everything below it.
const CHAIN = ['department_id', 'course_id', 'semester_id', 'section_id'];

const emptyFilters = {
  department_id: '',
  course_id: '',
  semester_id: '',
  section_id: '',
  assessment_type: '',
  status: '',
};

const toRows = (sheet) =>
  sheet.records.map((record) => ({
    ...record,
    draft: markValue(record),
  }));

export default function Assessments() {
  const navigate = useNavigate();
  const token = localStorage.getItem('smart_college_token');

  const [chain, setChain] = useState({
    departments: [], courses: [], semesters: [], sections: [],
  });
  const [filters, setFilters] = useState(emptyFilters);
  const [search, setSearch] = useState('');

  const [rows, setRows] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  // The mark sheet, opened from a row.
  const [sheet, setSheet] = useState(null);
  const [sheetRows, setSheetRows] = useState([]);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sheetError, setSheetError] = useState('');
  const [sheetNotice, setSheetNotice] = useState('');

  useEffect(() => {
    if (!token) navigate('/login');
  }, [token, navigate]);

  useEffect(() => {
    assessmentService
      .departments()
      .then((departments) => setChain((c) => ({ ...c, departments })))
      .catch(() => {});
  }, []);

  useEffect(() => {
    assessmentService
      .courses(filters.department_id)
      .then((courses) => setChain((c) => ({ ...c, courses })))
      .catch(() => {});
  }, [filters.department_id]);

  useEffect(() => {
    assessmentService
      .semesters(filters.course_id)
      .then((semesters) => setChain((c) => ({ ...c, semesters })))
      .catch(() => {});
  }, [filters.course_id]);

  useEffect(() => {
    assessmentService
      .sections(filters.semester_id)
      .then((sections) => setChain((c) => ({ ...c, sections })))
      .catch(() => {});
  }, [filters.semester_id]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, classes] = await Promise.all([
        assessmentService.list({ ...filters, search }),
        assessmentService.teachingAssignments({
          semester_id: filters.semester_id,
          section_id: filters.section_id,
        }),
      ]);
      setRows(list);
      setAssignments(classes);
      setError('');
    } catch (err) {
      if (err?.response?.status === 401) {
        navigate('/login');
        return;
      }
      setRows([]);
      setError(apiErrorMessage(err, 'Unable to load assessments.'));
    } finally {
      setLoading(false);
    }
  }, [filters, search, navigate]);

  useEffect(() => {
    const timer = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  const handleFilterChange = (key, value) => {
    setFilters((current) => {
      const next = { ...current, [key]: value };
      const index = CHAIN.indexOf(key);
      if (index !== -1) CHAIN.slice(index + 1).forEach((field) => { next[field] = ''; });
      return next;
    });
  };

  const resetFilters = () => {
    setFilters(emptyFilters);
    setSearch('');
  };

  // --- the mark sheet ---

  const openSheet = async (row) => {
    setSheetError('');
    setSheetNotice('');
    setDirty(false);
    try {
      const data = await assessmentService.sheet(row.id);
      setSheet(data);
      setSheetRows(toRows(data));
    } catch (err) {
      setSheet(null);
      setSheetRows([]);
      setSheetError(apiErrorMessage(err, 'Could not open this mark sheet.'));
    }
  };

  const handleCellChange = (studentId, patch) => {
    setDirty(true);
    setSheetRows((current) =>
      current.map((row) => (row.student_id === studentId ? { ...row, ...patch } : row)),
    );
  };

  const handleSaveSheet = async () => {
    setSaving(true);
    setSheetError('');
    setSheetNotice('');
    try {
      const entries = sheetRows.map((row) => ({
        student_id: row.student_id,
        // '' means "not entered" and clears the row — never a zero.
        marks_obtained: (row.draft ?? '') === '' ? null : Number(row.draft),
        is_absent: Boolean(row.is_absent),
        is_malpractice: Boolean(row.is_malpractice),
        remarks: row.remarks || null,
      }));
      const saved = await assessmentService.saveSheet(sheet.assessment_id, entries);
      setSheet(saved);
      setSheetRows(toRows(saved));
      setDirty(false);
      setSheetNotice('Marks saved.');
      load();
    } catch (err) {
      setSheetError(apiErrorMessage(err, 'Could not save these marks.'));
    } finally {
      setSaving(false);
    }
  };

  const resetSheet = () => {
    if (!sheet) return;
    setSheetRows(toRows(sheet));
    setDirty(false);
  };

  // --- status and deletion ---

  const handleStatus = async (row, action) => {
    setError('');
    setNotice('');
    try {
      await assessmentService.setStatus(row.id, action);
      setNotice(
        action === 'publish'
          ? `"${row.name}" is published — students can see it now.`
          : action === 'lock'
            ? `"${row.name}" is locked.`
            : `"${row.name}" is open for corrections again.`,
      );
      load();
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not change the status.'));
    }
  };

  const handleDelete = async (row) => {
    setError('');
    setNotice('');
    try {
      await assessmentService.remove(row.id);
      setNotice(`"${row.name}" deleted.`);
      load();
    } catch (err) {
      const message = apiErrorMessage(err, 'Could not delete this assessment.');
      // The API refuses while marks exist and says how many. Repeat that
      // count in the confirmation rather than asking a bare "are you sure?".
      if (err?.response?.status === 409 && window.confirm(`${message}\n\nDelete it anyway?`)) {
        try {
          await assessmentService.remove(row.id, true);
          setNotice(`"${row.name}" and its marks were deleted.`);
          load();
          return;
        } catch (forced) {
          setError(apiErrorMessage(forced, 'Could not delete this assessment.'));
          return;
        }
      }
      setError(message);
    }
  };

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel department-page">
        <header className="topbar page-topbar">
          <div className="welcome-text">
            <strong>Assessments</strong>
            <span className="page-subtitle">
              The gradable components of each subject. A draft reaches nobody until it is published.
            </span>
          </div>
          <button
            type="button"
            className="table-btn success-btn"
            onClick={() => { setEditing(null); setFormOpen(true); }}
          >
            New assessment
          </button>
        </header>

        {error && (
          <div className="error-box dismissable" onClick={() => setError('')} role="alert">{error}</div>
        )}
        {notice && (
          <div className="notice-box dismissable" onClick={() => setNotice('')} role="status">{notice}</div>
        )}

        <AssessmentFilters
          chain={chain}
          filters={filters}
          search={search}
          onChange={handleFilterChange}
          onSearchChange={setSearch}
          onReset={resetFilters}
        />

        <AssessmentTable
          rows={rows}
          loading={loading}
          onEdit={(row) => { setEditing(row); setFormOpen(true); }}
          onEnterMarks={openSheet}
          onStatus={handleStatus}
          onDelete={handleDelete}
        />

        {(sheet || sheetError) && (
          <MarkSheetPanel
            sheet={sheet}
            rows={sheetRows}
            dirty={dirty}
            saving={saving}
            error={sheetError}
            notice={sheetNotice}
            onChange={handleCellChange}
            onSave={handleSaveSheet}
            onReset={resetSheet}
            onDismissError={() => setSheetError('')}
          />
        )}

        {formOpen && (
          <AssessmentForm
            editing={editing}
            assignments={assignments}
            onClose={() => setFormOpen(false)}
            onSaved={(_, message) => {
              setFormOpen(false);
              setNotice(message);
              load();
            }}
          />
        )}
      </main>
    </div>
  );
}
