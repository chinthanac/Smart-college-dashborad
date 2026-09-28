/**
 * Create / Edit / Reassign.
 *
 * The chain forks at the semester: Subject and Section are both drawn from
 * the SAME selected semester, so `section.semester_id == subject.semester_id`
 * holds by construction and the backend check is only a safety net.
 *
 * In `lockPlacement` mode (Reassign) the academic selects are frozen and only
 * the faculty member can change — the row is edited, never duplicated.
 */
export default function TeachingAssignmentForm({
  editing,
  lockPlacement,
  form,
  errors,
  departments,
  courses,
  semesters,
  subjects,
  sections,
  visibleFaculty,
  showAllFaculty,
  onToggleShowAllFaculty,
  selectedSubject,
  selectedFaculty,
  currentFacultyName,
  saving,
  onLevelChange,
  onFieldChange,
  onSubmit,
  onCancel,
}) {
  const level = (name) => (e) => onLevelChange(name, e.target.value);
  const crossDepartment =
    selectedFaculty &&
    selectedSubject &&
    selectedFaculty.department_id !== selectedSubject.department_id;

  return (
    <form onSubmit={onSubmit} className="department-form form-grid">
      <div className="form-section span-2">Academic Placement</div>

      <label>
        Department
        <select value={form.department_id} onChange={level('department_id')} disabled={lockPlacement}>
          <option value="">All departments</option>
          {departments.map((item) => (
            <option key={item.id} value={item.id}>{item.name} ({item.code})</option>
          ))}
        </select>
      </label>

      <label>
        Course
        <select value={form.course_id} onChange={level('course_id')} disabled={lockPlacement || !courses.length}>
          <option value="">{courses.length ? 'Select course' : 'No courses available'}</option>
          {courses.map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
        {errors.course_id && <span className="field-error">{errors.course_id}</span>}
      </label>

      <label className="span-2">
        Semester
        <select value={form.semester_id} onChange={level('semester_id')} disabled={lockPlacement || !form.course_id}>
          <option value="">
            {!form.course_id
              ? 'Select a course first'
              : semesters.length ? 'Select semester' : 'No semesters for this course'}
          </option>
          {semesters.map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
        {errors.semester_id && <span className="field-error">{errors.semester_id}</span>}
      </label>

      <label>
        Subject
        <select value={form.subject_id} onChange={level('subject_id')} disabled={lockPlacement || !form.semester_id}>
          <option value="">
            {!form.semester_id
              ? 'Select a semester first'
              : subjects.length ? 'Select subject' : 'No active subjects in this semester'}
          </option>
          {subjects.map((item) => (
            <option key={item.id} value={item.id}>{item.subject_code} — {item.name}</option>
          ))}
        </select>
        {errors.subject_id && <span className="field-error">{errors.subject_id}</span>}
      </label>

      <label>
        Section
        <select value={form.section_id} onChange={level('section_id')} disabled={lockPlacement || !form.semester_id}>
          <option value="">
            {!form.semester_id
              ? 'Select a semester first'
              : sections.length ? 'Select section' : 'No sections in this semester'}
          </option>
          {sections.map((item) => (
            <option key={item.id} value={item.id}>{item.name} ({item.room_number})</option>
          ))}
        </select>
        {errors.section_id && <span className="field-error">{errors.section_id}</span>}
      </label>

      <div className="form-section span-2">Faculty</div>

      <label className="span-2">
        Faculty Member
        <select value={form.faculty_id} onChange={level('faculty_id')} disabled={!visibleFaculty.length}>
          <option value="">
            {visibleFaculty.length ? 'Select faculty member' : 'No active faculty available'}
          </option>
          {visibleFaculty.map((item) => (
            <option key={item.id} value={item.id}>
              {item.full_name} — {item.faculty_id} ({item.department_code})
            </option>
          ))}
        </select>
        {errors.faculty_id && <span className="field-error">{errors.faculty_id}</span>}
      </label>

      <label className="checkbox-row span-2">
        <input type="checkbox" checked={showAllFaculty} onChange={onToggleShowAllFaculty} />
        <span>Show faculty from all departments</span>
      </label>

      {selectedSubject && (
        <p className="modal-hint span-2 inline-hint">
          {showAllFaculty
            ? `Showing all ${visibleFaculty.length} active faculty. Cross-department assignment is allowed.`
            : `Showing ${visibleFaculty.length} faculty from ${selectedSubject.department_name}.`}
        </p>
      )}

      {crossDepartment && (
        <p className="cross-dept-note span-2">
          Cross-department assignment — {selectedFaculty.full_name} is in{' '}
          {selectedFaculty.department_name}, while this subject belongs to{' '}
          {selectedSubject.department_name}. This is allowed.
        </p>
      )}

      {lockPlacement && currentFacultyName && (
        <p className="modal-hint span-2 inline-hint">
          A subject is taught to a section by exactly one faculty member. Saving replaces{' '}
          <strong>{currentFacultyName}</strong>.
        </p>
      )}

      <label className="span-2">
        Notes
        <textarea
          rows="2"
          value={form.notes}
          onChange={(e) => onFieldChange('notes', e.target.value)}
          placeholder="Optional — e.g. shared lab slot with Section C."
        />
      </label>

      <label className="checkbox-row span-2">
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={(e) => onFieldChange('is_active', e.target.checked)}
        />
        <span>Active — deactivate to pause an assignment without losing the record.</span>
      </label>

      <div className="modal-actions span-2">
        <button type="button" className="secondary-btn" onClick={onCancel}>Cancel</button>
        <button type="submit" className="primary-btn" disabled={saving}>
          {saving ? 'Saving...' : editing ? 'Save Assignment' : 'Assign Subject'}
        </button>
      </div>
    </form>
  );
}
