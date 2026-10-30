#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

mkdir -p data/ai
if [ ! -x data/ai/.venv/bin/python ]; then
  python -m venv data/ai/.venv
fi

data/ai/.venv/bin/python -m pip install --upgrade pip setuptools wheel
# Install VieNeu dependencies now so Voice Studio can be tested in Codespaces.
data/ai/.venv/bin/python -m pip install -r local-voice/requirements.txt

python -m py_compile app.py video_worker.py voice_worker.py run_codespaces.py
python tests/smoke_test.py

echo "Codespaces setup complete."
