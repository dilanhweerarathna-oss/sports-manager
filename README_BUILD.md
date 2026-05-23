# Building & Shipping Sports Manager

How to produce a Windows installer (`SportsManagerSetup.exe`) you can hand
to a new school and run on a fresh PC.

---

## One-time setup on your dev machine

1. **Python 3.11+** (any 64-bit Windows build is fine).
2. **Inno Setup 6** — download from <https://jrsoftware.org/isdl.php> and
   install with defaults. Adds `ISCC.exe` to `C:\Program Files (x86)\Inno Setup 6\`.
3. Optional: drop an `assets\icon.ico` into the project to give the exe a
   proper icon. Skip and the default Python rocket icon is used.

That's it — no virtualenv needed; `build.bat` installs PyInstaller for you.

---

## Build the app (every release)

From the project root:

```cmd
build.bat
```

This:
- installs / upgrades PyInstaller and the runtime deps from `requirements.txt`
- wipes any prior `build\` and `dist\` folders
- runs PyInstaller against `SportsManager.spec`
- leaves you with `dist\SportsManager\SportsManager.exe`

Double-click that exe to smoke-test the bundle locally before packaging the
installer.

---

## Build the installer

```cmd
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

Output: `installer\SportsManagerSetup.exe` — a single ~80 MB file you can
copy to a USB stick, email, or upload anywhere.

---

## Installing on a new school PC

1. Copy `SportsManagerSetup.exe` to the target machine.
2. Right-click → **Run as administrator** (the installer writes to
   `Program Files`).
3. Click through the wizard. Defaults are fine.
4. A Start-Menu shortcut "Sports Manager" is created; tick the Desktop
   shortcut box during install if you want one.
5. First launch creates the database automatically.

### Where the data lives

| Item        | Location |
|-------------|----------|
| Program files | `C:\Program Files\SportsManager\` |
| Database    | `%LOCALAPPDATA%\SportsManager\sports_manager.db` |
| Logs        | `%LOCALAPPDATA%\SportsManager\logs\` |
| Receipts    | `%LOCALAPPDATA%\SportsManager\reports\` |
| Backups     | `%LOCALAPPDATA%\SportsManager\backups\` |

The user data lives in `%LOCALAPPDATA%` so it survives uninstalls /
upgrades. To fully wipe a school, delete that folder after uninstalling.

---

## Updating a school to a new version

Build the new `SportsManagerSetup.exe`, run it on the school's PC — it
upgrades the install in place and **does not touch the database**.

---

## Common issues

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: reportlab.X` after build | Add the missing submodule to `hiddenimports` in `SportsManager.spec` |
| App opens then closes instantly on the school PC | Run from `cmd` to see the error, or temporarily set `console=True` in the spec and rebuild |
| "Windows protected your PC" SmartScreen warning | Expected for unsigned exes. Click "More info" → "Run anyway". To remove permanently, buy a code-signing certificate and sign `SportsManagerSetup.exe`. |
| First launch crashes with DB error | Delete `%LOCALAPPDATA%\SportsManager\sports_manager.db` and relaunch |
