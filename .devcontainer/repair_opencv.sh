#!/usr/bin/env bash
set -euo pipefail

echo "[Codespaces] Repairing OpenCV/headless runtime..."

sudo apt-get update
sudo apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libsm6 libxext6 libxrender1

python -m pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless || true
python -m pip install --upgrade --force-reinstall "opencv-python-headless>=4.8"

python - <<'PY'
import cv2
print('OpenCV OK:', cv2.__version__)
PY

echo "[Codespaces] OpenCV repair complete."
