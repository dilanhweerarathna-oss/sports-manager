// One student row in the marking grid.
//
// Props: entry { student_id, full_name, admission_no, status, note }, disabled,
//        flashRef (object whose .id matches when the row should briefly flash),
//        onStatusChange(student_id, newStatus), onNoteClick(student_id).

import { useEffect, useRef } from 'react';
import StatusPill from './StatusPill.jsx';

export default function AttendanceRow({ entry, disabled, flashKey, onStatusChange, onNoteClick }) {
  const ref = useRef(null);

  // Briefly highlight the row when flashKey changes (used by scan).
  useEffect(() => {
    if (!flashKey || flashKey !== entry.student_id) return;
    const el = ref.current;
    if (!el) return;
    el.classList.add('flash');
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const t = setTimeout(() => el.classList.remove('flash'), 900);
    return () => clearTimeout(t);
  }, [flashKey, entry.student_id]);

  return (
    <div className="att-row" ref={ref}>
      <div className="att-info">
        <div className="att-name">{entry.full_name}</div>
        <div className="att-meta">{entry.admission_no || ''}</div>
        <button
          type="button"
          className={`note-btn ${entry.note ? 'has-note' : ''}`}
          onClick={() => onNoteClick(entry.student_id)}
        >
          ✎ {entry.note ? entry.note : 'add note'}
        </button>
      </div>
      <StatusPill
        status={entry.status === 'not_marked' ? null : entry.status}
        disabled={disabled}
        onChange={(newStatus) => onStatusChange(entry.student_id, newStatus)}
      />
    </div>
  );
}
