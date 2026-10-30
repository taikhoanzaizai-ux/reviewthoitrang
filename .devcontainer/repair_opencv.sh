#!/usr/bin/env bash
set -euo pipefail

echo "[Codespaces] Repairing OpenCV/headless runtime..."

# Some Codespaces images contain a Yarn apt source whose signing key may be
# missing/expired. That unrelated repository can make `apt-get update` fail and
# block our OpenCV repair. Temporarily disable only Yarn sources, update Debian,
# install the shared libraries, then restore the Yarn source files.
TMP_APT_DIR="$(mktemp -d)"
restore_yarn_sources() {
  shopt -s nullglob
  for f in "$TMP_APT_DIR"/*; do
    sudo mv "$f" /etc/apt/sources.list.d/ 2>/dev/null || true
  done
  rmdir "$TMP_APT_DIR" 2>/dev/null || true
}
trap restore_yarn_sources EXIT

shopt -s nullglob
for f in /etc/apt/sources.list.d/*yarn*.list /etc/apt/sources.list.d/*yarn*.sources; do
  echo "[Codespaces] Temporarily disabling broken apt source: $f"
  sudo mv "$f" "$TMP_APT_DIR/"
done
shopt -u nullglob

sudo apt-get update
sudo apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libsm6 libxext6 libxrender1

# Avoid mixing the desktop and headless OpenCV wheels.
python -m pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless || true
python -m pip install --no-cache-dir --upgrade --force-reinstall "opencv-python-headless>=4.8"

python - <<'PY'
import cv2
print('OpenCV OK:', cv2.__version__)
print('cv2 path:', cv2.__file__)
PY

echo "[Codespaces] OpenCV repair complete."
