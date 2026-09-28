import AssignmentAttendancePanel from './AssignmentAttendancePanel';

export default function TeachingAssignmentDetails({ assignment, onClose, onReassign }) {
  const stale = [
    assignment.subject_is_active === false && 'Subject is inactive',
    assignment.section_is_active === false && 'Section is inactive',
    assignment.faculty_is_active === false && 'Faculty member is inactive',
  ].filter(Boolean);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h3>Teaching Assignment</h3>

        <div className="profile-hero">
          <strong>{assignment.subject_name}</strong>
          <span className="mono">{assignment.subject_code}</span>
          <span className={`status-badge ${assignment.is_active ? 'active' : 'inactive'}`}>
            {assignment.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>

        {stale.length > 0 && (
          <div className="error-box">{stale.join(' · ')} — this assignment may need attention.</div>
        )}

        <div className="profile-section-title">Faculty</div>
        <div className="profile-grid">
          <div><span>Name</span><strong>{assignment.faculty_name}</strong></div>
          <div><span>Faculty ID</span><strong className="mono">{assignment.faculty_code}</strong></div>
          <div><span>Designation</span><strong>{assignment.faculty_designation || '—'}</strong></div>
          <div>
            <span>Department</span>
            <strong>
              {assignment.faculty_department_name} ({assignment.faculty_department_code})
              {assignment.is_cross_department && (
                <span className="type-chip type-cross-dept" style={{ marginLeft: '8px' }}>CROSS-DEPT</span>
              )}
            </strong>
          </div>
        </div>

        <div className="profile-section-title">Subject &amp; Section</div>
        <div className="profile-grid">
          <div><span>Subject Type</span><strong>{assignment.subject_type}</strong></div>
          <div><span>Credits</span><strong>{assignment.subject_credits}</strong></div>
          <div><span>Section</span><strong>{assignment.section_name} ({assignment.section_code})</strong></div>
          <div><span>Room</span><strong>{assignment.section_room_number || '—'}</strong></div>
          <div><span>Capacity</span><strong>{assignment.section_capacity ?? '—'}</strong></div>
        </div>

        <div className="profile-section-title">Academic Placement</div>
        <div className="profile-grid">
          <div><span>Department</span><strong>{assignment.department_name} ({assignment.department_code})</strong></div>
          <div><span>Course</span><strong>{assignment.course_name}</strong></div>
          <div><span>Semester</span><strong>{assignment.semester_name}</strong></div>
          <div><span>Academic Year</span><strong>{assignment.academic_year_name || '—'}</strong></div>
          {assignment.notes && (
            <div className="span-2"><span>Notes</span><strong>{assignment.notes}</strong></div>
          )}
        </div>

        <AssignmentAttendancePanel assignment={assignment} />

        <div className="modal-actions">
          <button type="button" className="secondary-btn" onClick={onClose}>Close</button>
          <button type="button" className="primary-btn" onClick={() => onReassign(assignment)}>
            Reassign Faculty
          </button>
        </div>
      </div>
    </div>
  );
}
