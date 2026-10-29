@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Auto Review Video - Check FFmpeg
if not exist ".venv\Scripts\python.exe" (
  echo Chua co .venv. Hay chay INSTALL_AND_RUN.bat truoc.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import imageio_ffmpeg,subprocess,pathlib; p=imageio_ffmpeg.get_ffmpeg_exe(); print('FFmpeg path:',p); print('Exists:',pathlib.Path(p).exists()); cp=subprocess.run([p,'-version'],capture_output=True,text=True); print((cp.stdout or cp.stderr).splitlines()[0] if (cp.stdout or cp.stderr) else 'No output')"
pause
