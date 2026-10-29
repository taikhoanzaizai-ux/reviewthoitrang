
import os, sys, json, traceback
from pathlib import Path

def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

def main():
    out_json = sys.argv[-1]
    try:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from vieneu import Vieneu

        cmd = sys.argv[1]
        if cmd == "list":
            mode = sys.argv[2]
            tts = Vieneu(mode=mode)
            voices = []
            for item in tts.list_preset_voices():
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    voices.append({"label": str(item[0]), "id": str(item[1])})
                else:
                    voices.append({"label": str(item), "id": str(item)})
            write(out_json, {"ok": True, "voices": voices})
            return

        if cmd == "synth":
            req = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
            mode = req.get("mode", "v3turbo")
            text = (req.get("text") or "").strip()
            if not text:
                raise RuntimeError("Lời review/Voice đang trống.")
            out_wav = req["out_wav"]
            tts = Vieneu(mode=mode)
            ref = req.get("ref_audio")
            voice = req.get("voice")
            kwargs = {}
            if ref:
                audio = tts.infer(text, ref_audio=ref, denoise=True, **kwargs)
            else:
                audio = tts.infer(text, voice=voice or None, **kwargs)
            tts.save(audio, out_wav)
            if not Path(out_wav).exists() or Path(out_wav).stat().st_size < 1000:
                raise RuntimeError("VieNeu không tạo được file voice hợp lệ.")
            write(out_json, {"ok": True, "out_wav": out_wav})
            return

        raise RuntimeError("Lệnh voice worker không hợp lệ.")
    except Exception as e:
        write(out_json, {"ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()})

if __name__ == "__main__":
    main()
