; ============================================================
; Inno Setup script for Sports Manager
; Compile with: ISCC.exe installer.iss
; Produces:     installer\SportsManagerSetup.exe
; ============================================================

#define MyAppName        "Sports Manager"
#define MyAppVersion     "1.0.0"
#define MyAppPublisher   "School Sports Manager"
#define MyAppExeName     "SportsManager.exe"

[Setup]
AppId={{8F1B4D2E-5A6C-4E7A-9D3B-7C2A1F4E9B11}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SportsManager
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=SportsManagerSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
PrivilegesRequired=admin
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; Ship the entire PyInstaller --onedir output as-is
Source: "dist\SportsManager\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "Launch {#MyAppName}"; \
    Flags: nowait postinstall skipifsilent

; ============================================================
; Note: user data (database, logs, reports, backups) is stored
; in %LOCALAPPDATA%\SportsManager and is NOT removed by the
; uninstaller. To wipe a school's data, delete that folder by
; hand after uninstalling.
; ============================================================
