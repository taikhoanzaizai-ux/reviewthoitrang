@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
title Auto Review Video V4.9 - Separate VieNeu Environment

echo ============================================================
echo AUTO REVIEW VIDEO V4.9
echo EDITOR PYTHON 3.12 + VIENEU PYTHON 3.11 RIENG
echo KHONG WINGET
echo ============================================================
echo.

set "BOOTPY="
where py >nul 2>nul
if not errorlevel 1 (
  py -c "import sys; print(sys.executable)" > "%TEMP%\arv_bootpy.txt" 2>nul
  if not errorlevel 1 set /p BOOTPY=<"%TEMP%\arv_bootpy.txt"
)
if not defined BOOTPY (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; print(sys.executable)" > "%TEMP%\arv_bootpy.txt" 2>nul
    if not errorlevel 1 set /p BOOTPY=<"%TEMP%\arv_bootpy.txt"
  )
)
if not defined BOOTPY (
  echo [LOI] Khong tim thay Python bootstrap tren may.
  pause
  exit /b 1
)

echo [1/7] Python bootstrap:
"%BOOTPY%" --version

echo.
echo [2/7] Cai uv - khong dung winget...
"%BOOTPY%" -m pip install --upgrade uv
if errorlevel 1 "%BOOTPY%" -m pip install --user --upgrade uv
if errorlevel 1 (
  echo [LOI] Khong cai duoc uv. Kiem tra Internet.
  pause
  exit /b 1
)

echo.
echo [3/7] Tai Python 3.12 cho editor va Python 3.11 cho VieNeu...
"%BOOTPY%" -m uv python install 3.12 3.11
if errorlevel 1 (
  echo [LOI] uv khong tai duoc Python 3.12/3.11. Kiem tra Internet/firewall.
  pause
  exit /b 1
)

REM Editor venv 3.12
if exist ".venv\Scripts\python.exe" (
  set "VER="
  for /f "delims=" %%V in ('".venv\Scripts\python.exe" -c "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))" 2^>nul') do set "VER=%%V"
  if not "!VER!"=="3.12" rmdir /s /q ".venv"
)
if not exist ".venv\Scripts\python.exe" (
  echo [4/7] Tao moi truong editor Python 3.12...
  "%BOOTPY%" -m uv venv --python 3.12 .venv
)
if not exist ".venv\Scripts\python.exe" goto :venvfail

REM VieNeu venv 3.11 - theo kien truc Quan Ban Tin
if exist "data\ai\.venv\Scripts\python.exe" (
  set "VVER="
  for /f "delims=" %%V in ('"data\ai\.venv\Scripts\python.exe" -c "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))" 2^>nul') do set "VVER=%%V"
  if not "!VVER!"=="3.11" rmdir /s /q "data\ai\.venv"
)
if not exist "data\ai\.venv\Scripts\python.exe" (
  echo [5/7] Tao moi truong VieNeu Python 3.11 rieng...
  if not exist "data\ai" mkdir "data\ai"
  "%BOOTPY%" -m uv venv --python 3.11 "data\ai\.venv"
)
if not exist "data\ai\.venv\Scripts\python.exe" goto :voicevenvfail

echo.
echo [6/7] Cai thu vien editor...
"%BOOTPY%" -m uv pip install --python ".venv\Scripts\python.exe" -r requirements.txt
if errorlevel 1 goto :installfail

echo.
echo [7/7] Cai VieNeu 3.8.3 vao Python 3.11 rieng...
"%BOOTPY%" -m uv pip install --python "data\ai\.venv\Scripts\python.exe" -r "local-voice\requirements.txt"
if errorlevel 1 goto :voiceinstallfail

echo.
echo ===== KIEM TRA HAI MOI TRUONG =====
".venv\Scripts\python.exe" -c "import sys; print('EDITOR PYTHON:',sys.version.split()[0])"
"data\ai\.venv\Scripts\python.exe" -c "import sys,importlib.metadata as m; print('VOICE PYTHON:',sys.version.split()[0]); print('VIENEU:',m.version('vieneu'))"
if errorlevel 1 goto :voiceinstallfail

echo.
echo ============================================================
echo CAI DAT THANH CONG
echo Editor = Python 3.12
echo VieNeu = Python 3.11 + vieneu 3.8.3
echo Cache/model VieNeu = data\ai\cache
echo ============================================================
echo Dang mo Auto Review Video...
".venv\Scripts\python.exe" app.py
pause
exit /b 0

:venvfail
echo [LOI] Khong tao duoc moi truong editor Python 3.12.
pause
exit /b 1

:voicevenvfail
echo [LOI] Khong tao duoc moi truong VieNeu Python 3.11.
pause
exit /b 1

:installfail
echo [LOI] Cai thu vien editor that bai.
pause
exit /b 1

:voiceinstallfail
echo [LOI] Cai VieNeu vao Python 3.11 that bai.
echo Xem data\ai neu can kiem tra cache/moi truong.
pause
exit /b 1
