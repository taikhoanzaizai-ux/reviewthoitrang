import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
RAW_VERSION = "https://raw.githubusercontent.com/taikhoanzaizai-ux/reviewthoitrang/main/version.json"
MAIN_ZIP = "https://github.com/taikhoanzaizai-ux/reviewthoitrang/archive/refs/heads/main.zip"
LOCAL_VERSION = APP_DIR / "version.json"

PRESERVE_TOP = {
    ".venv", "data", "voice_library", "uploads", "exports", "generated",
    "preview_cache", ".git", ".vscode"
}
PRESERVE_FILES = {"render_error.log", "ffmpeg_export_debug.txt"}


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "AutoReviewVideo-Updater/1.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def download(url: str, dst: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "AutoReviewVideo-Updater/1.1"})
    with urllib.request.urlopen(req, timeout=120) as r, dst.open("wb") as f:
        total = int(r.headers.get("Content-Length", "0") or 0)
        got = 0
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if total:
                print(f"\rDang tai ban cap nhat... {int(got*100/total)}%", end="", flush=True)
        print()


def copy_tree_update(src_root: Path, dst_root: Path):
    for item in src_root.iterdir():
        if item.name in PRESERVE_TOP or item.name in PRESERVE_FILES:
            continue
        dst = dst_root / item.name
        if item.is_dir():
            if dst.exists() and dst.is_file():
                dst.unlink()
            dst.mkdir(parents=True, exist_ok=True)
            copy_tree_update(item, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dst)


def run_checked(cmd, label):
    print(f"\n[{label}] {' '.join(map(str, cmd))}")
    cp = subprocess.run(cmd, cwd=APP_DIR)
    if cp.returncode != 0:
        raise RuntimeError(f"{label} that bai (ma {cp.returncode}).")


def environments_ready():
    return (
        (APP_DIR / ".venv" / "Scripts" / "python.exe").exists()
        and (APP_DIR / "data" / "ai" / ".venv" / "Scripts" / "python.exe").exists()
    )


def bootstrap_if_needed():
    if environments_ready():
        return
    installer = APP_DIR / "INSTALL_AND_RUN.bat"
    if not installer.exists():
        raise RuntimeError("Thieu INSTALL_AND_RUN.bat de tao moi truong lan dau.")
    print("\nChua co moi truong editor/VieNeu. Dang tu dong cai dat lan dau...")
    cp = subprocess.run(["cmd", "/c", "call", str(installer)], cwd=APP_DIR)
    if cp.returncode != 0:
        raise RuntimeError("Cai moi truong lan dau that bai.")


def install_dependencies():
    py = APP_DIR / ".venv" / "Scripts" / "python.exe"
    if py.exists():
        run_checked([str(py), "-m", "pip", "install", "-r", "requirements.txt"], "Cap nhat thu vien editor")

    voice_py = APP_DIR / "data" / "ai" / ".venv" / "Scripts" / "python.exe"
    voice_req = APP_DIR / "local-voice" / "requirements.txt"
    if voice_py.exists() and voice_req.exists():
        run_checked([str(voice_py), "-m", "pip", "install", "-r", str(voice_req)], "Cap nhat thu vien VieNeu")


def main():
    print("=" * 64)
    print("AUTO REVIEW VIDEO - WINDOWS UPDATER")
    print("Nguon cap nhat: GitHub main")
    print("=" * 64)

    local = read_json(LOCAL_VERSION, {"version": "unknown"})
    try:
        remote = fetch_json(RAW_VERSION)
    except Exception as e:
        print(f"Khong kiem tra duoc version GitHub: {e}")
        remote = {"version": "latest", "archive_url": MAIN_ZIP}

    print("Version tren may :", local.get("version", "unknown"))
    print("Version tren GitHub:", remote.get("version", "latest"))

    tmpdir = Path(tempfile.mkdtemp(prefix="arv_update_"))
    try:
        archive = tmpdir / "main.zip"
        download(remote.get("archive_url") or MAIN_ZIP, archive)
        with zipfile.ZipFile(archive, "r") as z:
            z.extractall(tmpdir / "src")
        roots = [p for p in (tmpdir / "src").iterdir() if p.is_dir()]
        if not roots:
            raise RuntimeError("Khong tim thay source sau khi giai nen.")

        print("Dang cap nhat source (giu nguyen cache/voice/video/export)...")
        copy_tree_update(roots[0], APP_DIR)

        if not environments_ready():
            bootstrap_if_needed()
        else:
            install_dependencies()

        print("\nCAP NHAT THANH CONG")
        print("Version hien tai:", read_json(LOCAL_VERSION, remote).get("version", remote.get("version")))
        print("Du lieu nguoi dung va cache VieNeu da duoc giu nguyen.")

        run_bat = APP_DIR / "RUN.bat"
        if run_bat.exists() and environments_ready():
            print("Dang mo lai Auto Review Video...")
            subprocess.Popen(["cmd", "/c", "start", "", str(run_bat)], cwd=APP_DIR)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n[LOI CAP NHAT]", e)
        input("Nhan Enter de dong...")
        sys.exit(1)
