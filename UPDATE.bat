@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Auto Review Video - Update tu GitHub

echo ============================================================
echo AUTO REVIEW VIDEO - CAP NHAT TU GITHUB
echo ============================================================
echo.

echo Neu Auto Review Video dang mo, hay dong cua so backend truoc khi update.
echo.

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" update_tool.py
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    py update_tool.py
  ) else (
    where python >nul 2>nul
    if not errorlevel 1 (
      python update_tool.py
    ) else (
      echo [LOI] Khong tim thay Python de chay updater.
      echo Hay chay INSTALL_AND_RUN.bat mot lan truoc.
      pause
      exit /b 1
    )
  )
)

if errorlevel 1 (
  echo.
  echo Cap nhat that bai.
  pause
  exit /b 1
)

exit /b 0
