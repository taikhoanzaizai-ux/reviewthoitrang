@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === CHECK WEBVIEW2 / PYWEBVIEW ===
if not exist .venv\Scripts\python.exe (
  echo Chua co .venv. Hay chay INSTALL_AND_RUN.bat truoc.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -c "import webview; print('pywebview OK:', webview.__version__ if hasattr(webview,'__version__') else 'installed')"
echo.
echo Neu app van Not Responding ngay khi mo, hay cai/Repair Microsoft Edge WebView2 Runtime.
pause
