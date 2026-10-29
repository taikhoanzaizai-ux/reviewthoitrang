@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Auto Review Video V4.9
if not exist ".venv\Scripts\python.exe" (
  echo Chua co moi truong editor. Chay INSTALL_AND_RUN.bat.
  pause
  exit /b 1
)
if not exist "data\ai\.venv\Scripts\python.exe" (
  echo Chua co moi truong VieNeu. Chay INSTALL_AND_RUN.bat.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py
pause
