import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminSidebar from '../../../components/AdminSidebar';
import TeachingAssignmentFilters from '../../../components/teaching-assignments/TeachingAssignmentFilters';
import TeachingAssignmentTable from '../../../components/teaching-assignments/TeachingAssignmentTable';
import TeachingAssignmentForm from '../../../components/teaching-assignments/TeachingAssignmentForm';
import BulkAssignForm from '../../../components/teaching-assignments/BulkAssignForm';
import TeachingAssignmentDetails from '../../../components/teaching-assignments/TeachingAssignmentDetails';
import teachingAssignmentService from '../../../services/teachingAssignmentService';

const PAGE_SIZES = [10, 25, 50, 100];

// Department → Course → Semester → {Subject, Section}. Changing a level
// clears everything after it in this order.
const CHAIN = ['department_id', 'course_id', 'semester_id', 'subject_id', 'section_id'];

const emptyForm = {
  department_id: '',
  course_id: '',
  semester_id: '',
  subject_id: '',
  section_id: '',
  faculty_id: '',
  notes: '',
  is_active: true,
};

const emptyBulkForm = {
  department_id: '',
  course_id: '',
  semester_id: '',
  subject_id: '',
  faculty_id: '',
  section_ids: [],
  notes: '',
  is_active: true,
};

const emptyFilters = {
  department_id: '',
  course_id: '',
  semester_id: '',
  subject_id: '',
  section_id: '',
  is_active: '',
};

const emptyOptions = { courses: [], semesters: [], subjects: [], sections: [] };

export default function TeachingAssignments() {
  const navigate = useNavigate();
  const token = localStorage.getItem('smart_college_token');

  const [assignments, setAssignments] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [facultyList, setFacultyList] = useState([]);

  const [filterOptions, setFilterOptions] = useState(emptyOptions);
  const [formOptions, setFormOptions] = useState(emptyOptions);
  const [bulkOptions, setBulkOptions] = useState(emptyOptions);

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [filters, setFilters] = useState(emptyFilters);
  const [sort, setSort] = useState({ key: 'subject_code', direction: 'asc' });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [lockPlacement, setLockPlacement] = useState(false);
  const [currentFacultyName, setCurrentFacultyName] = useState('');
  const [form, setForm] = useState(emptyForm);
  const [formErrors, setFormErrors] = useState({});
  const [showAllFaculty, setShowAllFaculty] = useState(false);
  const [saving, setSaving] = useState(false);

  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkForm, setBulkForm] = useState(emptyBulkForm);
  const [bulkErrors, setBulkErrors] = useState({});
  const [bulkShowAllFaculty, setBulkShowAllFaculty] = useState(false);

  const [detailsFor, setDetailsFor] = useState(null);
  const [busyRowId, setBusyRowId] = useState(null);

  // ---------------------------------------------------------------- data

  const fetchAssignments = useCallback(async () => {
    try {
      setAssignments(
        await teachingAssignmentService.list({ ...filters, search: debouncedSearch.trim() }),
      );
      setError('');
    } catch (err) {
      if (err?.response?.status === 401) {
        navigate('/login');
        return;
      }
      setError(err?.response?.data?.detail || 'Unable to load teaching assignments.');
    } finally {
      setLoading(false);
    }
  }, [filters, debouncedSearch, navigate]);

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }
    const loadReferenceData = async () => {
      try {
        const [departmentList, faculty, courses] = await Promise.all([
          teachingAssignmentService.departments(),
          teachingAssignmentService.faculty(),
          teachingAssignmentService.courses(),
        ]);
        setDepartments(departmentList);
        setFacultyList(faculty);
        setFilterOptions((current) => ({ ...current, courses }));
        setFormOptions((current) => ({ ...current, courses }));
        setBulkOptions((current) => ({ ...current, courses }));
      } catch (err) {
        setError(err?.response?.data?.detail || 'Unable to load reference data.');
      }
    };
    loadReferenceData();
  }, [token, navigate]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (!token) return;
    fetchAssignments();
  }, [token, fetchAssignments]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, filters, pageSize]);

  /**
   * Reload only the levels below whichever one changed. Subject and Section
   * are fetched from the SAME semester, which is what makes an invalid
   * subject/section pair unreachable from the UI.
   */
  const loadChain = useCallback(async (selection, setOptions) => {
    const next = { ...emptyOptions };
    try {
      next.courses = await teachingAssignmentService.courses(selection.department_id || undefined);
      if (selection.course_id) {
        next.semesters = await teachingAssignmentService.semesters(selection.course_id);
      }
      if (selection.semester_id) {
        const [subjects, sections] = await Promise.all([
          teachingAssignmentService.subjects(selection.semester_id),
          teachingAssignmentService.sections(selection.semester_id),
        ]);
        next.subjects = subjects;
        next.sections = sections;
      }
      setOptions(next);
      return next;
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load academic options.');
      setOptions(next);
      return next;
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    loadChain(filters, setFilterOptions);
  }, [token, loadChain, filters.department_id, filters.course_id, filters.semester_id]);

  // --------------------------------------------------------- derived

  const stats = useMemo(() => {
    const active = assignments.filter((a) => a.is_active).length;
    return {
      total: assignments.length,
      active,
      inactive: assignments.length - active,
      sections: new Set(assignments.map((a) => a.section_id)).size,
      faculty: new Set(assignments.map((a) => a.faculty_id)).size,
    };
  }, [assignments]);

  const sortedAssignments = useMemo(() => {
    const rows = [...assignments];
    const { key, direction } = sort;
    const factor = direction === 'asc' ? 1 : -1;
    rows.sort((a, b) => {
      const left = a[key];
      const right = b[key];
      if (key === 'semester_number') return ((left ?? 0) - (right ?? 0)) * factor;
      if (key === 'is_active') return (Number(left) - Number(right)) * factor;
      return String(left ?? '').localeCompare(String(right ?? ''), undefined, { numeric: true }) * factor;
    });
    return rows;
  }, [assignments, sort]);

  const totalPages = Math.max(1, Math.ceil(sortedAssignments.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visibleAssignments = useMemo(
    () => sortedAssignments.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [sortedAssignments, currentPage, pageSize],
  );

  const activeFilterCount = Object.values(filters).filter(Boolean).length + (search.trim() ? 1 : 0);

  const toggleSort = (key) =>
    setSort((c) => ({ key, direction: c.key === key && c.direction === 'asc' ? 'desc' : 'asc' }));

  // --------------------------------------------------------- filters

  const handleFilterChange = (key, value) => {
    setFilters((current) => {
      const next = { ...current, [key]: value };
      const index = CHAIN.indexOf(key);
      if (index !== -1) CHAIN.slice(index + 1).forEach((k) => { next[k] = ''; });
      return next;
    });
  };

  const resetFilters = () => {
    setFilters(emptyFilters);
    setSearch('');
  };

  // ------------------------------------------------- faculty filtering

  const subjectFor = (subjectId, options) =>
    options.subjects.find((s) => String(s.id) === String(subjectId)) || null;

  const selectedSubject = useMemo(
    () => subjectFor(form.subject_id, formOptions),
    [form.subject_id, formOptions],
  );

  const visibleFaculty = useMemo(() => {
    if (showAllFaculty || !selectedSubject?.department_id) return facultyList;
    return facultyList.filter((f) => f.department_id === selectedSubject.department_id);
  }, [facultyList, showAllFaculty, selectedSubject]);

  const selectedFaculty = useMemo(
    () => facultyList.find((f) => String(f.id) === String(form.faculty_id)) || null,
    [facultyList, form.faculty_id],
  );

  // An empty dropdown with no explanation is the worst outcome — fall back
  // to every department and say so.
  useEffect(() => {
    if (!showAllFaculty && selectedSubject && visibleFaculty.length === 0 && facultyList.length > 0) {
      setShowAllFaculty(true);
      setNotice(`No active faculty in ${selectedSubject.department_name} — showing all departments.`);
    }
  }, [showAllFaculty, selectedSubject, visibleFaculty.length, facultyList.length]);

  const bulkSelectedSubject = useMemo(
    () => subjectFor(bulkForm.subject_id, bulkOptions),
    [bulkForm.subject_id, bulkOptions],
  );

  const bulkVisibleFaculty = useMemo(() => {
    if (bulkShowAllFaculty || !bulkSelectedSubject?.department_id) return facultyList;
    return facultyList.filter((f) => f.department_id === bulkSelectedSubject.department_id);
  }, [facultyList, bulkShowAllFaculty, bulkSelectedSubject]);

  /** Sections in the chosen semester that already teach the chosen subject. */
  const existingBySection = useMemo(() => {
    if (!bulkForm.subject_id) return {};
    return assignments
      .filter((a) => String(a.subject_id) === String(bulkForm.subject_id))
      .reduce((acc, a) => ({ ...acc, [a.section_id]: a }), {});
  }, [assignments, bulkForm.subject_id]);

  // ----------------------------------------------------------- modal

  const openCreateModal = async () => {
    setEditingId(null);
    setLockPlacement(false);
    setCurrentFacultyName('');
    setForm(emptyForm);
    setFormErrors({});
    setShowAllFaculty(false);
    setError('');
    setModalOpen(true);
    await loadChain(emptyForm, setFormOptions);
  };

  const openEditModal = async (assignment, { lock } = { lock: false }) => {
    setEditingId(assignment.id);
    setLockPlacement(lock);
    setCurrentFacultyName(assignment.faculty_name || '');
    const next = {
      department_id: String(assignment.department_id || ''),
      course_id: String(assignment.course_id || ''),
      semester_id: String(assignment.semester_id),
      subject_id: String(assignment.subject_id),
      section_id: String(assignment.section_id),
      faculty_id: String(assignment.faculty_id),
      notes: assignment.notes || '',
      is_active: assignment.is_active,
    };
    setForm(next);
    setFormErrors({});
    setShowAllFaculty(Boolean(assignment.is_cross_department));
    setError('');
    setDetailsFor(null);
    setModalOpen(true);
    await loadChain(next, setFormOptions);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
    setLockPlacement(false);
    setForm(emptyForm);
    setFormErrors({});
  };

  const handleFieldChange = (name, value) => {
    setForm((current) => ({ ...current, [name]: value }));
    setFormErrors((current) => ({ ...current, [name]: '' }));
  };

  const handleLevelChange = async (level, value) => {
    if (level === 'faculty_id' || level === 'section_id') {
      handleFieldChange(level, value);
      return;
    }

    const next = { ...form, [level]: value };
    const index = CHAIN.indexOf(level);
    if (index !== -1) CHAIN.slice(index + 1).forEach((k) => { next[k] = ''; });

    setForm(next);
    setFormErrors({});
    await loadChain(next, setFormOptions);
  };

  // Changing the subject can invalidate the chosen faculty under the filter.
  useEffect(() => {
    if (!form.faculty_id) return;
    if (!visibleFaculty.some((f) => String(f.id) === String(form.faculty_id))) {
      setForm((current) => ({ ...current, faculty_id: '' }));
    }
  }, [visibleFaculty, form.faculty_id]);

  const validateForm = () => {
    const errors = {};
    if (!form.course_id) errors.course_id = 'Select a course.';
    if (!form.semester_id) errors.semester_id = 'Select a semester.';
    if (!form.subject_id) errors.subject_id = 'Select a subject.';
    if (!form.section_id) errors.section_id = 'Select a section.';
    if (!form.faculty_id) errors.faculty_id = 'Select a faculty member.';
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!validateForm()) return;

    const payload = {
      faculty_id: Number(form.faculty_id),
      subject_id: Number(form.subject_id),
      section_id: Number(form.section_id),
      notes: form.notes.trim() || null,
      is_active: form.is_active,
    };

    // A subject+section pair holds exactly one faculty. If the pair is already
    // taken, offer to replace rather than letting the server 409.
    if (!editingId) {
      const existing = assignments.find(
        (a) => a.subject_id === payload.subject_id && a.section_id === payload.section_id,
      );
      if (existing) {
        const replacement = facultyList.find((f) => f.id === payload.faculty_id);
        const confirmed = window.confirm(
          `${existing.subject_code} for ${existing.section_name} is currently taught by ${existing.faculty_name}.\n\n` +
            `Replace with ${replacement?.full_name || 'the selected faculty member'}?`,
        );
        if (!confirmed) return;

        setSaving(true);
        try {
          await teachingAssignmentService.update(existing.id, payload);
          setNotice(`${existing.subject_code} · ${existing.section_name} reassigned.`);
          closeModal();
          fetchAssignments();
        } catch (err) {
          setError(err?.response?.data?.detail || 'Operation failed.');
        } finally {
          setSaving(false);
        }
        return;
      }
    }

    setSaving(true);
    setError('');
    try {
      if (editingId) {
        const updated = await teachingAssignmentService.update(editingId, payload);
        setNotice(`${updated.subject_code} · ${updated.section_name} → ${updated.faculty_name}.`);
      } else {
        const created = await teachingAssignmentService.create(payload);
        setNotice(`${created.subject_code} · ${created.section_name} assigned to ${created.faculty_name}.`);
      }
      closeModal();
      fetchAssignments();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Operation failed.');
    } finally {
      setSaving(false);
    }
  };

  // ------------------------------------------------------ bulk assign

  const openBulkModal = async () => {
    setBulkForm(emptyBulkForm);
    setBulkErrors({});
    setBulkShowAllFaculty(false);
    setError('');
    setBulkOpen(true);
    await loadChain(emptyBulkForm, setBulkOptions);
  };

  const handleBulkFieldChange = (name, value) => {
    setBulkForm((current) => ({ ...current, [name]: value }));
    setBulkErrors((current) => ({ ...current, [name]: '' }));
  };

  const handleBulkLevelChange = async (level, value) => {
    if (level === 'faculty_id') {
      handleBulkFieldChange(level, value);
      return;
    }

    const next = { ...bulkForm, [level]: value, section_ids: [] };
    const index = CHAIN.indexOf(level);
    if (index !== -1) CHAIN.slice(index + 1).forEach((k) => { if (k in next) next[k] = ''; });

    setBulkForm(next);
    setBulkErrors({});
    await loadChain(next, setBulkOptions);
  };

  const toggleBulkSection = (sectionId) => {
    setBulkForm((current) => ({
      ...current,
      section_ids: current.section_ids.includes(sectionId)
        ? current.section_ids.filter((id) => id !== sectionId)
        : [...current.section_ids, sectionId],
    }));
    setBulkErrors((current) => ({ ...current, section_ids: '' }));
  };

  const handleBulkSubmit = async (event) => {
    event.preventDefault();

    const errors = {};
    if (!bulkForm.course_id) errors.course_id = 'Select a course.';
    if (!bulkForm.semester_id) errors.semester_id = 'Select a semester.';
    if (!bulkForm.subject_id) errors.subject_id = 'Select a subject.';
    if (!bulkForm.faculty_id) errors.faculty_id = 'Select a faculty member.';
    if (!bulkForm.section_ids.length) errors.section_ids = 'Choose at least one section.';
    setBulkErrors(errors);
    if (Object.keys(errors).length) return;

    setSaving(true);
    setError('');
    try {
      const result = await teachingAssignmentService.bulkAssign({
        faculty_id: Number(bulkForm.faculty_id),
        subject_id: Number(bulkForm.subject_id),
        section_ids: bulkForm.section_ids.map(Number),
        notes: bulkForm.notes.trim() || null,
        is_active: bulkForm.is_active,
      });
      const skippedNote = result.skipped.length
        ? ` ${result.skipped.length} skipped — already assigned.`
        : '';
      setNotice(`Assigned to ${result.created.length} section(s).${skippedNote}`);
      setBulkOpen(false);
      setBulkForm(emptyBulkForm);
      fetchAssignments();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Bulk assignment failed.');
    } finally {
      setSaving(false);
    }
  };

  // ------------------------------------------------------ row actions

  const handleToggleStatus = async (assignment) => {
    const next = !assignment.is_active;
    if (!window.confirm(`${next ? 'Activate' : 'Deactivate'} ${assignment.subject_code} · ${assignment.section_name}?`)) {
      return;
    }

    setBusyRowId(assignment.id);
    try {
      await teachingAssignmentService.setStatus(assignment.id, next);
      setNotice(`${assignment.subject_code} · ${assignment.section_name} is now ${next ? 'active' : 'inactive'}.`);
      fetchAssignments();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not change the status.');
    } finally {
      setBusyRowId(null);
    }
  };

  const handleDelete = async (assignment) => {
    const confirmed = window.confirm(
      `Remove ${assignment.faculty_name} from ${assignment.subject_code} · ${assignment.section_name}?\n\n` +
        'Once attendance and marks reference this assignment, removing it destroys that history. ' +
        'Deactivate it instead to pause the assignment.',
    );
    if (!confirmed) return;

    setBusyRowId(assignment.id);
    try {
      await teachingAssignmentService.remove(assignment.id);
      setNotice(`${assignment.subject_code} · ${assignment.section_name} assignment removed.`);
      fetchAssignments();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not remove this assignment.');
    } finally {
      setBusyRowId(null);
    }
  };

  // ---------------------------------------------------------- render

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel department-page">
        <header className="topbar page-topbar">
          <div className="welcome-text">
            <strong>Teaching Assignments</strong>
            <span className="page-subtitle">
              Decide who teaches which subject to which section — the mapping Attendance and Marks build on.
            </span>
          </div>

          <div className="topbar-right">
            <button type="button" className="secondary-btn" onClick={openBulkModal}>Bulk Assign</button>
            <button type="button" className="primary-btn department-primary-btn" onClick={openCreateModal}>
              + Assign Subject
            </button>
          </div>
        </header>

        <section className="mini-stats">
          <div className="mini-stat">
            <span className="mini-stat-label">Total Assignments</span>
            <strong className="mini-stat-value">{stats.total}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Active</span>
            <strong className="mini-stat-value tone-green">{stats.active}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Inactive</span>
            <strong className="mini-stat-value tone-gray">{stats.inactive}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Sections Covered</span>
            <strong className="mini-stat-value tone-blue">{stats.sections}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Faculty Engaged</span>
            <strong className="mini-stat-value tone-blue">{stats.faculty}</strong>
          </div>
        </section>

        <TeachingAssignmentFilters
          search={search}
          onSearchChange={setSearch}
          filters={filters}
          onFilterChange={handleFilterChange}
          departments={departments}
          courses={filterOptions.courses}
          semesters={filterOptions.semesters}
          subjects={filterOptions.subjects}
          sections={filterOptions.sections}
          activeFilterCount={activeFilterCount}
          onReset={resetFilters}
        />

        {error && <div className="error-box dismissable" onClick={() => setError('')} role="alert">{error}</div>}
        {notice && <div className="success-box dismissable" onClick={() => setNotice('')} role="status">{notice}</div>}

        <TeachingAssignmentTable
          assignments={visibleAssignments}
          loading={loading}
          hasFilters={Boolean(activeFilterCount)}
          sort={sort}
          onSort={toggleSort}
          onView={setDetailsFor}
          onReassign={(item) => openEditModal(item, { lock: true })}
          onEdit={(item) => openEditModal(item, { lock: false })}
          onToggleStatus={handleToggleStatus}
          onDelete={handleDelete}
          busyRowId={busyRowId}
        />

        {!loading && sortedAssignments.length > 0 && (
          <div className="table-footer">
            <span>
              Showing {(currentPage - 1) * pageSize + 1}–
              {Math.min(currentPage * pageSize, sortedAssignments.length)} of {sortedAssignments.length}
            </span>
            <div className="pager">
              <label className="page-size">
                Rows
                <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}>
                  {PAGE_SIZES.map((size) => (
                    <option key={size} value={size}>{size}</option>
                  ))}
                </select>
              </label>
              <button type="button" className="table-btn neutral-btn" onClick={() => setPage(currentPage - 1)} disabled={currentPage <= 1}>
                Previous
              </button>
              <span className="page-indicator">Page {currentPage} of {totalPages}</span>
              <button type="button" className="table-btn neutral-btn" onClick={() => setPage(currentPage + 1)} disabled={currentPage >= totalPages}>
                Next
              </button>
            </div>
          </div>
        )}
      </main>

      {modalOpen && (
        <div className="modal-backdrop" onClick={closeModal}>
          <div className="modal-card wide" onClick={(e) => e.stopPropagation()}>
            <h3>
              {lockPlacement ? 'Reassign Faculty' : editingId ? 'Edit Assignment' : 'Assign Subject to Section'}
            </h3>
            <p className="modal-hint">
              Subjects and sections are both drawn from the semester you pick, so an incompatible
              pair cannot be chosen.
            </p>
            <TeachingAssignmentForm
              editing={Boolean(editingId)}
              lockPlacement={lockPlacement}
              form={form}
              errors={formErrors}
              departments={departments}
              courses={formOptions.courses}
              semesters={formOptions.semesters}
              subjects={formOptions.subjects}
              sections={formOptions.sections}
              visibleFaculty={visibleFaculty}
              showAllFaculty={showAllFaculty}
              onToggleShowAllFaculty={() => setShowAllFaculty((v) => !v)}
              selectedSubject={selectedSubject}
              selectedFaculty={selectedFaculty}
              currentFacultyName={currentFacultyName}
              saving={saving}
              onLevelChange={handleLevelChange}
              onFieldChange={handleFieldChange}
              onSubmit={handleSubmit}
              onCancel={closeModal}
            />
          </div>
        </div>
      )}

      {bulkOpen && (
        <div className="modal-backdrop" onClick={() => setBulkOpen(false)}>
          <div className="modal-card wide" onClick={(e) => e.stopPropagation()}>
            <h3>Bulk Assign</h3>
            <p className="modal-hint">
              Assign one faculty member to one subject across several sections of the same semester.
            </p>
            <BulkAssignForm
              form={bulkForm}
              errors={bulkErrors}
              departments={departments}
              courses={bulkOptions.courses}
              semesters={bulkOptions.semesters}
              subjects={bulkOptions.subjects}
              sections={bulkOptions.sections}
              visibleFaculty={bulkVisibleFaculty}
              showAllFaculty={bulkShowAllFaculty}
              onToggleShowAllFaculty={() => setBulkShowAllFaculty((v) => !v)}
              selectedSubject={bulkSelectedSubject}
              existingBySection={existingBySection}
              saving={saving}
              onLevelChange={handleBulkLevelChange}
              onFieldChange={handleBulkFieldChange}
              onToggleSection={toggleBulkSection}
              onSubmit={handleBulkSubmit}
              onCancel={() => setBulkOpen(false)}
            />
          </div>
        </div>
      )}

      {detailsFor && (
        <TeachingAssignmentDetails
          assignment={detailsFor}
          onClose={() => setDetailsFor(null)}
          onReassign={(item) => openEditModal(item, { lock: true })}
        />
      )}
    </div>
  );
}
