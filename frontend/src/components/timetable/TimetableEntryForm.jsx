import { DAY_NAMES } from '../../services/timetableService';

/**
 * Place or move one class.
 *
 * `extraAssignment` covers the case where the entry being edited points at a
 * teaching assignment that has since been paused: the picker only loads
 * active ones, so without a synthetic option the <select> would match nothing,
 * the browser would show the first option instead, and saving would silently
 * reassign the cell to a different subject.
 */
export default function TimetableEntryForm({
  editing,
  form,
  errors,
  formError,
  assignments,
  extraAssignment,
  slots,
  days,
  section,
  saving,
  onFieldChange,
  onSubmit,
  onCancel,
}) {
  const teachingSlots = slots.filter((slot) => !slot.is_break);
  const options = extraAssignment ? [extraAssignment, ...assignments] : assignments;

  return (
    <form onSubmit={onSubmit} className="department-form form-grid">
      <div className="form-section span-2">What to place</div>

      <label className="span-2">
        Class
        <select
          value={form.teaching_assignment_id}
          onChange={(e) => onFieldChange('teaching_assignment_id', e.target.value)}
          disabled={!options.length}
        >
          <option value="">
            {options.length
              ? 'Select subject and faculty'
              : 'No active teaching assignments for this section'}
          </option>
          {options.map((item) => (
            <option key={item.id} value={item.id}>
              {item.subject_code} — {item.subject_name} · {item.faculty_name}
              {item.is_paused ? ' (paused)' : ''}
            </option>
          ))}
        </select>
        {errors.teaching_assignment_id && (
          <span className="field-error">{errors.teaching_assignment_id}</span>
        )}
      </label>

      {!options.length && (
        <p className="modal-hint span-2 inline-hint">
          Assign subjects to this section under Teaching Assignments first — the timetable only
          places assignments that already exist.
        </p>
      )}

      {extraAssignment && (
        <p className="cross-dept-note span-2">
          This class's teaching assignment is paused. Reactivate it under Teaching Assignments
          before saving, or the server will reject the change.
        </p>
      )}

      <div className="form-section span-2">When</div>

      <label>
        Day
        <select value={form.day_of_week} onChange={(e) => onFieldChange('day_of_week', e.target.value)}>
          <option value="">Select day</option>
          {days.map((day) => (
            <option key={day} value={day}>{DAY_NAMES[day]}</option>
          ))}
        </select>
        {errors.day_of_week && <span className="field-error">{errors.day_of_week}</span>}
      </label>

      <label>
        Period
        <select value={form.time_slot_id} onChange={(e) => onFieldChange('time_slot_id', e.target.value)}>
          <option value="">Select period</option>
          {teachingSlots.map((slot) => (
            <option key={slot.id} value={slot.id}>{slot.name} — {slot.label}</option>
          ))}
        </select>
        {errors.time_slot_id && <span className="field-error">{errors.time_slot_id}</span>}
      </label>

      <div className="form-section span-2">Where</div>

      <label className="span-2">
        Room
        <input
          type="text"
          value={form.room_number}
          onChange={(e) => onFieldChange('room_number', e.target.value)}
          placeholder={
            section?.room_number
              ? `${section.room_number} (the section's own room)`
              : 'Optional — the section has no room of its own'
          }
        />
      </label>

      <p className="modal-hint span-2 inline-hint">
        Leave the room blank to use the section's own room. Fill it in for a lab or any class that
        sits somewhere else.
      </p>

      <label className="checkbox-row span-2">
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={(e) => onFieldChange('is_active', e.target.checked)}
        />
        <span>Active — a paused class keeps its place on the grid.</span>
      </label>

      {formError && <div className="error-box span-2">{formError}</div>}

      <div className="modal-actions span-2">
        <button type="button" className="secondary-btn" onClick={onCancel}>Cancel</button>
        <button type="submit" className="primary-btn" disabled={saving}>
          {saving ? 'Saving...' : editing ? 'Save Class' : 'Place Class'}
        </button>
      </div>
    </form>
  );
}
