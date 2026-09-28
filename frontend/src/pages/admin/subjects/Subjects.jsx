import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminSidebar from '../../../components/AdminSidebar';
import SubjectFilters from '../../../components/subjects/SubjectFilters';
import SubjectTable from '../../../components/subjects/SubjectTable';
import SubjectForm from '../../../components/subjects/SubjectForm';
import SubjectDetails from '../../../components/subjects/SubjectDetails';
import subjectService from '../../../services/subjectService';

const PAGE_SIZES = [10, 25, 50, 100];

const emptyForm = {
  course_id: '',
  semester_id: '',
  subject_code: '',
  name: '',
  description: '',
  credits: '4',
  subject_type: 'THEORY',
  lecture_hours: '3',
  tutorial_hours: '1',
  practical_hours: '0',
  is_active: true,
};

const emptyFilters = {
  department_id: '',
  course_id: '',
  semester_id: '',
  subject_type: '',
  is_active: '',
};

export default function Subjects() {
  const navigate = useNavigate();
  const token = localStorage.getItem('smart_college_token');

  const [subjects, setSubjects] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [subjectTypes, setSubjectTypes] = useState([]);

  const [filterCourses, setFilterCourses] = useState([]);
  const [filterSemesters, setFilterSemesters] = useState([]);
  const [formCourses, setFormCourses] = useState([]);
  const [formSemesters, setFormSemesters] = useState([]);

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
  const [form, setForm] = useState(emptyForm);
  const [formErrors, setFormErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const [detailsFor, setDetailsFor] = useState(null);
  const [busyRowId, setBusyRowId] = useState(null);

  // ---------------------------------------------------------------- data

  const fetchSubjects = useCallback(async () => {
    try {
      setSubjects(await subjectService.list({ ...filters, search: debouncedSearch.trim() }));
      setError('');
    } catch (err) {
      if (err?.response?.status === 401) {
        navigate('/login');
        return;
      }
      setError(err?.response?.data?.detail || 'Unable to load subjects.');
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
        const [departmentList, options, courseList] = await Promise.all([
          subjectService.departments(),
          subjectService.options(),
          subjectService.courses(),
        ]);
        setDepartments(departmentList);
        setSubjectTypes(options.subject_types);
        setFilterCourses(courseList);
        setFormCourses(courseList);
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
    fetchSubjects();
  }, [token, fetchSubjects]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, filters, pageSize]);

  // Filter bar: department narrows the courses, course narrows the semesters.
  useEffect(() => {
    if (!token) return;
    subjectService
      .courses(filters.department_id)
      .then(setFilterCourses)
      .catch(() => setFilterCourses([]));
  }, [token, filters.department_id]);

  useEffect(() => {
    if (!token) return;
    subjectService
      .semesters(filters.course_id)
      .then(setFilterSemesters)
      .catch(() => setFilterSemesters([]));
  }, [token, filters.course_id]);

  // --------------------------------------------------------- derived

  const stats = useMemo(() => {
    const active = subjects.filter((s) => s.is_active).length;
    return {
      total: subjects.length,
      active,
      inactive: subjects.length - active,
      credits: subjects.reduce((sum, s) => sum + (s.is_active ? s.credits : 0), 0),
    };
  }, [subjects]);

  const sortedSubjects = useMemo(() => {
    const rows = [...subjects];
    const { key, direction } = sort;
    const factor = direction === 'asc' ? 1 : -1;
    rows.sort((a, b) => {
      const left = a[key];
      const right = b[key];
      if (['credits', 'semester_number'].includes(key)) return ((left ?? 0) - (right ?? 0)) * factor;
      if (key === 'is_active') return (Number(left) - Number(right)) * factor;
      return String(left ?? '').localeCompare(String(right ?? ''), undefined, { numeric: true }) * factor;
    });
    return rows;
  }, [subjects, sort]);

  const totalPages = Math.max(1, Math.ceil(sortedSubjects.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visibleSubjects = useMemo(
    () => sortedSubjects.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [sortedSubjects, currentPage, pageSize],
  );

  const activeFilterCount = Object.values(filters).filter(Boolean).length + (search.trim() ? 1 : 0);

  const toggleSort = (key) =>
    setSort((c) => ({ key, direction: c.key === key && c.direction === 'asc' ? 'desc' : 'asc' }));

  const handleFilterChange = (key, value) => {
    setFilters((current) => {
      const next = { ...current, [key]: value };
      // clearing a parent clears what depends on it
      if (key === 'department_id') {
        next.course_id = '';
        next.semester_id = '';
      }
      if (key === 'course_id') next.semester_id = '';
      return next;
    });
  };

  const resetFilters = () => {
    setFilters(emptyFilters);
    setSearch('');
  };

  // ----------------------------------------------------------- modal

  const openCreateModal = async () => {
    setEditingId(null);
    setForm(emptyForm);
    setFormErrors({});
    setError('');
    setFormSemesters([]);
    setModalOpen(true);

    try {
      setFormCourses(await subjectService.courses());
    } catch {
      setError('Unable to load courses.');
    }
  };

  const openEditModal = async (subject) => {
    setEditingId(subject.id);
    setForm({
      course_id: String(subject.course_id),
      semester_id: String(subject.semester_id),
      subject_code: subject.subject_code,
      name: subject.name,
      description: subject.description || '',
      credits: String(subject.credits),
      subject_type: subject.subject_type,
      lecture_hours: String(subject.lecture_hours),
      tutorial_hours: String(subject.tutorial_hours),
      practical_hours: String(subject.practical_hours),
      is_active: subject.is_active,
    });
    setFormErrors({});
    setError('');
    setDetailsFor(null);
    setModalOpen(true);

    try {
      const [courseList, semesterList] = await Promise.all([
        subjectService.courses(),
        subjectService.semesters(subject.course_id),
      ]);
      setFormCourses(courseList);
      setFormSemesters(semesterList);
    } catch {
      setError('Unable to load the academic options.');
    }
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
    setForm(emptyForm);
    setFormErrors({});
  };

  const handleFieldChange = (name, value) => {
    setForm((current) => ({ ...current, [name]: value }));
    setFormErrors((current) => ({ ...current, [name]: '' }));
  };

  /** Changing the course resets the semester and reloads its options. */
  const handleCourseChange = async (courseId) => {
    setForm((current) => ({ ...current, course_id: courseId, semester_id: '' }));
    setFormErrors((current) => ({ ...current, course_id: '', semester_id: '' }));
    try {
      setFormSemesters(await subjectService.semesters(courseId));
    } catch {
      setFormSemesters([]);
    }
  };

  const validateForm = () => {
    const errors = {};
    if (!form.course_id) errors.course_id = 'Select a course.';
    if (!form.semester_id) errors.semester_id = 'Select a semester.';
    if (!form.subject_code.trim()) errors.subject_code = 'Subject code is required.';
    if (!form.name.trim()) errors.name = 'Subject name is required.';
    if (!form.subject_type) errors.subject_type = 'Select a subject type.';
    if (!(Number(form.credits) > 0)) errors.credits = 'Credits must be greater than zero.';

    const hours = ['lecture_hours', 'tutorial_hours', 'practical_hours'].map((k) => Number(form[k]) || 0);
    if (hours.some((h) => h < 0)) errors.hours = 'Hours cannot be negative.';
    else if (hours.reduce((a, b) => a + b, 0) === 0) {
      errors.hours = 'Add at least one lecture, tutorial, or practical hour.';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!validateForm()) return;

    setSaving(true);
    setError('');

    const payload = {
      course_id: Number(form.course_id),
      semester_id: Number(form.semester_id),
      subject_code: form.subject_code.trim().toUpperCase(),
      name: form.name.trim(),
      description: form.description.trim() || null,
      credits: Number(form.credits),
      subject_type: form.subject_type,
      lecture_hours: Number(form.lecture_hours) || 0,
      tutorial_hours: Number(form.tutorial_hours) || 0,
      practical_hours: Number(form.practical_hours) || 0,
      is_active: form.is_active,
    };

    try {
      if (editingId) {
        await subjectService.update(editingId, payload);
        setNotice(`${payload.subject_code} was updated.`);
      } else {
        const created = await subjectService.create(payload);
        setNotice(`${created.subject_code} — ${created.name} was added to the curriculum.`);
      }
      closeModal();
      fetchSubjects();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Operation failed.');
    } finally {
      setSaving(false);
    }
  };

  // ------------------------------------------------------ row actions

  const handleToggleStatus = async (subject) => {
    const next = !subject.is_active;
    if (!window.confirm(`${next ? 'Activate' : 'Deactivate'} ${subject.subject_code}?`)) return;

    setBusyRowId(subject.id);
    try {
      await subjectService.setStatus(subject.id, next);
      setNotice(`${subject.subject_code} is now ${next ? 'active' : 'inactive'}.`);
      fetchSubjects();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not change the status.');
    } finally {
      setBusyRowId(null);
    }
  };

  const handleDelete = async (subject) => {
    const confirmed = window.confirm(
      `Delete ${subject.subject_code} — ${subject.name} permanently?\n\nOnce teaching assignments, attendance, or marks reference this subject, deleting it destroys that history. Deactivate it instead to retire it from the curriculum.`,
    );
    if (!confirmed) return;

    setBusyRowId(subject.id);
    try {
      await subjectService.remove(subject.id);
      setNotice(`${subject.subject_code} was deleted.`);
      fetchSubjects();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not delete this subject.');
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
            <strong>Subject Management</strong>
            <span className="page-subtitle">
              Define what is taught in each course and semester of the curriculum.
            </span>
          </div>

          <div className="topbar-right">
            <button type="button" className="primary-btn department-primary-btn" onClick={openCreateModal}>
              + Add Subject
            </button>
          </div>
        </header>

        <section className="mini-stats">
          <div className="mini-stat">
            <span className="mini-stat-label">Total Subjects</span>
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
            <span className="mini-stat-label">Active Credits</span>
            <strong className="mini-stat-value tone-blue">{stats.credits}</strong>
          </div>
        </section>

        <SubjectFilters
          search={search}
          onSearchChange={setSearch}
          filters={filters}
          onFilterChange={handleFilterChange}
          departments={departments}
          courses={filterCourses}
          semesters={filterSemesters}
          subjectTypes={subjectTypes}
          activeFilterCount={activeFilterCount}
          onReset={resetFilters}
        />

        {error && <div className="error-box dismissable" onClick={() => setError('')} role="alert">{error}</div>}
        {notice && <div className="success-box dismissable" onClick={() => setNotice('')} role="status">{notice}</div>}

        <SubjectTable
          subjects={visibleSubjects}
          loading={loading}
          hasFilters={Boolean(activeFilterCount)}
          sort={sort}
          onSort={toggleSort}
          onView={setDetailsFor}
          onEdit={openEditModal}
          onToggleStatus={handleToggleStatus}
          onDelete={handleDelete}
          busyRowId={busyRowId}
        />

        {!loading && sortedSubjects.length > 0 && (
          <div className="table-footer">
            <span>
              Showing {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, sortedSubjects.length)} of{' '}
              {sortedSubjects.length}
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
            <h3>{editingId ? 'Edit Subject' : 'Add New Subject'}</h3>
            <p className="modal-hint">
              A subject belongs to one course and one semester. Changing the course reloads the semesters
              so an invalid pair cannot be saved.
            </p>
            <SubjectForm
              editing={Boolean(editingId)}
              form={form}
              errors={formErrors}
              courses={formCourses}
              semesters={formSemesters}
              subjectTypes={subjectTypes}
              saving={saving}
              onFieldChange={handleFieldChange}
              onCourseChange={handleCourseChange}
              onSubmit={handleSubmit}
              onCancel={closeModal}
            />
          </div>
        </div>
      )}

      {detailsFor && (
        <SubjectDetails subject={detailsFor} onClose={() => setDetailsFor(null)} onEdit={openEditModal} />
      )}
    </div>
  );
}
