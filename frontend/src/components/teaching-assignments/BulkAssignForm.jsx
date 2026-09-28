/**
 * One faculty member, one subject, several sections at once.
 * Sections that already have this subject are shown disabled and annotated,
 * so the server's `skipped` list is normally empty.
 */
export default function BulkAssignForm({
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
  existingBySection,
  saving,
  onLevelChange,
  onFieldChange,
  onToggleSection,
  onSubmit,
  onCancel,
}) {
  const level = (name) => (e) => onLevelChange(name, e.target.value);
  const selectable = sections.filter((s) => !existingBySection[s.id]);
  const allSelected = selectable.length > 0 && selectable.every((s) => form.section_ids.includes(s.id));

  return (
    <form onSubmit={onSubmit} className="department-form form-grid">
      <div className="form-section span-2">Academic Placement</div>

      <label>
        Department
        <select value={form.department_id} onChange={level('department_id')}>
          <option value="">All departments</option>
          {departments.map((item) => (
            <option key={item.id} value={item.id}>{item.name} ({item.code})</option>
          ))}
        </select>
      </label>

      <label>
        Course
        <select value={form.course_id} onChange={level('course_id')} disabled={!courses.length}>
          <option value="">{courses.length ? 'Select course' : 'No courses available'}</option>
          {courses.map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
        {errors.course_id && <span className="field-error">{errors.course_id}</span>}
      </label>

      <label>
        Semester
        <select value={form.semester_id} onChange={level('semester_id')} disabled={!form.course_id}>
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
        <select value={form.subject_id} onChange={level('subject_id')} disabled={!form.semester_id}>
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

      <div className="form-section span-2">Sections</div>

      {!form.subject_id ? (
        <p className="empty-note span-2">Choose a subject to list the sections in its semester.</p>
      ) : sections.length === 0 ? (
        <p className="empty-note span-2">This semester has no sections yet.</p>
      ) : (
        <>
          <label className="checkbox-row span-2">
            <input
              type="checkbox"
              checked={allSelected}
              disabled={!selectable.length}
              onChange={() =>
                onFieldChange('section_ids', allSelected ? [] : selectable.map((s) => s.id))
              }
            />
            <span>Select all available sections</span>
          </label>

          <div className="section-picker span-2">
            {sections.map((item) => {
              const taken = existingBySection[item.id];
              return (
                <label key={item.id} className={`section-option ${taken ? 'is-taken' : ''}`}>
                  <input
                    type="checkbox"
                    checked={form.section_ids.includes(item.id)}
                    disabled={Boolean(taken)}
                    onChange={() => onToggleSection(item.id)}
                  />
                  <span>
                    <strong>{item.name}</strong>
                    <span className="dept-desc">
                      {taken ? `already taught by ${taken.faculty_name}` : item.room_number}
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
          {errors.section_ids && <span className="field-error span-2">{errors.section_ids}</span>}
        </>
      )}

      <label className="span-2">
        Notes
        <textarea
          rows="2"
          value={form.notes}
          onChange={(e) => onFieldChange('notes', e.target.value)}
          placeholder="Optional — applied to every assignment created."
        />
      </label>

      <div className="modal-actions span-2">
        <button type="button" className="secondary-btn" onClick={onCancel}>Cancel</button>
        <button type="submit" className="primary-btn" disabled={saving}>
          {saving
            ? 'Assigning...'
            : `Assign to ${form.section_ids.length} section${form.section_ids.length === 1 ? '' : 's'}`}
        </button>
      </div>
    </form>
  );
}
