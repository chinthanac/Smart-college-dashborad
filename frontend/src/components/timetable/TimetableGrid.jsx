import { useMemo } from 'react';
import { DAY_NAMES, SHORT_DAY_NAMES } from '../../services/timetableService';
import TimetableCell from './TimetableCell';

/**
 * One section's week: days down, periods across.
 *
 * Break periods render as a thin inert column rather than clickable cells —
 * resolve_slot rejects a break slot with a 400, so offering a + there would
 * only produce an error.
 */
export default function TimetableGrid({
  slots,
  days,
  entries,
  loading,
  placingLabel,
  busyEntryId,
  onEmptyClick,
  onView,
  onEdit,
  onToggleStatus,
  onDelete,
}) {
  const cellMap = useMemo(() => {
    const map = {};
    entries.forEach((entry) => {
      map[`${entry.day_of_week}:${entry.time_slot_id}`] = entry;
    });
    return map;
  }, [entries]);

  const columnCount = slots.length + 1;

  return (
    <div className="department-table-wrap scroll-table">
      <table className="department-table timetable-table tt-by-day is-editable">
        <thead>
          <tr>
            <th className="tt-day-head-cell">Day</th>
            {slots.map((slot) => (
              <th
                key={slot.id}
                className={slot.is_break ? 'tt-slot-head is-break' : 'tt-slot-head'}
              >
                <span className="tt-slot-name">{slot.name}</span>
                <span className="tt-slot-time mono">{slot.label}</span>
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {loading && (
            <tr>
              <td colSpan={columnCount} className="table-loading">Loading the weekly grid...</td>
            </tr>
          )}

          {!loading && slots.length === 0 && (
            <tr>
              <td colSpan={columnCount} className="table-empty">
                No active periods are configured. Add time slots before scheduling.
              </td>
            </tr>
          )}

          {!loading &&
            slots.length > 0 &&
            days.map((day) => (
              <tr key={day}>
                <th className="tt-day-cell">
                  <span className="tt-day-full">{DAY_NAMES[day]}</span>
                  <span className="tt-day-short">{SHORT_DAY_NAMES[day]}</span>
                </th>
                {slots.map((slot) => {
                  if (slot.is_break) {
                    return <td key={`${day}:${slot.id}`} className="tt-cell is-break" />;
                  }
                  const entry = cellMap[`${day}:${slot.id}`] || null;
                  return (
                    <TimetableCell
                      key={`${day}:${slot.id}`}
                      entry={entry}
                      day={day}
                      slot={slot}
                      placingLabel={placingLabel}
                      busy={Boolean(entry) && busyEntryId === entry.id}
                      onEmptyClick={onEmptyClick}
                      onView={onView}
                      onEdit={onEdit}
                      onToggleStatus={onToggleStatus}
                      onDelete={onDelete}
                    />
                  );
                })}
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
