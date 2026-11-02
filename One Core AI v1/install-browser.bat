@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run start.bat once to create the isolated Python environment.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-browser.txt
if errorlevel 1 (echo Playwright installation failed.&pause&exit /b 1)
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (echo Chromium installation failed.&pause&exit /b 1)
echo Virtual browser installed. Restart One Core AI.
pause
endlocal