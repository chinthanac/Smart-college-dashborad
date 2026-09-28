export default function EntryDetails({ entry, onClose, onEdit }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h3>Scheduled Class</h3>

        <div className="profile-hero">
          <strong>{entry.subject_name}</strong>
          <span className="mono">{entry.subject_code}</span>
          <span className={`status-badge ${entry.is_active ? 'active' : 'inactive'}`}>
            {entry.is_active ? 'Active' : 'Paused'}
          </span>
        </div>

        <div className="profile-section-title">When</div>
        <div className="profile-grid">
          <div><span>Day</span><strong>{entry.day_name || '—'}</strong></div>
          <div><span>Period</span><strong>{entry.slot_name || '—'}</strong></div>
          {/* start_time and end_time arrive as "HH:MM" strings, not dates. */}
          <div><span>Starts</span><strong className="mono">{entry.start_time || '—'}</strong></div>
          <div><span>Ends</span><strong className="mono">{entry.end_time || '—'}</strong></div>
        </div>

        <div className="profile-section-title">Who</div>
        <div className="profile-grid">
          <div><span>Faculty</span><strong>{entry.faculty_name || '—'}</strong></div>
          <div><span>Faculty ID</span><strong className="mono">{entry.faculty_code || '—'}</strong></div>
          <div><span>Subject Type</span><strong>{entry.subject_type || '—'}</strong></div>
          <div><span>Credits</span><strong>{entry.subject_credits ?? '—'}</strong></div>
        </div>

        <div className="profile-section-title">Where</div>
        <div className="profile-grid">
          <div><span>Room</span><strong>{entry.room_number || '—'}</strong></div>
          <div><span>Section's Room</span><strong>{entry.section_room_number || '—'}</strong></div>
          {entry.is_relocated && (
            <div className="span-2">
              <span>Note</span>
              <strong>This class sits outside its section's own room.</strong>
            </div>
          )}
        </div>

        <div className="profile-section-title">Placement</div>
        <div className="profile-grid">
          <div><span>Section</span><strong>{entry.section_name} ({entry.section_code})</strong></div>
          <div><span>Semester</span><strong>{entry.semester_name || '—'}</strong></div>
          <div><span>Course</span><strong>{entry.course_name || '—'}</strong></div>
          <div><span>Department</span><strong>{entry.department_name || '—'}</strong></div>
          <div><span>Academic Year</span><strong>{entry.academic_year_name || '—'}</strong></div>
        </div>

        <div className="modal-actions">
          <button type="button" className="secondary-btn" onClick={onClose}>Close</button>
          <button type="button" className="primary-btn" onClick={() => onEdit(entry)}>Edit Class</button>
        </div>
      </div>
    </div>
  );
}
