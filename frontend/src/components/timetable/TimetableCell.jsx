/**
 * One (day, period) cell.
 *
 * A cell holds 0 or 1 entry — the DB's UniqueConstraint on
 * (section_id, day_of_week, time_slot_id) guarantees it. A PAUSED entry is
 * still rendered in place: check_clashes deliberately ignores is_active, so
 * an inactive class keeps occupying its cell and hiding it would leave a
 * cell that looks free but always rejects.
 */
export default function TimetableCell({
  entry,
  day,
  slot,
  placingLabel,
  busy,
  onEmptyClick,
  onView,
  onEdit,
  onToggleStatus,
  onDelete,
}) {
  if (!entry) {
    return (
      <td className="tt-cell is-empty">
        <button
          type="button"
          className="tt-add"
          onClick={() => onEmptyClick(day, slot)}
          title={placingLabel ? `Place ${placingLabel} here` : `Add a class — ${slot.name}`}
        >
          +
        </button>
      </td>
    );
  }

  // subject_type is nullable on the wire, so guard before lowercasing it.
  const typeClass = entry.subject_type ? `type-${String(entry.subject_type).toLowerCase()}` : '';

  return (
    <td className={`tt-cell is-filled ${entry.is_active ? '' : 'is-inactive'}`}>
      <button type="button" className="link-btn dept-name tt-entry-subject" onClick={() => onView(entry)}>
        {entry.subject_code || 'Class'}
      </button>
      <div className="dept-desc">{entry.subject_name}</div>
      <div className="dept-desc">{entry.faculty_name}</div>

      {entry.subject_type && <span className={`type-chip ${typeClass}`}>{entry.subject_type}</span>}

      {entry.is_relocated && (
        <span className="tt-room-chip" title={`Section's own room is ${entry.section_room_number || '—'}`}>
          {entry.room_number}
        </span>
      )}

      {!entry.is_active && <span className="status-badge inactive">Paused</span>}

      <div className="action-buttons tt-entry-actions">
        <button type="button" className="table-btn edit-btn" onClick={() => onEdit(entry)} disabled={busy}>
          Edit
        </button>
        <button
          type="button"
          className={`table-btn ${entry.is_active ? 'warn-btn' : 'success-btn'}`}
          onClick={() => onToggleStatus(entry)}
          disabled={busy}
        >
          {entry.is_active ? 'Pause' : 'Resume'}
        </button>
        <button type="button" className="table-btn delete-btn" onClick={() => onDelete(entry)} disabled={busy}>
          Remove
        </button>
      </div>
    </td>
  );
}
