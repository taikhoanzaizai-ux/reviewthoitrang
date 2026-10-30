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

# Compatibility shim: app.py uses the Windows VieNeu path. Keep Windows logic untouched
# while making the same path resolve inside Linux Codespaces.
mkdir -p data/ai/.venv/Scripts
ln -sf ../bin/python data/ai/.venv/Scripts/python.exe

python -m py_compile app.py video_worker.py voice_worker.py run_codespaces.py
python tests/smoke_test.py

echo "Codespaces setup complete."
