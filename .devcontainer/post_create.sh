#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

# Codespaces is headless Linux. Use one repair path that also works when an
# unrelated Yarn apt source has a broken/missing signing key.
bash .devcontainer/repair_opencv.sh

# Core editor must be available immediately in Codespaces.
python -m py_compile app.py video_worker.py voice_worker.py run_codespaces.py
python tests/smoke_test.py

# Prepare folders only. VieNeu is installed on demand so a heavy AI dependency
# cannot block Codespaces from starting the editor and forwarding port 8000.
mkdir -p data/ai data/ai/cache data/ai/temp

# Start editor once during creation as an extra fallback. postStart/postAttach
# will also ensure it is running after resume/reconnect.
bash .devcontainer/start_editor.sh

echo "Codespaces core setup complete. Editor should be available on port 8000."
echo "VieNeu can be installed later with: bash .devcontainer/install_vieneu.sh"
