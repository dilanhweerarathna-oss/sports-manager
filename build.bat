@echo off
REM ============================================================
REM  Sports Manager - one-shot build script (single-file exe)
REM  Produces: dist\SportsManager.exe
REM ============================================================
setlocal

echo.
echo === Installing / upgrading build dependencies ===
python -m pip install --upgrade pip
python -m pip install --upgrade pyinstaller
python -m pip install --upgrade -r requirements.txt
if errorlevel 1 (
    echo.
    echo Dependency install failed. Aborting.
    exit /b 1
)

echo.
echo === Cleaning previous build artifacts ===
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo.
echo === Running PyInstaller ===
pyinstaller SportsManager.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo PyInstaller failed. See output above.
    exit /b 1
)

echo.
echo ============================================================
echo  Build complete.
echo  Run:  dist\SportsManager.exe
echo ============================================================
endlocal
