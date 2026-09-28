/**
 * Create/Edit form. The Semester dropdown stays disabled until a Course is
 * chosen and is repopulated from GET /api/semesters?course_id= each time
 * the Course changes, so an invalid pair cannot be submitted.
 */
export default function SubjectForm({
  editing,
  form,
  errors,
  courses,
  semesters,
  subjectTypes,
  saving,
  onFieldChange,
  onCourseChange,
  onSubmit,
  onCancel,
}) {
  const field = (name) => (e) => onFieldChange(name, e.target.value);
  const totalHours =
    (Number(form.lecture_hours) || 0) + (Number(form.tutorial_hours) || 0) + (Number(form.practical_hours) || 0);

  return (
    <form onSubmit={onSubmit} className="department-form form-grid">
      <div className="form-section span-2">Academic Placement</div>

      <label>
        Course
        <select value={form.course_id} onChange={(e) => onCourseChange(e.target.value)} disabled={!courses.length}>
          <option value="">{courses.length ? 'Select course' : 'No courses available'}</option>
          {courses.map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
        {errors.course_id && <span className="field-error">{errors.course_id}</span>}
      </label>

      <label>
        Semester
        <select value={form.semester_id} onChange={field('semester_id')} disabled={!form.course_id}>
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

      <div className="form-section span-2">Subject Details</div>

      <label>
        Subject Code
        <input type="text" value={form.subject_code} onChange={field('subject_code')} placeholder="CS501" />
        {errors.subject_code && <span className="field-error">{errors.subject_code}</span>}
      </label>

      <label>
        Subject Name
        <input type="text" value={form.name} onChange={field('name')} placeholder="Database Management Systems" />
        {errors.name && <span className="field-error">{errors.name}</span>}
      </label>

      <label>
        Subject Type
        <select value={form.subject_type} onChange={field('subject_type')}>
          {subjectTypes.map((item) => (
            <option key={item} value={item}>{item}</option>
          ))}
        </select>
        {errors.subject_type && <span className="field-error">{errors.subject_type}</span>}
      </label>

      <label>
        Credits
        <input type="number" min="1" value={form.credits} onChange={field('credits')} placeholder="4" />
        {errors.credits && <span className="field-error">{errors.credits}</span>}
      </label>

      <div className="form-section span-2">Weekly Hours</div>

      <label>
        Lecture Hours
        <input type="number" min="0" value={form.lecture_hours} onChange={field('lecture_hours')} />
      </label>

      <label>
        Tutorial Hours
        <input type="number" min="0" value={form.tutorial_hours} onChange={field('tutorial_hours')} />
      </label>

      <label>
        Practical Hours
        <input type="number" min="0" value={form.practical_hours} onChange={field('practical_hours')} />
        {errors.hours && <span className="field-error">{errors.hours}</span>}
      </label>

      <div className="hours-summary">
        <span>Total</span>
        <strong>{totalHours} hrs / week</strong>
      </div>

      <label className="span-2">
        Description
        <textarea
          rows="3"
          value={form.description}
          onChange={field('description')}
          placeholder="Relational modelling, SQL, transactions, indexing."
        />
      </label>

      <label className="checkbox-row span-2">
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={(e) => onFieldChange('is_active', e.target.checked)}
        />
        <span>Active — inactive subjects stay in the curriculum but are not offered.</span>
      </label>

      <div className="modal-actions span-2">
        <button type="button" className="secondary-btn" onClick={onCancel}>Cancel</button>
        <button type="submit" className="primary-btn" disabled={saving}>
          {saving ? 'Saving...' : editing ? 'Update Subject' : 'Create Subject'}
        </button>
      </div>
    </form>
  );
}
