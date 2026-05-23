# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Sports Manager - single-file build.

Build:    pyinstaller SportsManager.spec --clean --noconfirm
Output:   dist\\SportsManager.exe   (single executable, no _internal folder)

Note: onefile mode extracts to a temp directory on each launch, so first
start is slower than a folder build. Good for distributing one file to
another PC for testing.
"""
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH)

# Bundle non-Python resources the app reads at runtime.
# (source_path_relative_to_project, dest_folder_inside_bundle)
datas = [
    ('database/schema.sql',                       'database'),
    ('database/migration_001_add_payment_type.py', 'database'),
]

# Ship the assets folder only if it has any files in it
if (PROJECT_ROOT / 'assets').exists() and any((PROJECT_ROOT / 'assets').iterdir()):
    datas.append(('assets', 'assets'))

# Optional .ico — used for the exe and shortcut icon
_icon_path = PROJECT_ROOT / 'assets' / 'icon.ico'
icon = str(_icon_path) if _icon_path.exists() else None

# Modules we *know* we depend on but PyInstaller may not auto-detect
hiddenimports = [
    'reportlab',
    'reportlab.pdfgen',
    'reportlab.platypus',
    'reportlab.lib.styles',
    'reportlab.lib.pagesizes',
    'reportlab.lib.colors',
    'reportlab.lib.units',
]

# Modules we explicitly do NOT need — keeps the bundle smaller.
# These get auto-pulled by PyInstaller hooks because they're installed in the
# system Python (left over from other projects); the Sports Manager code never
# imports them.
excludes = [
    # Other GUI / plotting frameworks
    'tkinter', 'matplotlib', 'numpy', 'pandas',
    'PyQt5', 'PyQt6', 'PySide2',
    # ML / scientific stack (huge, unused)
    'torch', 'torchvision', 'torchaudio',
    'scipy',
    'sklearn', 'sympy', 'numba',
    # Web / async / data libraries (unused)
    'cryptography', 'pydantic', 'pydantic_core',
    'sqlalchemy', 'aiohttp', 'httpx', 'requests',
    'urllib3', 'fsspec',
    'google', 'grpc',
    # Win32 / COM (we only need pywin32 indirectly via PySide6 framing)
    'win32com', 'Pythonwin', 'pywin32_system32',
    # Terminal UI / debugging tools
    'IPython', 'jupyter', 'notebook',
    'rich', 'pygments', 'colorama',
    # Test frameworks
    'pytest', 'test', 'unittest', 'pydoc', 'doctest',
    # Misc
    'zstandard', 'tzdata',
]


a = Analysis(
    ['main.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SportsManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)
