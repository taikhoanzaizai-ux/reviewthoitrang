import os
import time
from pathlib import Path

from flask import jsonify, request
from waitress import serve

import app as core

app = core.app
CHUNK_DIR = core.UPLOADS / ".chunks"
CHUNK_DIR.mkdir(parents=True, exist_ok=True)


def _safe_upload_id(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isalnum() or ch in "-_" )[:80]


@app.route("/api/cs_upload_chunk", methods=["POST"])
def cs_upload_chunk():
    try:
        upload_id = _safe_upload_id(request.form.get("upload_id", ""))
        index = int(request.form.get("index", "0"))
        chunk = request.files.get("chunk")
        if not upload_id or chunk is None:
            return jsonify(ok=False, error="Thiếu chunk upload."), 400
        d = CHUNK_DIR / upload_id
        d.mkdir(parents=True, exist_ok=True)
        chunk.save(d / f"{index:06d}.part")
        return jsonify(ok=True, index=index)
    except Exception as e:
        return jsonify(ok=False, error=f"{type(e).__name__}: {e}"), 500


@app.route("/api/cs_upload_finalize", methods=["POST"])
def cs_upload_finalize():
    try:
        q = request.get_json(force=True) or {}
        upload_id = _safe_upload_id(q.get("upload_id", ""))
        filename = core.secure_filename(q.get("filename", "")) or f"video_{int(time.time())}.mp4"
        expected = int(q.get("total_chunks", 0))
        if not upload_id or expected <= 0:
            return jsonify(ok=False, error="Thông tin finalize không hợp lệ."), 400

        d = CHUNK_DIR / upload_id
        parts = sorted(d.glob("*.part"))
        if len(parts) != expected:
            return jsonify(ok=False, error=f"Thiếu chunk: nhận {len(parts)}/{expected}."), 400

        dst = core.UPLOADS / f"{int(time.time()*1000)}_{filename}"
        with dst.open("wb") as out:
            for p in parts:
                with p.open("rb") as src:
                    while True:
                        buf = src.read(1024 * 1024)
                        if not buf:
                            break
                        out.write(buf)

        data = core.worker_call(["probe", str(dst)], timeout=60)
        core.STATE["video"] = dst
        core.STATE["meta"] = data["meta"]

        for p in parts:
            try:
                p.unlink()
            except Exception:
                pass
        try:
            d.rmdir()
        except Exception:
            pass

        return jsonify(
            ok=True,
            name=filename,
            meta=data["meta"],
            url=f"/media/source?v={int(time.time())}",
        )
    except Exception as e:
        return jsonify(ok=False, error=f"{type(e).__name__}: {e}"), 500


@app.after_request
def inject_codespaces_uploader(response):
    try:
        if request.path == "/" and response.status_code == 200:
            response.direct_passthrough = False
            ctype = response.headers.get("Content-Type", "")
            if "text/html" in ctype:
                html = response.get_data(as_text=True)
                tag = '<script src="/codespaces-upload.js?v=2"></script>'
                if tag not in html:
                    html = html.replace("</body>", tag + "</body>")
                    response.set_data(html)
                    response.headers["Content-Length"] = str(len(response.get_data()))
    except Exception:
        pass
    return response


def main():
    port = int(os.environ.get("PORT", "8000"))
    print("=" * 62)
    print("AUTO REVIEW VIDEO - GITHUB CODESPACES")
    print(f"Listening on 0.0.0.0:{port}")
    print("Chunked video upload enabled for Codespaces.")
    print("Open the forwarded port from the Codespaces Ports tab.")
    print("=" * 62)
    serve(app, host="0.0.0.0", port=port, threads=8)


if __name__ == "__main__":
    main()
