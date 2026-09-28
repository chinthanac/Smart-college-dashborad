import { useMemo } from 'react';
import {
  DAY_NAMES,
  SHORT_DAY_NAMES,
  WORKING_DAYS,
  todayIndex,
} from '../../services/timetableService';

/**
 * The signed-in user's own week, read-only.
 *
 * Shared by the faculty and student dashboards. Both fill it from
 * GET /api/timetable/me, which is role-aware on the server: faculty see every
 * class they teach (including cross-department ones the scoped list hides),
 * students see their section's grid.
 */
export default function MyTimetable({
  id,
  entries = [],
  slots = [],
  loading = false,
  days = WORKING_DAYS,
  title = 'My Weekly Timetable',
  emptyText = 'Nothing is scheduled yet.',
  showSection = false,
  showFaculty = false,
}) {
  // The clash rules make one class per (day, period) true for both roles, but
  // a duplicate is surfaced rather than silently dropped.
  const { cellMap, collisions } = useMemo(() => {
    const map = {};
    const clashes = [];
    entries.forEach((entry) => {
      const key = `${entry.day_of_week}:${entry.time_slot_id}`;
      if (map[key]) clashes.push(entry);
      else map[key] = entry;
    });
    return { cellMap: map, collisions: clashes };
  }, [entries]);

  const columnCount = slots.length + 1;

  return (
    <section className="panel" id={id}>
      <div className="panel-header">
        <h3>{title}</h3>
        {!loading && entries.length > 0 && (
          <span className="panel-count">
            {entries.length} class{entries.length === 1 ? '' : 'es'}
          </span>
        )}
      </div>

      {loading && <p className="empty-note">Loading your timetable...</p>}

      {!loading && entries.length === 0 && <p className="empty-note">{emptyText}</p>}

      {!loading && entries.length > 0 && (
        <>
          {collisions.length > 0 && (
            <div className="error-box">
              {collisions.length} class{collisions.length === 1 ? '' : 'es'} overlap another in the
              same period. Ask your admin to check the timetable.
            </div>
          )}

          {/* Days run down the rows and periods across the columns: a week is
              six rows tall whichever way round it is drawn, but this way the
              wide axis (up to eight periods) is the one that scrolls. */}
          <div className="department-table-wrap scroll-table">
            <table className="department-table timetable-table tt-by-day">
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
                {slots.length === 0 && (
                  <tr>
                    <td colSpan={columnCount} className="table-empty">
                      Period times are unavailable right now.
                    </td>
                  </tr>
                )}

                {slots.length > 0 &&
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
                        const entry = cellMap[`${day}:${slot.id}`];
                        if (!entry) {
                          return <td key={`${day}:${slot.id}`} className="tt-cell is-empty" />;
                        }
                        return (
                          <td
                            key={`${day}:${slot.id}`}
                            className={`tt-cell is-filled ${entry.is_active ? '' : 'is-inactive'}`}
                          >
                            <div className="dept-name">{entry.subject_code}</div>
                            <div className="dept-desc">{entry.subject_name}</div>
                            {showFaculty && <div className="dept-desc">{entry.faculty_name}</div>}
                            {showSection && <div className="dept-desc">{entry.section_name}</div>}
                            {entry.room_number && (
                              <div className="dept-desc mono">{entry.room_number}</div>
                            )}
                            {!entry.is_active && (
                              <span className="status-badge inactive">Paused</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

/**
 * Today's classes in order. start_time and end_time arrive as "HH:MM"
 * strings, so they are printed as-is — new Date("09:00") is Invalid Date.
 */
export function TodayClasses({ entries = [], loading = false }) {
  const today = todayIndex();

  const todays = useMemo(
    () =>
      entries
        .filter((entry) => entry.day_of_week === today && entry.is_active)
        .sort((a, b) => (a.period_number ?? 0) - (b.period_number ?? 0)),
    [entries, today],
  );

  if (loading) return <p className="empty-note">Loading today's classes...</p>;

  if (todays.length === 0) {
    return <p className="empty-note">No classes scheduled for {DAY_NAMES[today]}.</p>;
  }

  return (
    <div className="department-table-wrap scroll-table">
      <table className="department-table">
        <thead>
          <tr>
            <th>Period</th>
            <th>Subject</th>
            <th>Room</th>
          </tr>
        </thead>
        <tbody>
          {todays.map((entry) => (
            <tr key={entry.id}>
              <td>
                <div className="dept-name">{entry.slot_name}</div>
                <div className="dept-desc mono">{entry.start_time}–{entry.end_time}</div>
              </td>
              <td>
                <div className="dept-name">{entry.subject_name}</div>
                <div className="dept-desc mono">{entry.subject_code}</div>
              </td>
              <td>{entry.room_number || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
