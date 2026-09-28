import { toDateValue } from '../../services/attendanceService';

const STATUS_BADGE = {
  MARKED: 'active',
  CANCELLED: 'inactive',
  PAUSED: 'inactive',
  UNMARKED: '',
};

const STATUS_LABEL = {
  MARKED: 'Marked',
  CANCELLED: 'Cancelled',
  PAUSED: 'Paused',
  UNMARKED: 'Not marked',
};

/**
 * A lecturer's day. The date drives everything: the API only returns classes
 * that actually meet on that weekday, so an empty list means "nothing to
 * teach", not "nothing loaded".
 */
export default function AttendanceClassPicker({
  classDate,
  classes,
  loading,
  selectedEntryId,
  onDateChange,
  onSelect,
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h3>My Classes</h3>
        {!loading && <span className="panel-count">{classes.length}</span>}
      </div>

      <label className="attendance-date">
        Date
        <input
          type="date"
          value={classDate}
          max={toDateValue()}
          onChange={(e) => onDateChange(e.target.value)}
        />
      </label>

      {loading && <p className="empty-note">Loading your classes...</p>}

      {!loading && classes.length === 0 && (
        <p className="empty-note">
          You have no classes scheduled on this day. Pick another date.
        </p>
      )}

      {!loading &&
        classes.map((item) => (
          <button
            key={item.timetable_entry_id}
            type="button"
            className={`coverage-row ${
              selectedEntryId === item.timetable_entry_id ? 'is-placing' : ''
            }`}
            onClick={() => onSelect(item)}
          >
            <span className="coverage-subject">
              <span className="dept-name">
                {item.slot_name} · {item.subject_code}
              </span>
              <span className="dept-desc">{item.subject_name}</span>
              <span className="dept-desc">
                {item.section_name}
                {item.room_number ? ` · ${item.room_number}` : ''}
              </span>
            </span>
            <span className="coverage-counts">
              {item.status === 'MARKED' && (
                <strong>
                  {item.present_count}/{item.total_students}
                </strong>
              )}
              <span className={`status-badge ${STATUS_BADGE[item.status]}`}>
                {STATUS_LABEL[item.status]}
              </span>
            </span>
          </button>
        ))}
    </section>
  );
}
