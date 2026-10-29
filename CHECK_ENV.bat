@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===== AUTO REVIEW VIDEO V4.9 - CHECK =====
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; print('EDITOR:',sys.version)"
) else echo Editor venv: CHUA CO

echo.
if exist "data\ai\.venv\Scripts\python.exe" (
  "data\ai\.venv\Scripts\python.exe" -c "import sys,importlib.metadata as m; print('VOICE:',sys.version); print('VIENEU:',m.version('vieneu'))"
) else echo Voice venv: CHUA CO

echo.
echo Cache VieNeu: %CD%\data\ai\cache
echo Thu vien Voice: %CD%\voice_library
pause
