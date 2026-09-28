const STATUS_LABEL = {
  UNSCHEDULED: 'Not placed',
  COMPLETE: 'Complete',
};

const statusLabel = (item) => {
  if (item.status === 'UNDER_SCHEDULED') {
    return `${item.remaining_periods} left`;
  }
  if (item.status === 'OVER_SCHEDULED') {
    return `Over by ${item.scheduled_periods - item.required_periods}`;
  }
  return STATUS_LABEL[item.status] || item.status;
};

/**
 * Required weekly periods versus what is actually on the grid.
 *
 * Clicking a subject arms "place mode": the next empty cell the admin clicks
 * opens the form with that class already chosen, which is the difference
 * between scheduling a week and re-picking the subject thirty times.
 */
export default function CoveragePanel({
  coverage,
  loading,
  placingAssignmentId,
  onPlace,
}) {
  // 0 required periods would make this 0/0 — NaN% silently breaks the style.
  const percent = coverage?.total_required
    ? Math.min(100, Math.round((coverage.total_scheduled / coverage.total_required) * 100))
    : 0;

  return (
    <aside className="panel coverage-panel">
      <div className="panel-header">
        <h3>Coverage</h3>
        {coverage && (
          <span className="panel-count">
            {coverage.total_scheduled}/{coverage.total_required} periods
          </span>
        )}
      </div>

      {loading && <p className="empty-note">Loading coverage...</p>}

      {!loading && !coverage && (
        <p className="empty-note">Coverage loads once you choose a section.</p>
      )}

      {!loading && coverage && (
        <>
          <div className="coverage-bar">
            <div className="coverage-bar-fill" style={{ width: `${percent}%` }} />
          </div>

          {coverage.subjects.length === 0 ? (
            <p className="empty-note">
              No active teaching assignments for this section yet, so there is nothing to schedule.
            </p>
          ) : (
            coverage.subjects.map((item) => (
              <button
                key={item.teaching_assignment_id}
                type="button"
                className={`coverage-row ${
                  String(placingAssignmentId) === String(item.teaching_assignment_id) ? 'is-placing' : ''
                }`}
                onClick={() => onPlace(item.teaching_assignment_id)}
                title="Click, then click an empty cell to place this class"
              >
                <span className="coverage-subject">
                  <span className="dept-name">{item.subject_code}</span>
                  <span className="dept-desc">{item.subject_name}</span>
                  <span className="dept-desc">{item.faculty_name}</span>
                </span>
                <span className="coverage-counts">
                  <strong>{item.scheduled_periods}/{item.required_periods}</strong>
                  <span className={`coverage-status ${item.status}`}>{statusLabel(item)}</span>
                </span>
              </button>
            ))
          )}
        </>
      )}
    </aside>
  );
}
