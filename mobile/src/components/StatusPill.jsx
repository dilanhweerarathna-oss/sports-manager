// [Present] [Absent] segmented control. Re-clicking the active state unmarks
// (status -> null). Disabled while the session is closed.

export default function StatusPill({ status, disabled, onChange }) {
  function click(target) {
    if (disabled) return;
    onChange(status === target ? null : target);
  }
  return (
    <div className="pill">
      <button
        type="button"
        className={`pill-btn present ${status === 'present' ? 'active' : ''}`}
        disabled={disabled}
        onClick={() => click('present')}
      >
        Present
      </button>
      <button
        type="button"
        className={`pill-btn absent ${status === 'absent' ? 'active' : ''}`}
        disabled={disabled}
        onClick={() => click('absent')}
      >
        Absent
      </button>
    </div>
  );
}
