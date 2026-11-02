@echo off
setlocal
cd /d "%~dp0"
echo.
echo  ONE CORE AI v1 - LOCAL WORKSPACE
echo.
if not exist ".venv\Scripts\python.exe" (
  echo Creating isolated Python environment...
  py -3.12 -m venv .venv
  if errorlevel 1 py -m venv .venv
  if errorlevel 1 (echo Python was not found.&pause&exit /b 1)
)
echo Starting standalone server on port 9001...
start "One Core AI Server" /min ".venv\Scripts\python.exe" "backend\app.py"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:9001"
echo One Core AI: http://127.0.0.1:9001
endlocal