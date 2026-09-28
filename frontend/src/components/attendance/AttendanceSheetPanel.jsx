import { formatDateValue } from '../../services/attendanceService';
import AttendanceSheetTable from './AttendanceSheetTable';

/**
 * One register: the roster, a live tally, and the cancel switch.
 *
 * The tally is computed from what is on screen rather than from the saved
 * session, so the percentage moves as the lecturer marks.
 */
export default function AttendanceSheetPanel({
  sheet,
  records,
  cancelled,
  cancelReason,
  notes,
  saving,
  error,
  notice,
  onChange,
  onMarkAll,
  onToggleCancelled,
  onCancelReasonChange,
  onNotesChange,
  onSave,
  onDismissError,
}) {
  // A sheet that would not open (wrong weekday, a paused class, a date
  // outside the semester) still has to say why — the reason is the only
  // thing that tells the lecturer what to change.
  if (!sheet) {
    return (
      <section className="panel">
        <div className="panel-header">
          <h3>Register</h3>
        </div>
        {error ? (
          <div className="error-box dismissable" onClick={onDismissError} role="alert">
            {error}
          </div>
        ) : (
          <p className="empty-note">Pick a class to open its register.</p>
        )}
      </section>
    );
  }

  const present = records.filter((r) => r.status === 'PRESENT' || r.status === 'LATE').length;
  const absent = records.filter((r) => r.status === 'ABSENT').length;
  const excused = records.filter((r) => r.status === 'EXCUSED').length;
  const countable = records.length - excused;
  const percent = countable ? Math.round((present / countable) * 1000) / 10 : 0;

  const locked = !sheet.editable;

  return (
    <section className="panel">
      <div className="panel-header">
        <h3>
          {sheet.subject_code} · {sheet.section_name}
        </h3>
        <span className="panel-count">
          {sheet.day_name} {formatDateValue(sheet.class_date)}
          {sheet.slot_name ? ` · ${sheet.slot_name}` : ''}
        </span>
      </div>

      <p className="modal-hint inline-hint">
        {sheet.subject_name}
        {sheet.faculty_name ? ` · ${sheet.faculty_name}` : ''}
        {sheet.room_number ? ` · ${sheet.room_number}` : ''}
      </p>

      {sheet.sheet_state === 'MARKED' && sheet.session && (
        <div className="info-box">
          Marked by {sheet.session.marked_by_name}. Saving again corrects this register.
        </div>
      )}

      {error && (
        <div className="error-box dismissable" onClick={onDismissError} role="alert">
          {error}
        </div>
      )}
      {notice && <div className="success-box" role="status">{notice}</div>}

      {!cancelled && (
        <section className="mini-stats">
          <div className="mini-stat">
            <span className="mini-stat-label">Present</span>
            <strong className="mini-stat-value tone-green">{present}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Absent</span>
            <strong className="mini-stat-value tone-red">{absent}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Excused</span>
            <strong className="mini-stat-value tone-gray">{excused}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Attendance</span>
            <strong className="mini-stat-value tone-blue">{percent}%</strong>
          </div>
        </section>
      )}

      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={cancelled}
          onChange={(e) => onToggleCancelled(e.target.checked)}
          disabled={saving}
        />
        <span>This class was cancelled — it counts toward nobody's attendance.</span>
      </label>

      {cancelled ? (
        <label className="attendance-reason">
          Why was it cancelled?
          <textarea
            rows="2"
            value={cancelReason}
            onChange={(e) => onCancelReasonChange(e.target.value)}
            placeholder="e.g. Faculty on college duty"
            disabled={saving}
          />
        </label>
      ) : (
        <AttendanceSheetTable
          records={records}
          disabled={saving || locked}
          onChange={onChange}
          onMarkAll={onMarkAll}
        />
      )}

      {locked && sheet.locked_reason && !cancelled && (
        <p className="empty-note">{sheet.locked_reason}</p>
      )}

      <label className="attendance-reason">
        Notes (optional)
        <textarea
          rows="2"
          value={notes}
          onChange={(e) => onNotesChange(e.target.value)}
          placeholder="Anything worth remembering about this class."
          disabled={saving}
        />
      </label>

      <div className="modal-actions">
        <button
          type="button"
          className="primary-btn"
          onClick={onSave}
          disabled={saving || (locked && !cancelled)}
        >
          {saving ? 'Saving...' : sheet.sheet_state === 'DRAFT' ? 'Save Register' : 'Save Changes'}
        </button>
      </div>
    </section>
  );
}
