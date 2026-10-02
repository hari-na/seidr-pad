@echo off
rem One-time setup: Python environment and packages, the ViGEmBus driver, and a desktop shortcut.
cd /d "%~dp0.."

if not exist .venv (
  python -m venv .venv || (echo Python 3.10 or newer is required: https://www.python.org/downloads/ & pause & exit /b 1)
)
.venv\Scripts\python -m pip install -q --upgrade pip
.venv\Scripts\python -m pip install -q -e . || (pause & exit /b 1)

sc query ViGEmBus >nul 2>&1
if %errorlevel%==0 (
  echo ViGEmBus driver already installed.
) else (
  echo Installing the ViGEmBus driver. Approve the Windows prompt and accept the installer defaults.
  msiexec /i "%cd%\.venv\Lib\site-packages\vgamepad\win\vigem\install\x64\ViGEmBusSetup_x64.msi"
  echo If the installer asks you to restart, restart before starting seidr-pad.
)

echo.
choice /M "Create a desktop shortcut"
if %errorlevel%==1 powershell -NoProfile -ExecutionPolicy Bypass -File scripts\create-shortcut.ps1

echo.
echo Setup done. Start seidr-pad from the desktop shortcut or scripts\run.bat
pause
