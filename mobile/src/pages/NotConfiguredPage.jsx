export default function NotConfiguredPage() {
  return (
    <div className="phone-screen centered">
      <div className="card">
        <div className="big-emoji">⚽</div>
        <h1>Sports Manager</h1>
        <p className="muted">Coach Mobile Attendance</p>
        <hr />
        <h3>Not set up yet</h3>
        <p>
          To use this app, your school's admin needs to share a
          <strong> setup QR code</strong> with you.
        </p>
        <ol>
          <li>Open your phone camera (or any QR scanner).</li>
          <li>Scan the QR your admin sent.</li>
          <li>The link opens this app, ready to sign in.</li>
        </ol>
        <p className="muted small">
          Don't have a QR yet? Ask your sports director or principal.
        </p>
      </div>
    </div>
  );
}
