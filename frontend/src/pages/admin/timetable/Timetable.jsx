import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminSidebar from '../../../components/AdminSidebar';
import TimetableScopePicker from '../../../components/timetable/TimetableScopePicker';
import TimetableGrid from '../../../components/timetable/TimetableGrid';
import TimetableEntryForm from '../../../components/timetable/TimetableEntryForm';
import CoveragePanel from '../../../components/timetable/CoveragePanel';
import CopyDayForm from '../../../components/timetable/CopyDayForm';
import EntryDetails from '../../../components/timetable/EntryDetails';
import timetableService, {
  ALL_DAYS,
  DAY_NAMES,
  WORKING_DAYS,
  apiErrorMessage,
} from '../../../services/timetableService';

// Department → Course → Semester → Section. Changing a level clears
// everything after it, so the section can never belong to a semester the
// admin has already navigated away from.
const CHAIN = ['department_id', 'course_id', 'semester_id', 'section_id'];

const emptyScope = { department_id: '', course_id: '', semester_id: '', section_id: '' };
const emptyOptions = { courses: [], semesters: [], sections: [] };
const emptyForm = {
  teaching_assignment_id: '',
  day_of_week: '',
  time_slot_id: '',
  room_number: '',
  is_active: true,
};

export default function Timetable() {
  const navigate = useNavigate();
  const token = localStorage.getItem('smart_college_token');

  const [departments, setDepartments] = useState([]);
  const [scopeOptions, setScopeOptions] = useState(emptyOptions);
  const [scope, setScope] = useState(emptyScope);

  const [slots, setSlots] = useState([]);
  const [entries, setEntries] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [coverage, setCoverage] = useState(null);
  const [showWeekend, setShowWeekend] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const [busyEntryId, setBusyEntryId] = useState(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [formErrors, setFormErrors] = useState({});
  const [formError, setFormError] = useState('');

  const [copyOpen, setCopyOpen] = useState(false);
  const [copyForm, setCopyForm] = useState({ from_day: '0', to_day: '1' });
  const [copyError, setCopyError] = useState('');
  const [copyResult, setCopyResult] = useState(null);

  const [detailsFor, setDetailsFor] = useState(null);
  const [placingAssignmentId, setPlacingAssignmentId] = useState('');

  const days = useMemo(() => (showWeekend ? ALL_DAYS : WORKING_DAYS), [showWeekend]);

  // ---------------------------------------------------------------- data

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }

    const loadReferenceData = async () => {
      try {
        const [departmentList, courses, timeSlots] = await Promise.all([
          timetableService.departments(),
          timetableService.courses(),
          timetableService.timeSlots(true),
        ]);
        setDepartments(departmentList);
        setScopeOptions((current) => ({ ...current, courses }));
        setSlots(timeSlots);
      } catch (err) {
        if (err?.response?.status === 401) {
          navigate('/login');
          return;
        }
        setError(apiErrorMessage(err, 'Unable to load reference data.'));
      }
    };

    loadReferenceData();
  }, [token, navigate]);

  /** Reload only the levels below whichever one changed. */
  const loadChain = useCallback(async (selection) => {
    const next = { ...emptyOptions };
    try {
      next.courses = await timetableService.courses(selection.department_id || undefined);
      if (selection.course_id) {
        next.semesters = await timetableService.semesters(selection.course_id);
      }
      if (selection.semester_id) {
        next.sections = await timetableService.sections(selection.semester_id);
      }
    } catch (err) {
      setError(apiErrorMessage(err, 'Unable to load academic options.'));
    }
    // Set even on failure, so stale options from the previous level cannot linger.
    setScopeOptions(next);
  }, []);

  useEffect(() => {
    if (!token) return;
    loadChain(scope);
  }, [token, loadChain, scope.department_id, scope.course_id, scope.semester_id]);

  /**
   * allSettled rather than all: a failing coverage call must never blank the
   * grid the admin is working in.
   */
  const fetchGrid = useCallback(async () => {
    if (!scope.section_id) {
      setEntries([]);
      setAssignments([]);
      setCoverage(null);
      return;
    }

    setLoading(true);
    const [entryResult, assignmentResult, coverageResult] = await Promise.allSettled([
      timetableService.forSection(scope.section_id),
      timetableService.assignmentsForSection(scope.section_id),
      timetableService.coverage(scope.section_id),
    ]);

    const unauthorized = [entryResult, assignmentResult, coverageResult].some(
      (result) => result.status === 'rejected' && result.reason?.response?.status === 401,
    );
    if (unauthorized) {
      navigate('/login');
      return;
    }

    if (entryResult.status === 'fulfilled') {
      setEntries(entryResult.value);
      setError('');
    } else {
      setEntries([]);
      setError(apiErrorMessage(entryResult.reason, 'Unable to load this section’s timetable.'));
    }

    setAssignments(assignmentResult.status === 'fulfilled' ? assignmentResult.value : []);
    setCoverage(coverageResult.status === 'fulfilled' ? coverageResult.value : null);
    setLoading(false);
  }, [scope.section_id, navigate]);

  useEffect(() => {
    fetchGrid();
  }, [fetchGrid]);

  // ------------------------------------------------------------- derived

  const selectedSection = useMemo(
    () => scopeOptions.sections.find((s) => String(s.id) === String(scope.section_id)) || null,
    [scopeOptions.sections, scope.section_id],
  );

  const placingAssignment = useMemo(
    () => assignments.find((a) => String(a.id) === String(placingAssignmentId)) || null,
    [assignments, placingAssignmentId],
  );

  const placingLabel = placingAssignment
    ? `${placingAssignment.subject_code} — ${placingAssignment.subject_name}`
    : '';

  const stats = useMemo(() => {
    const active = entries.filter((e) => e.is_active).length;
    const teachingSlots = slots.filter((s) => !s.is_break).length;
    return {
      placed: active,
      paused: entries.length - active,
      free: Math.max(0, days.length * teachingSlots - entries.length),
      scheduled: coverage ? `${coverage.total_scheduled}/${coverage.total_required}` : '—',
      complete: coverage ? coverage.subjects.filter((s) => s.status === 'COMPLETE').length : '—',
    };
  }, [entries, slots, days, coverage]);

  /**
   * Entries the grid cannot show — their period was deactivated after the
   * class was placed, or they sit on a day that is currently hidden. They
   * still occupy their cell for clash purposes, so they must stay reachable.
   */
  const offGrid = useMemo(() => {
    const slotIds = new Set(slots.map((s) => s.id));
    return entries.filter((e) => !slotIds.has(e.time_slot_id) || !days.includes(e.day_of_week));
  }, [entries, slots, days]);

  // -------------------------------------------------------------- scope

  const handleScopeChange = (key, value) => {
    setScope((current) => {
      const next = { ...current, [key]: value };
      const index = CHAIN.indexOf(key);
      if (index !== -1) CHAIN.slice(index + 1).forEach((k) => { next[k] = ''; });
      return next;
    });
    setPlacingAssignmentId('');
  };

  const resetScope = () => {
    setScope(emptyScope);
    setPlacingAssignmentId('');
  };

  // --------------------------------------------------------------- form

  const openCreate = (day, slot) => {
    setEditingEntry(null);
    setFormErrors({});
    setFormError('');
    setForm({
      teaching_assignment_id: placingAssignmentId ? String(placingAssignmentId) : '',
      day_of_week: String(day),
      time_slot_id: String(slot.id),
      room_number: '',
      is_active: true,
    });
    setModalOpen(true);
  };

  const openEdit = (entry) => {
    setEditingEntry(entry);
    setFormErrors({});
    setFormError('');
    setDetailsFor(null);
    setForm({
      teaching_assignment_id: String(entry.teaching_assignment_id),
      day_of_week: String(entry.day_of_week),
      time_slot_id: String(entry.time_slot_id),
      // serialize() returns the EFFECTIVE room, so prefilling it verbatim
      // would turn "use the section's room" into an explicit pin.
      room_number: entry.is_relocated ? entry.room_number || '' : '',
      is_active: entry.is_active,
    });
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingEntry(null);
    setForm(emptyForm);
    setFormErrors({});
    setFormError('');
  };

  const handleFieldChange = (name, value) => {
    setForm((current) => ({ ...current, [name]: value }));
    setFormErrors((current) => ({ ...current, [name]: '' }));
  };

  /** The paused teaching assignment an edited entry may still point at. */
  const extraAssignment = useMemo(() => {
    if (!editingEntry) return null;
    const known = assignments.some(
      (a) => String(a.id) === String(editingEntry.teaching_assignment_id),
    );
    if (known) return null;
    return {
      id: editingEntry.teaching_assignment_id,
      subject_code: editingEntry.subject_code,
      subject_name: editingEntry.subject_name,
      faculty_name: editingEntry.faculty_name,
      is_paused: true,
    };
  }, [editingEntry, assignments]);

  const handleSubmit = async (event) => {
    event.preventDefault();

    const errors = {};
    if (!form.teaching_assignment_id) errors.teaching_assignment_id = 'Choose what to place.';
    // '0' is Monday — an emptiness check must compare to '', not be falsy.
    if (form.day_of_week === '') errors.day_of_week = 'Choose a day.';
    if (!form.time_slot_id) errors.time_slot_id = 'Choose a period.';
    setFormErrors(errors);
    if (Object.keys(errors).length) return;

    const payload = {
      teaching_assignment_id: Number(form.teaching_assignment_id),
      day_of_week: Number(form.day_of_week),
      time_slot_id: Number(form.time_slot_id),
      room_number: form.room_number.trim() || null,
      is_active: form.is_active,
    };

    setSaving(true);
    setFormError('');
    try {
      const saved = editingEntry
        ? await timetableService.update(editingEntry.id, payload)
        : await timetableService.create(payload);
      setNotice(`${saved.subject_code} · ${saved.day_name} ${saved.slot_name} saved.`);
      setPlacingAssignmentId('');
      closeModal();
      await fetchGrid();
    } catch (err) {
      // A clash names the class it collides with — that sentence is the only
      // thing that tells the admin what to move, so it stays in the modal.
      setFormError(apiErrorMessage(err, 'Could not save this class.'));
    } finally {
      setSaving(false);
    }
  };

  // ------------------------------------------------------- entry actions

  const handleToggleStatus = async (entry) => {
    const next = !entry.is_active;
    const question = next
      ? `Resume ${entry.subject_code} on ${entry.day_name} ${entry.slot_name}?`
      : `Pause ${entry.subject_code} on ${entry.day_name} ${entry.slot_name}?\n\n` +
        'It keeps its place on the grid, so nothing else can be scheduled there.';
    if (!window.confirm(question)) return;

    setBusyEntryId(entry.id);
    try {
      await timetableService.setStatus(entry.id, next);
      setNotice(`${entry.subject_code} is now ${next ? 'active' : 'paused'}.`);
      await fetchGrid();
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not change the status.'));
    } finally {
      setBusyEntryId(null);
    }
  };

  const handleDelete = async (entry) => {
    const confirmed = window.confirm(
      `Remove ${entry.subject_code} from ${entry.day_name} ${entry.slot_name}?\n\n` +
        'Once attendance references this class, removing it destroys that history. ' +
        'Pause it instead to take it off the week without losing the record.',
    );
    if (!confirmed) return;

    setBusyEntryId(entry.id);
    try {
      await timetableService.remove(entry.id);
      setNotice(`${entry.subject_code} removed from ${entry.day_name}.`);
      setDetailsFor(null);
      await fetchGrid();
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not remove this class.'));
    } finally {
      setBusyEntryId(null);
    }
  };

  // ----------------------------------------------------------- copy day

  const openCopy = () => {
    setCopyForm({ from_day: String(days[0]), to_day: String(days[1] ?? days[0]) });
    setCopyError('');
    setCopyResult(null);
    setCopyOpen(true);
  };

  const handleCopySubmit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setCopyError('');
    try {
      const result = await timetableService.copyDay({
        section_id: Number(scope.section_id),
        from_day: Number(copyForm.from_day),
        to_day: Number(copyForm.to_day),
      });
      setCopyResult(result);
      const skippedNote = result.skipped.length ? ` ${result.skipped.length} skipped.` : '';
      setNotice(
        `Copied ${result.created.length} class(es) to ${DAY_NAMES[Number(copyForm.to_day)]}.${skippedNote}`,
      );
      await fetchGrid();
    } catch (err) {
      setCopyError(apiErrorMessage(err, 'Could not copy this day.'));
    } finally {
      setSaving(false);
    }
  };

  // ------------------------------------------------------------- render

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel department-page">
        <header className="topbar page-topbar">
          <div className="welcome-text">
            <strong>Timetable</strong>
            <span className="page-subtitle">
              Place each teaching assignment on the week. A faculty member, a section and a room can
              each hold only one class per period.
            </span>
          </div>

          <div className="topbar-right">
            <button
              type="button"
              className="secondary-btn"
              onClick={openCopy}
              disabled={!scope.section_id}
            >
              Copy Day
            </button>
            <button
              type="button"
              className="primary-btn department-primary-btn"
              onClick={() => openCreate(days[0], slots.find((s) => !s.is_break) || { id: '', name: '' })}
              disabled={!scope.section_id || !slots.some((s) => !s.is_break)}
            >
              + Place Class
            </button>
          </div>
        </header>

        <TimetableScopePicker
          scope={scope}
          departments={departments}
          courses={scopeOptions.courses}
          semesters={scopeOptions.semesters}
          sections={scopeOptions.sections}
          showWeekend={showWeekend}
          onChange={handleScopeChange}
          onToggleWeekend={() => setShowWeekend((v) => !v)}
          onReset={resetScope}
        />

        {scope.section_id && (
          <section className="mini-stats">
            <div className="mini-stat">
              <span className="mini-stat-label">Classes Placed</span>
              <strong className="mini-stat-value tone-green">{stats.placed}</strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Paused</span>
              <strong className="mini-stat-value tone-gray">{stats.paused}</strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Free Periods</span>
              <strong className="mini-stat-value tone-blue">{stats.free}</strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Scheduled / Required</span>
              <strong className="mini-stat-value tone-blue">{stats.scheduled}</strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Subjects Complete</span>
              <strong className="mini-stat-value tone-green">{stats.complete}</strong>
            </div>
          </section>
        )}

        {error && <div className="error-box dismissable" onClick={() => setError('')} role="alert">{error}</div>}
        {notice && <div className="success-box dismissable" onClick={() => setNotice('')} role="status">{notice}</div>}

        {placingLabel && (
          <div className="tt-placing-banner">
            <span>Placing <strong>{placingLabel}</strong> — click any empty cell.</span>
            <button type="button" className="secondary-btn" onClick={() => setPlacingAssignmentId('')}>
              Cancel
            </button>
          </div>
        )}

        {!scope.section_id ? (
          <div className="panel">
            <p className="empty-note">
              Choose a section to open its weekly grid. A timetable belongs to one section, which is
              what keeps a period from holding two classes.
            </p>
          </div>
        ) : (
          <div className="timetable-layout">
            <TimetableGrid
              slots={slots}
              days={days}
              entries={entries}
              loading={loading}
              placingLabel={placingLabel}
              busyEntryId={busyEntryId}
              onEmptyClick={openCreate}
              onView={setDetailsFor}
              onEdit={openEdit}
              onToggleStatus={handleToggleStatus}
              onDelete={handleDelete}
            />

            <CoveragePanel
              coverage={coverage}
              loading={loading}
              placingAssignmentId={placingAssignmentId}
              onPlace={setPlacingAssignmentId}
            />
          </div>
        )}

        {offGrid.length > 0 && (
          <section className="panel" style={{ marginTop: '18px' }}>
            <div className="panel-header">
              <h3>Classes outside the current grid</h3>
              <span className="panel-count">{offGrid.length}</span>
            </div>
            <p className="empty-note">
              These sit on a hidden day or in a period that is no longer active. They still occupy
              their slot, so nothing else can be scheduled over them.
            </p>
            <div className="department-table-wrap scroll-table">
              <table className="department-table">
                <thead>
                  <tr>
                    <th>Day</th>
                    <th>Period</th>
                    <th>Subject</th>
                    <th>Faculty</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {offGrid.map((entry) => (
                    <tr key={entry.id}>
                      <td>{entry.day_name || '—'}</td>
                      <td>{entry.slot_label || `Period ${entry.time_slot_id}`}</td>
                      <td>
                        <div className="dept-name">{entry.subject_name}</div>
                        <div className="dept-desc mono">{entry.subject_code}</div>
                      </td>
                      <td>{entry.faculty_name}</td>
                      <td>
                        <div className="action-buttons">
                          <button
                            type="button"
                            className="table-btn edit-btn"
                            onClick={() => openEdit(entry)}
                            disabled={busyEntryId === entry.id}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="table-btn delete-btn"
                            onClick={() => handleDelete(entry)}
                            disabled={busyEntryId === entry.id}
                          >
                            Remove
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>

      {modalOpen && (
        <div className="modal-backdrop" onClick={closeModal}>
          <div className="modal-card wide" onClick={(e) => e.stopPropagation()}>
            <h3>{editingEntry ? 'Edit Class' : 'Place a Class'}</h3>
            <p className="modal-hint">
              {selectedSection ? `${selectedSection.name} · ` : ''}
              Only subjects already assigned to this section can be scheduled.
            </p>
            <TimetableEntryForm
              editing={Boolean(editingEntry)}
              form={form}
              errors={formErrors}
              formError={formError}
              assignments={assignments}
              extraAssignment={extraAssignment}
              slots={slots}
              days={days}
              section={selectedSection}
              saving={saving}
              onFieldChange={handleFieldChange}
              onSubmit={handleSubmit}
              onCancel={closeModal}
            />
          </div>
        </div>
      )}

      {copyOpen && (
        <div className="modal-backdrop" onClick={() => setCopyOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Copy a Day</h3>
            <p className="modal-hint">
              Duplicate one day of {selectedSection?.name || 'this section'} onto another day of the
              same week.
            </p>
            <CopyDayForm
              form={copyForm}
              days={days}
              saving={saving}
              formError={copyError}
              result={copyResult}
              onFieldChange={(name, value) => setCopyForm((c) => ({ ...c, [name]: value }))}
              onSubmit={handleCopySubmit}
              onCancel={() => setCopyOpen(false)}
            />
          </div>
        </div>
      )}

      {detailsFor && (
        <EntryDetails entry={detailsFor} onClose={() => setDetailsFor(null)} onEdit={openEdit} />
      )}
    </div>
  );
}
