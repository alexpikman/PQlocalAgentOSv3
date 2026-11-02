@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating isolated Python environment...
  py -3.12 -m venv .venv
  if errorlevel 1 py -m venv .venv
  if errorlevel 1 (echo Python not found.&pause&exit /b 1)
)
if not exist "frontend\assets\fonts\Manrope[wght].ttf" (
  if not exist "frontend\assets\fonts" mkdir "frontend\assets\fonts"
  echo Downloading Manrope Variable font...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing 'https://static.oeh.ac.at/fonts/ofl/manrope/Manrope%%5Bwght%%5D.ttf' -OutFile 'frontend\assets\fonts\Manrope[wght].ttf'"
)
if not exist "frontend\assets\fonts\OFL-Manrope.txt" powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/google/fonts/main/ofl/manrope/OFL.txt' -OutFile 'frontend\assets\fonts\OFL-Manrope.txt'" 2>nul
echo Starting One Core AI on 127.0.0.1:9001...
start "One Core AI Server" /min ".venv\Scripts\python.exe" "backend\app.py"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:9001"
endlocal