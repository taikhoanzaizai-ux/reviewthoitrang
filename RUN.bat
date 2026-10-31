@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Auto Review Video V4.9

if not exist ".venv\Scripts\python.exe" goto :bootstrap
if not exist "data\ai\.venv\Scripts\python.exe" goto :bootstrap

".venv\Scripts\python.exe" app.py
pause
exit /b 0

:bootstrap
echo ============================================================
echo AUTO REVIEW VIDEO - TU DONG CAI MOI TRUONG LAN DAU
echo ============================================================
echo.
echo Chua co day du moi truong editor/VieNeu.
echo Tool se tu chay INSTALL_AND_RUN.bat mot lan.
echo.
if not exist "INSTALL_AND_RUN.bat" (
  echo [LOI] Khong tim thay INSTALL_AND_RUN.bat trong thu muc tool.
  pause
  exit /b 1
)
call INSTALL_AND_RUN.bat
exit /b %errorlevel%
