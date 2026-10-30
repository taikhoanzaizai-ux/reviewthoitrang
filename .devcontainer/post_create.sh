#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

# Codespaces is a headless Linux environment. Replace desktop OpenCV with
# the headless build and install common shared libraries needed by cv2/ffmpeg.
sudo apt-get update
sudo apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libsm6 libxext6 libxrender1
python -m pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless || true
python -m pip install "opencv-python-headless>=4.8"

# Core editor must be available immediately in Codespaces.
python -m py_compile app.py video_worker.py voice_worker.py run_codespaces.py
python -c "import cv2; print('OpenCV Codespaces:', cv2.__version__)"
python tests/smoke_test.py

# Prepare folders only. VieNeu is installed on demand so a heavy AI dependency
# cannot block Codespaces from starting the editor and forwarding port 8000.
mkdir -p data/ai data/ai/cache data/ai/temp

# Start editor once during creation as an extra fallback. postStart/postAttach
# will also ensure it is running after resume/reconnect.
bash .devcontainer/start_editor.sh

echo "Codespaces core setup complete. Editor should be available on port 8000."
echo "VieNeu can be installed later with: bash .devcontainer/install_vieneu.sh"
