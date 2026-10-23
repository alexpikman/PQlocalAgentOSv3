@echo off
cd /d "%~dp0"
set PQ_PORT=8765
if not exist data mkdir data
python --version >nul 2>&1
if errorlevel 1 (
  echo Python 3 is required. Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)
python -c "import psutil" >nul 2>&1
if errorlevel 1 (
  echo Installing psutil for detailed system telemetry...
  python -m pip install -r requirements.txt
  if errorlevel 1 echo WARNING: psutil installation failed. Basic telemetry will still run, but network/process details may be unavailable.
)
echo Checking for an old server on port %PQ_PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ids = Get-NetTCPConnection -LocalPort %PQ_PORT% -State Listen -ErrorAction SilentlyContinue ^| Select-Object -ExpandProperty OwningProcess -Unique; foreach ($id in $ids) { if ($id -ne $PID) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } }"
echo Starting PQlocalAgentOSv3 at http://127.0.0.1:%PQ_PORT%
python server.py
pause
