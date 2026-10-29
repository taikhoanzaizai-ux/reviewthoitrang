from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as app_module


def main():
    required = [
        ROOT / "app.py",
        ROOT / "video_worker.py",
        ROOT / "voice_worker.py",
        ROOT / "static" / "index.html",
        ROOT / "requirements.txt",
        ROOT / "local-voice" / "requirements.txt",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f"Missing required files: {missing}")

    client = app_module.app.test_client()
    r = client.get("/")
    assert r.status_code == 200, r.status_code
    assert b"Auto Review" in r.data or b"V4.9" in r.data, "index page missing app marker"

    ok, info = app_module.check_ffmpeg()
    assert ok, f"FFmpeg check failed: {info}"
    print("FFmpeg:", info)
    print("Flask index: OK")
    print("Core smoke test: OK")


if __name__ == "__main__":
    main()
