# Cloud Deployment + Verification Guide

End-to-end setup for **one school** going from "desktop-only" to "coaches mark
attendance from their phones". Once done, you copy the `.exe` to as many
schools as you like — each one runs this guide once for their own Supabase
project + their own Vercel PWA.

Estimated time, start to finish: **30–45 minutes**.

---

## Prerequisites

- Sports Manager desktop installed and working (existing setup unchanged).
- A **Google account** (or GitHub) to sign into Supabase + Vercel.
- A computer with **Node.js 18+** for building the mobile PWA. ([Download](https://nodejs.org))
- About 30 minutes.

---

## Part 1 — Create the Supabase project (~5 min)

1. Go to [supabase.com/dashboard](https://supabase.com/dashboard) → sign in (Google or GitHub works fine for free).
2. Click **New project**.
3. Name it your school (e.g. `royal-college-sports`). Pick a strong DB password — **save it**, but you won't need it day-to-day.
4. Pick a region close to you (Singapore/Mumbai are fastest from Sri Lanka).
5. Wait ~1 minute for provisioning.

### Apply the schema

6. Left sidebar → **SQL Editor** → **New query**.
7. Open [cloud/supabase_schema.sql](cloud/supabase_schema.sql) from this repo in a text editor and copy the entire contents.
8. Paste into the SQL Editor → **Run**. Should take < 1 second and show "Success. No rows returned."
9. Verify by running:
   ```sql
   SELECT table_name FROM information_schema.tables
     WHERE table_schema='public' ORDER BY table_name;
   ```
   You should see ~9 tables (`student_ref`, `sport_ref`, `coach_ref`, `mic_ref`,
   `enrollment_ref`, `sport_coach_ref`, `sport_mic_ref`, `attendance_sessions`,
   `attendance_records`).

### Collect your keys

10. Left sidebar → **Project Settings** → **API**.
11. Copy three values (keep this tab open — you'll paste these in Part 2):
    - **Project URL** (e.g. `https://abcd1234.supabase.co`)
    - **anon** key (public — long string starting with `eyJ`)
    - **service_role** key (SECRET — click "Reveal", copy carefully)

### Create the first admin user

12. Left sidebar → **Authentication** → **Users** → **Add user → Create new user**.
13. Email = your admin email. Pick a strong password. Click **Create user**.
14. Click the new user → scroll to **App Metadata** → click **Edit**.
15. Paste this and save:
    ```json
    {
      "role": "admin"
    }
    ```
    This admin can see every sport. (Coach + MIC accounts get created later
    from the desktop app, not here.)

---

## Part 2 — Wire up the desktop (~3 min)

1. Open Sports Manager → **Settings** → **Cloud** tab → click **🌐 Set up cloud**.
2. Paste the three values from Supabase. Click **Test connection**.
   - "✓ Connection OK" → you're good.
   - "Cloud schema is missing" → re-do step 7–8 of Part 1.
   - "Service key was rejected" → you copied the anon key. Click "Reveal" on the service_role key in Supabase API settings.
3. Click **Save & finish** → restart Sports Manager.
4. After restart, look at the top-right of the title bar:
   - **⟳ Syncing** for a few seconds, then
   - **✓ Synced** → desktop is mirroring data to the cloud.
5. Optional: in Supabase Studio → **Table Editor** → click `student_ref`. You should see your students (just `student_id`, `full_name`, `admission_no`, `is_active` — no PII).

---

## Part 3 — Deploy the mobile PWA (~10 min)

You need to do this **once per school** so the PWA points at the school's own Supabase project. After that, every coach scans the same QR.

### Build it

```bash
cd mobile
npm install      # downloads ~150MB of dev deps; one-time
npm run build
```

Output: a `dist/` folder of static files. That's the whole PWA.

### Deploy to Vercel

**Easiest path — drag-and-drop:**

1. Go to [vercel.com](https://vercel.com) → sign in.
2. **Add New → Project → Browse all templates → Static Site**, *or* on the dashboard click **Add New → Project**.
3. If asked to import from Git, click **Skip → Deploy without Git**.
4. Drag the `dist` folder into the upload area. Click **Deploy**.
5. After ~30 seconds you'll get a URL like `https://your-school-pwa.vercel.app`. Copy it.

**Or via CLI (one-line redeploys later):**

```bash
npm install -g vercel
cd mobile
vercel              # interactive — accept defaults
vercel --prod       # redeploy to production
```

### Tell the desktop where the PWA lives

6. Open `%LOCALAPPDATA%\SportsManager\.env` in Notepad.
7. Add at the bottom:
   ```
   PWA_BASE_URL=https://your-school-pwa.vercel.app
   ```
8. Restart Sports Manager. Generated setup QRs will now point at the right URL.

---

## Part 4 — Create coach logins (~2 min per coach)

For each coach who needs mobile access:

1. Sports Manager → **Coaches** page → select the coach.
2. Make sure they have an **email** on file (edit if not).
3. Click **📱 Mobile Access** → **Create login**.
4. A dialog shows the temp password — click **Copy password**.
5. Share with the coach in person, via WhatsApp, or via a sealed envelope.

Same flow for MICs from the **MICs** page (with `role: 'mic'` automatically set).

---

## Part 5 — Generate the setup QR (~1 min)

Once. Reusable for every coach.

1. Sports Manager → **Settings → Cloud → 📱 Generate Mobile Setup QR**.
2. A QR appears. Click **💾 Save QR as PNG** → print it, or **📋 Copy URL** to paste into your school's WhatsApp group.
3. Coaches scan with their phone camera (or open the link). The PWA opens, binds to your Supabase, and shows the sign-in screen.

---

## Part 6 — End-to-end verification (~10 min)

Run this checklist once after Part 5 to confirm everything works. Use a real coach account and a phone.

### A. Sign in and roster scoping

- [ ] On the phone, open the setup QR's URL. PWA loads.
- [ ] Sign in with coach email + temp password. → Land on **Your sports**.
- [ ] You see **only the sports this coach is assigned to** (not every school sport).
- [ ] Tap a sport → see the **sessions list** (empty if no sessions yet).

### B. Create + mark a session

- [ ] Tap **+** → fill in date/time → **Create**.
- [ ] You land on the marking screen. Every student is **gray "Not marked"**.
- [ ] Tap **Present** next to one student. The pill turns green; "✓ saved just now" appears.
- [ ] Tap **Present** again on the same student → reverts to gray.
- [ ] Type a student's admission number in the search box → press Enter → row flashes green, marked Present.
- [ ] Tap 📷 → grant camera permission → point at any QR (or skip with ✕). If you scan a card whose admission number matches a student, that student gets marked Present.
- [ ] Tap **Mark rest Absent** → confirm → all unmarked students become Absent.
- [ ] Tap **Close** → confirm → badge flips to 🔒 CLOSED, pills disable.
- [ ] Tap **Reopen** → editable again.

### C. Round-trip with desktop

- [ ] On the desktop, open the **Attendance** page → pick the same sport → same session.
- [ ] The status the coach marked on mobile is **visible on desktop** (within 30s).
- [ ] On the desktop, change a student's status → wait 30s → **refresh the mobile** → the change appears.

### D. Two coaches at once (if you have two phones / browsers handy)

- [ ] Sign in on two devices with **the same coach** (or two coaches who share a sport).
- [ ] One marks Alice Present → the other device shows it within 1–2 seconds (this is Supabase Realtime).

### E. Privacy contract — verify what's in the cloud

In Supabase Studio → Table Editor:

- [ ] `student_ref` has only `student_id, full_name, admission_no, is_active`. **No** gender / DOB / parent / contact / address / notes / fees.
- [ ] `coach_ref` has only `coach_id, full_name, email, is_active`. **No** contact_no / address.
- [ ] No `payments`, `receipts`, `settings`, `users`, `activity_log`, `student_sports.joined_date` etc. — they don't exist in the cloud at all.

### F. Authorization (RLS)

- [ ] Sign in as coach A. In the browser console: `fetch('/rest/v1/attendance_sessions?sport_id=eq.<a_sport_NOT_assigned_to_them>', { headers: ... })`. Returns `[]` even though sessions exist — RLS denies them.
- [ ] In the desktop, click **Mobile Access → Disable** on a coach. Within minutes that coach can't sign in.

### G. Offline tolerance

- [ ] Disconnect the desktop's internet. App keeps working — top-bar shows **⚠ Offline**. Mark some attendance locally.
- [ ] Reconnect. Within 30s the top-bar goes **✓ Synced** and the new marks appear on mobile.
- [ ] Disconnect the phone's data. The PWA shows an error toast when you try to mark — but pre-existing data remains visible.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Desktop status shows **✗ Sync error** with "schema" message | SQL script not run (or partially) | Re-run the schema SQL in Supabase SQL Editor |
| Status shows **✗ Sync error** with "401" / "Invalid API key" | Wrong service_role key in .env | Re-run Cloud Setup wizard with the correct key (rotate in Supabase Studio if you're unsure) |
| Coach can sign in but sees no sports | Coach not assigned to any sports yet | Assign them via the Sports page in desktop. Wait 30s. Refresh the PWA. |
| PWA shows "Not set up yet" after scanning QR | Localstorage was cleared, or wrong URL | Re-scan the QR |
| Camera button does nothing on iPhone | Camera permission denied | Settings → Safari → Camera → Allow |
| Mobile pull-to-refresh doesn't update | Service worker cached old data | Close the tab + reopen, or hard refresh |

---

## Distributing to a new school

The .exe + this guide is all another school needs.

1. Copy the Sports Manager folder (`.exe` + assets) to their PC.
2. Hand them this `CLOUD_DEPLOYMENT.md`.
3. They run Parts 1–5 themselves (their own Supabase project, their own Vercel deploy).
4. Their data is fully isolated from yours.

Each school = one free Supabase project (500 MB DB, 50k Edge Function calls/mo)
+ one free Vercel deploy. **Zero ongoing cost.**

---

## What's NOT in v1

- **Offline writes on mobile.** If a coach loses internet mid-session, marks fail with a toast. Pull-to-refresh + offline write queue planned for v2.
- **Forced password change on first login.** Temp passwords are shared once; the coach should change it themselves via mobile (planned: a "Change password" screen).
- **Push notifications.** Sessions don't notify coaches when opened.
- **Self-service coach sign-up.** Admin creates every account from the desktop.
- **Camera scanning fallback for old phones.** Some Android phones < 8.0 may not support the `BarcodeDetector` API; we fall back to `jsQR`, which works but slower.

All of the above are clean additions on top of the v1 architecture, not rewrites.
