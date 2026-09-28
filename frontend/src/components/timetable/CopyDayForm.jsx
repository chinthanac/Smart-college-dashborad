import { DAY_NAMES } from '../../services/timetableService';

/**
 * Duplicate one day of this section's week onto another.
 *
 * The endpoint answers 201 even when it places nothing: each period that
 * would clash is reported in `skipped` with the reason. That is a warning,
 * not a failure, so the modal stays open to show the list.
 */
export default function CopyDayForm({
  form,
  days,
  saving,
  formError,
  result,
  onFieldChange,
  onSubmit,
  onCancel,
}) {
  return (
    <form onSubmit={onSubmit} className="department-form form-grid">
      <label>
        Copy from
        <select value={form.from_day} onChange={(e) => onFieldChange('from_day', e.target.value)}>
          {days.map((day) => (
            <option key={day} value={day}>{DAY_NAMES[day]}</option>
          ))}
        </select>
      </label>

      <label>
        Copy to
        <select value={form.to_day} onChange={(e) => onFieldChange('to_day', e.target.value)}>
          {days.map((day) => (
            <option key={day} value={day}>{DAY_NAMES[day]}</option>
          ))}
        </select>
      </label>

      <p className="modal-hint span-2 inline-hint">
        Periods that would double-book the faculty member, the section or the room are skipped and
        listed here — the rest are copied.
      </p>

      {formError && <div className="error-box span-2">{formError}</div>}

      {result && (
        <div className="span-2">
          <div className="success-box">
            Copied {result.created.length} class{result.created.length === 1 ? '' : 'es'}.
          </div>
          {result.skipped.length > 0 && (
            <>
              <p className="modal-hint inline-hint">
                {result.skipped.length} period{result.skipped.length === 1 ? '' : 's'} skipped:
              </p>
              <ul className="tt-skipped-list">
                {result.skipped.map((item) => (
                  <li key={item.time_slot_id}>
                    <strong>{item.slot_label || `Period ${item.time_slot_id}`}</strong> — {item.reason}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      <div className="modal-actions span-2">
        <button type="button" className="secondary-btn" onClick={onCancel}>Close</button>
        <button type="submit" className="primary-btn" disabled={saving}>
          {saving ? 'Copying...' : 'Copy Day'}
        </button>
      </div>
    </form>
  );
}
