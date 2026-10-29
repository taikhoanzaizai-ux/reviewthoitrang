@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===== AUTO REVIEW VIDEO - CHECK PYTHON =====
echo.
echo Python mac dinh:
python --version 2>nul
echo.
echo Python Launcher:
py -0p 2>nul
echo.
if exist ".venv\Scripts\python.exe" (
  echo Tool VENV:
  ".venv\Scripts\python.exe" -c "import sys; print(sys.version)"
  echo.
  ".venv\Scripts\python.exe" -c "import onnxruntime; print('ONNX Runtime:',onnxruntime.__version__)" 2>nul
) else (
  echo Chua co .venv
)
echo.
pause
