@echo off
rem Start the server in this window. -v logs every button press; remove it for a quieter log.
cd /d "%~dp0.."
.venv\Scripts\python -m seidr_pad -v %*
pause
