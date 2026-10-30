#!/usr/bin/env bash
set -euo pipefail

mkdir -p data/ai
if [ ! -x data/ai/.venv/bin/python ]; then
  python -m venv data/ai/.venv
fi

data/ai/.venv/bin/python -m pip install --upgrade pip setuptools wheel
data/ai/.venv/bin/python -m pip install -r local-voice/requirements.txt

# Compatibility path for app.py, which uses the Windows-style voice interpreter path.
mkdir -p data/ai/.venv/Scripts
ln -sf ../bin/python data/ai/.venv/Scripts/python.exe

data/ai/.venv/bin/python -c "import onnxruntime, vieneu; print('VieNeu OK'); print('ONNX Runtime', onnxruntime.__version__)"
echo "VieNeu Codespaces environment ready."
