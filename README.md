# Sports Manager

> Desktop attendance, billing, and reports for school sports programs — with optional cloud sync and a mobile coach PWA.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

Sports Manager is an offline-first Windows desktop app that helps schools run their sports programs: tracking students, coaches, sports, attendance, and payments, and generating PDF receipts and reports. Add an optional Supabase backend and the included React PWA, and coaches can mark attendance from their phones while the desktop stays in sync.

---

## Features

- **Student, coach, and sport management** — clean PySide6 UI with search, filters, and bulk actions
- **Attendance** — desktop entry, plus optional mobile PWA with QR-code based school setup
- **Payments & receipts** — track fees, generate numbered PDF receipts (ReportLab)
- **Reports** — printable PDF reports per student, coach, or sport
- **Auto-backups** — daily local SQLite backups
- **Secure auth** — bcrypt password hashing, first-run admin wizard
- **Optional cloud sync** — one Supabase project per school, pushes students/sports/enrollments/attendance
- **Offline-first** — every feature works without internet; cloud sync is purely additive

---

## Tech stack

**Desktop**
- Python 3.11+
- PySide6 + PySide6-Fluent-Widgets (Qt UI)
- SQLite (local database)
- ReportLab (PDF generation)
- bcrypt (password hashing)
- supabase-py (optional cloud sync)
- qrcode (school setup QR generation)

**Mobile PWA**
- React 18 + React Router
- Vite 5
- @supabase/supabase-js
- jsQR (QR scanning)

---

## Project structure

```
.
├── main.py                  # App entry point
├── config.py                # Loads .env, defines paths & cloud settings
├── requirements.txt         # Python dependencies
├── build.bat                # Builds .exe (PyInstaller) + installer (Inno Setup)
├── installer.iss            # Inno Setup installer config
├── SportsManager.spec       # PyInstaller spec
├── database/                # SQLite schema + migrations
├── models/                  # Domain models (student, coach, sport, …)
├── repositories/            # Data-access layer
├── services/                # Business logic (auth, payments, cloud sync, …)
├── ui/                      # PySide6 dialogs and windows
├── utils/                   # Logging, theming, helpers
├── cloud/                   # Supabase schema (one project per school)
├── mobile/                  # React PWA (coach attendance)
└── README_BUILD.md          # Detailed build & installer instructions
```

---

## Quick start — Desktop

**Prerequisites:** Python 3.11+, Windows.

```bash
# 1. Clone
git clone https://github.com/<your-username>/sports-manager.git
cd sports-manager

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure (optional — only needed if you want cloud sync)
copy .env.example .env
# then open .env and fill in SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_KEY

# 5. Run
python main.py
```

On first run, the app creates `sports_manager.db`, runs migrations, and walks you through creating an admin user.

---

## Quick start — Mobile PWA

The mobile PWA lets coaches mark attendance from a phone. It talks to Supabase, so it requires the cloud setup (see [CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md)).

```bash
cd mobile
npm install
npm run dev          # local dev at http://localhost:5173
npm run build        # production build → mobile/dist/
```

Deploy `mobile/dist/` to Vercel (or any static host) and put the resulting URL in your `.env` as `PWA_BASE_URL`. The desktop app then generates a setup QR code coaches scan to enroll their phone with your school.

See [mobile/README.md](mobile/README.md) for details.

---

## Building a Windows installer

A one-click installer for non-technical users:

```bash
build.bat
```

This runs PyInstaller to produce `dist\SportsManager.exe`, then runs Inno Setup against `installer.iss` to bundle it into a Windows installer. See [README_BUILD.md](README_BUILD.md) for prerequisites and troubleshooting.

---

## Cloud deployment

End-to-end Supabase + Vercel setup, per school:

→ [CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md)

The desktop app works **fully offline** if you skip this. Cloud sync is opt-in.

---

## Configuration

All configuration lives in `.env`. Copy `.env.example` to `.env` and edit as needed. Every key is optional — defaults are baked in.

| Key | Purpose | Default |
|---|---|---|
| `DB_PATH` | SQLite filename | `sports_manager.db` |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` | `INFO` |
| `LOG_DIR` | Log folder | `logs` |
| `REPORTS_DIR` | Generated PDF folder | `reports` |
| `BACKUP_DIR` | Auto-backup folder | `backups` |
| `APP_NAME` | Shown in title bar | `School Sports Manager` |
| `DEFAULT_SCHOOL_NAME` | Pre-filled school name on first run | `My School` |
| `RECEIPT_PREFIX` | Prefix for receipt numbers | `REC` |
| `SUPABASE_URL` | Your Supabase project URL | _empty (cloud off)_ |
| `SUPABASE_ANON_KEY` | Supabase anon key | _empty_ |
| `SUPABASE_SERVICE_KEY` | Supabase service-role key (desktop only — never in mobile) | _empty_ |
| `PWA_BASE_URL` | Where your mobile PWA is hosted | _placeholder_ |

When running as a packaged `.exe`, the app stores the DB, logs, reports, and backups under `%LOCALAPPDATA%\SportsManager` so Program Files can stay read-only.

---

## Security notes

- Passwords are hashed with bcrypt
- The Supabase **service key** bypasses RLS and must stay on the desktop — never bundle it in the mobile build
- The mobile PWA only ever uses the **anon key**; row-level security in Supabase is the enforcement layer
- The local SQLite DB is plain — protect it with OS-level filesystem permissions

---

## Contributing

PRs welcome. For larger changes, open an issue first so we can discuss the approach.

---

## License

MIT — see [LICENSE](LICENSE).
