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
echo Starting PQlocalAgentOSv3 at http://127.0.0.1:%PQ_PORT%
python server.py
pause
