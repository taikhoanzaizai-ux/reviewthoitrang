
import os, sys, json, time, socket, subprocess, tempfile, traceback, wave, webbrowser, threading, shutil
from pathlib import Path
from flask import Flask, send_file, jsonify, request
from PIL import Image, ImageDraw, ImageFont
from werkzeug.utils import secure_filename
from waitress import serve
import imageio_ffmpeg

APP_DIR = Path(__file__).resolve().parent
STATIC = APP_DIR / "static"
WORKER = APP_DIR / "video_worker.py"
VOICE_WORKER = APP_DIR / "voice_worker.py"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
GEN = APP_DIR / "generated"
GEN.mkdir(exist_ok=True)
EXPORT_DIR = APP_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)
UPLOADS = APP_DIR / "uploads"
UPLOADS.mkdir(exist_ok=True)
VOICE_LIBRARY_DIR = APP_DIR / "voice_library"
VOICE_LIBRARY_DIR.mkdir(exist_ok=True)
VOICE_LIBRARY_FILE = VOICE_LIBRARY_DIR / "library.json"
AI_DATA = APP_DIR / "data" / "ai"
AI_DATA.mkdir(parents=True, exist_ok=True)
VOICE_PYTHON = AI_DATA / ".venv" / "Scripts" / "python.exe"

app = Flask(__name__, static_folder=str(STATIC), static_url_path="")
STATE = {"video": None, "meta": None, "assets": {}}
EXPORT_JOBS = {}

def hidden_flags():
    return 0x08000000 if os.name == "nt" else 0

def ps_dialog(save=False, filter_text="All files|*.*", title="Chọn file", default_name=""):
    if os.name != "nt":
        return None
    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        raise RuntimeError("Không tìm thấy PowerShell.")
    cls = "SaveFileDialog" if save else "OpenFileDialog"
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.{cls}
$d.Title = '{title.replace("'", "''")}'
$d.Filter = '{filter_text.replace("'", "''")}'
"""
    if save and default_name:
        script += f"$d.FileName = '{default_name.replace(chr(39), chr(39)*2)}'\n"
    script += """
$r = $d.ShowDialog()
if ($r -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $d.FileName }
"""
    cp = subprocess.run([ps, "-NoProfile", "-STA", "-Command", script],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True, encoding="utf-8", errors="ignore",
                        creationflags=hidden_flags())
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or "Không mở được hộp thoại Windows.")
    p = cp.stdout.strip().splitlines()
    return p[-1].strip() if p else None

def worker_call(args, timeout=180):
    out = Path(tempfile.gettempdir()) / f"arv44_{os.getpid()}_{int(time.time()*1000)}.json"
    cp = subprocess.run(
        [sys.executable, str(WORKER)] + args + [str(out)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="ignore",
        timeout=timeout, creationflags=hidden_flags()
    )
    if not out.exists():
        raise RuntimeError(cp.stderr[-2500:] or "Video worker không trả kết quả.")
    data = json.loads(out.read_text(encoding="utf-8"))
    try: out.unlink()
    except: pass
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "Video worker lỗi."))
    return data

def voice_call(args, timeout=900):
    out = Path(tempfile.gettempdir()) / f"arv44voice_{os.getpid()}_{int(time.time()*1000)}.json"
    if not VOICE_PYTHON.exists():
        raise RuntimeError("VieNeu chưa được chuẩn bị. Hãy chạy INSTALL_AND_RUN.bat để cài môi trường Voice Python 3.11.")
    env = os.environ.copy()
    cache = AI_DATA / "cache"
    hf = cache / "huggingface"
    for p in [cache, hf, hf/"hub", cache/"torch", AI_DATA/"temp"]: p.mkdir(parents=True, exist_ok=True)
    env["HF_HOME"] = str(hf)
    env["HF_HUB_CACHE"] = str(hf / "hub")
    env["HUGGINGFACE_HUB_CACHE"] = str(hf / "hub")
    env["TORCH_HOME"] = str(cache / "torch")
    env["XDG_CACHE_HOME"] = str(cache)
    env["PIP_CACHE_DIR"] = str(cache / "pip")
    env["TEMP"] = str(AI_DATA / "temp")
    env["TMP"] = str(AI_DATA / "temp")
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    cp = subprocess.run(
        [str(VOICE_PYTHON), str(VOICE_WORKER)] + args + [str(out)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="ignore",
        timeout=timeout, creationflags=hidden_flags(), env=env
    )
    if not out.exists():
        raise RuntimeError(cp.stderr[-3000:] or "VieNeu worker không trả kết quả.")
    data = json.loads(out.read_text(encoding="utf-8"))
    try: out.unlink()
    except: pass
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "VieNeu lỗi."))
    return data

def wav_duration(p):
    try:
        with wave.open(str(p), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except:
        return 0.0


def load_voice_library():
    if not VOICE_LIBRARY_FILE.exists():
        return {"preset_loaded": [], "clones": [], "last_preset": ""}
    try:
        data=json.loads(VOICE_LIBRARY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data,dict): data={}
        data.setdefault("preset_loaded",[])
        data.setdefault("clones",[])
        data.setdefault("last_preset","")
        return data
    except:
        return {"preset_loaded": [], "clones": [], "last_preset": ""}

def save_voice_library(data):
    VOICE_LIBRARY_FILE.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")

def get_font(size):
    candidates=[r"C:\\Windows\\Fonts\\arialbd.ttf",r"C:\\Windows\\Fonts\\segoeuib.ttf",r"C:\\Windows\\Fonts\\arial.ttf"]
    for p in candidates:
        if Path(p).exists():
            try:return ImageFont.truetype(p,size=size)
            except:pass
    return ImageFont.load_default()

def make_text_png(text, tw, th, idx):
    text=(text or "").strip()
    if not text:return None
    font_size=max(28,int(tw*0.055))
    font=get_font(font_size)
    maxw=int(tw*0.86)
    words=text.split()
    lines=[];cur=""
    dummy=Image.new("RGBA",(10,10));d=ImageDraw.Draw(dummy)
    for w in words:
        test=(cur+" "+w).strip()
        bb=d.textbbox((0,0),test,font=font,stroke_width=2)
        if bb[2]-bb[0] <= maxw or not cur: cur=test
        else: lines.append(cur);cur=w
    if cur:lines.append(cur)
    if not lines:lines=[text]
    gap=max(8,int(font_size*0.2))
    widths=[];heights=[]
    for line in lines:
        bb=d.textbbox((0,0),line,font=font,stroke_width=2);widths.append(bb[2]-bb[0]);heights.append(bb[3]-bb[1])
    W=min(tw,max(widths)+60);H=sum(heights)+gap*(len(lines)-1)+40
    im=Image.new("RGBA",(W,H),(0,0,0,0));dr=ImageDraw.Draw(im)
    y=20
    for line,h in zip(lines,heights):
        bb=dr.textbbox((0,0),line,font=font,stroke_width=2);w=bb[2]-bb[0]
        x=(W-w)//2
        dr.rounded_rectangle((max(0,x-18),y-6,min(W,x+w+18),y+h+8),radius=10,fill=(0,0,0,130))
        dr.text((x,y),line,font=font,fill=(255,255,255,255),stroke_width=2,stroke_fill=(0,0,0,220))
        y+=h+gap
    p=GEN/f"text_{idx}_{int(time.time()*1000)}.png";im.save(p)
    return p

@app.route("/")
def index():
    return send_file(STATIC / "index.html")

@app.route("/media/source")
def media_source():
    p = STATE.get("video")
    return send_file(p, conditional=True) if p and Path(p).exists() else ("No video", 404)

@app.route("/media/asset/<asset_id>")
def media_asset(asset_id):
    p = STATE["assets"].get(asset_id)
    return send_file(p, conditional=True) if p and Path(p).exists() else ("No asset", 404)


@app.route("/api/upload_video", methods=["POST"])
def api_upload_video():
    try:
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify(ok=False, error="Chưa chọn video.")
        name = secure_filename(f.filename) or f"video_{int(time.time())}.mp4"
        dst = UPLOADS / f"{int(time.time()*1000)}_{name}"
        f.save(dst)
        data = worker_call(["probe", str(dst)], timeout=40)
        STATE["video"] = dst
        STATE["meta"] = data["meta"]
        return jsonify(ok=True, name=f.filename, meta=data["meta"], url=f"/media/source?v={int(time.time())}")
    except Exception as e:
        return jsonify(ok=False, error=f"{type(e).__name__}: {e}")

@app.route("/api/upload_audio", methods=["POST"])
def api_upload_audio():
    try:
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify(ok=False, error="Chưa chọn audio.")
        name = secure_filename(f.filename) or f"audio_{int(time.time())}.wav"
        dst = UPLOADS / f"{int(time.time()*1000)}_{name}"
        f.save(dst)
        aid = f"a{int(time.time()*1000)}"
        STATE["assets"][aid] = dst
        return jsonify(ok=True, id=aid, name=f.filename, url=f"/media/asset/{aid}")
    except Exception as e:
        return jsonify(ok=False, error=f"{type(e).__name__}: {e}")


@app.route("/api/upload_voice_audio", methods=["POST"])
def api_upload_voice_audio():
    try:
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify(ok=False, error="Chưa chọn file voice.")
        name = secure_filename(f.filename) or f"voice_audio_{int(time.time())}.wav"
        dst = UPLOADS / f"{int(time.time()*1000)}_{name}"
        f.save(dst)
        aid = f"vu{int(time.time()*1000)}"
        STATE["assets"][aid] = dst
        # duration by ffmpeg probe fallback via worker probe if audio-only probe unsupported
        dur=0.0
        try:
            cp=subprocess.run([FFMPEG,"-hide_banner","-loglevel","error","-i",str(dst),"-f","null","-"],
                              stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,encoding="utf-8",errors="ignore",
                              creationflags=hidden_flags())
            import re as _re
            m=_re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)",cp.stderr or "")
            if m: dur=int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3))
        except: pass
        return jsonify(ok=True,id=aid,name=f.filename,url=f"/media/asset/{aid}",duration=dur)
    except Exception as e:
        return jsonify(ok=False,error=f"{type(e).__name__}: {e}")

@app.route("/api/upload_clone_voice", methods=["POST"])
def api_upload_clone_voice():
    try:
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify(ok=False, error="Chưa chọn file giọng mẫu.")
        name = secure_filename(f.filename) or f"voice_ref_{int(time.time())}.wav"
        dst = UPLOADS / f"{int(time.time()*1000)}_{name}"
        f.save(dst)
        aid = f"ref{int(time.time()*1000)}"
        STATE["assets"][aid] = dst
        return jsonify(ok=True, id=aid, name=f.filename)
    except Exception as e:
        return jsonify(ok=False, error=f"{type(e).__name__}: {e}")

@app.route("/api/pick_video", methods=["POST"])
def api_pick_video():
    try:
        p = ps_dialog(False, "Video files|*.mp4;*.mov;*.mkv;*.avi;*.m4v|All files|*.*", "Chọn video")
        if not p:
            return jsonify(ok=False, cancelled=True)
        path = Path(p)
        data = worker_call(["probe", str(path)], timeout=25)
        STATE["video"] = path
        STATE["meta"] = data["meta"]
        return jsonify(ok=True, name=path.name, meta=data["meta"], url=f"/media/source?v={int(time.time())}")
    except Exception as e:
        return jsonify(ok=False, error=f"{type(e).__name__}: {e}")

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    try:
        q = request.get_json(force=True) or {}
        if not STATE.get("video"):
            return jsonify(ok=False, error="Chưa chọn video.")
        data = worker_call(
            ["analyze", str(STATE["video"]), str(int(q.get("strength",3))), str(int(q.get("target",30)))],
            timeout=max(120, int((STATE["meta"] or {}).get("duration",60)*2 + 60))
        )
        return jsonify(data)
    except Exception as e:
        return jsonify(ok=False, error=f"{type(e).__name__}: {e}")

@app.route("/api/pick_audio", methods=["POST"])
def api_pick_audio():
    try:
        p = ps_dialog(False, "Audio files|*.wav;*.mp3;*.m4a;*.flac;*.aac|All files|*.*", "Chọn audio")
        if not p: return jsonify(ok=False, cancelled=True)
        path=Path(p); aid=f"a{int(time.time()*1000)}"; STATE["assets"][aid]=path
        return jsonify(ok=True,id=aid,name=path.name,url=f"/media/asset/{aid}")
    except Exception as e:
        return jsonify(ok=False,error=f"{type(e).__name__}: {e}")

@app.route("/api/pick_clone_voice", methods=["POST"])
def api_pick_clone_voice():
    try:
        p = ps_dialog(False, "Voice sample|*.wav;*.mp3;*.m4a;*.flac;*.aac;*.mp4;*.mov|All files|*.*", "Chọn giọng mẫu")
        if not p: return jsonify(ok=False,cancelled=True)
        path=Path(p); aid=f"ref{int(time.time()*1000)}"; STATE["assets"][aid]=path
        return jsonify(ok=True,id=aid,name=path.name)
    except Exception as e:
        return jsonify(ok=False,error=f"{type(e).__name__}: {e}")

@app.route("/api/list_voices", methods=["POST"])
def api_list_voices():
    try:
        q=request.get_json(force=True) or {}
        return jsonify(voice_call(["list",q.get("mode","v3turbo")],timeout=600))
    except Exception as e:
        return jsonify(ok=False,error=f"{type(e).__name__}: {e}")


@app.route("/api/voice_library", methods=["GET"])
def api_voice_library():
    try:
        lib=load_voice_library();clean=[];changed=False
        for c in lib.get("clones",[]):
            if c.get("path") and Path(c["path"]).exists():clean.append(c)
            else:changed=True
        if changed:lib["clones"]=clean;save_voice_library(lib)
        return jsonify(ok=True,library=lib)
    except Exception as e:return jsonify(ok=False,error=f"{type(e).__name__}: {e}")

@app.route("/api/save_preset_voices", methods=["POST"])
def api_save_preset_voices():
    try:
        q=request.get_json(force=True) or {};lib=load_voice_library();lib["preset_loaded"]=q.get("voices") or [];lib["last_preset"]=q.get("selected") or lib.get("last_preset","");save_voice_library(lib);return jsonify(ok=True)
    except Exception as e:return jsonify(ok=False,error=f"{type(e).__name__}: {e}")

@app.route("/api/save_clone_voice", methods=["POST"])
def api_save_clone_voice():
    try:
        q=request.get_json(force=True) or {};aid=q.get("assetId");src=STATE["assets"].get(aid)
        if not src or not Path(src).exists():return jsonify(ok=False,error="Không tìm thấy file giọng mẫu.")
        name=(q.get("name") or Path(src).stem or "Giọng clone").strip();ext=Path(src).suffix or ".wav";cid=f"clone_{int(time.time()*1000)}";dst=VOICE_LIBRARY_DIR/f"{cid}{ext}";shutil.copy2(src,dst)
        lib=load_voice_library();lib.setdefault("clones",[]).append({"id":cid,"name":name,"path":str(dst)});save_voice_library(lib);STATE["assets"][cid]=dst
        return jsonify(ok=True,id=cid,name=name)
    except Exception as e:return jsonify(ok=False,error=f"{type(e).__name__}: {e}")

@app.route("/api/use_saved_clone", methods=["POST"])
def api_use_saved_clone():
    try:
        q=request.get_json(force=True) or {};cid=q.get("id");lib=load_voice_library();it=next((x for x in lib.get("clones",[]) if x.get("id")==cid),None)
        if not it or not Path(it.get("path","")).exists():return jsonify(ok=False,error="Giọng clone đã lưu không còn tồn tại.")
        STATE["assets"][cid]=Path(it["path"]);return jsonify(ok=True,id=cid,name=it.get("name") or cid)
    except Exception as e:return jsonify(ok=False,error=f"{type(e).__name__}: {e}")

@app.route("/api/synth_voice", methods=["POST"])
def api_synth_voice():
    try:
        payload=request.get_json(force=True) or {}
        text=(payload.get("text") or "").strip()
        if not text:return jsonify(ok=False,error="Lời review/Voice đang trống.")
        ts=int(time.time()*1000); out=GEN/f"voice_{ts}.wav"
        ref=STATE["assets"].get(payload.get("refId")) if payload.get("refId") else None
        req={
            "mode":payload.get("mode","v3turbo"),
            "text":text,
            "voice":payload.get("voice"),
            "ref_audio":str(ref) if ref else None,
            "out_wav":str(out)
        }
        req_path=GEN/f"voice_req_{ts}.json"
        req_path.write_text(json.dumps(req,ensure_ascii=False),encoding="utf-8")
        try: voice_call(["synth",str(req_path)],timeout=1200)
        finally:
            try:req_path.unlink()
            except:pass
        speed=max(0.5,min(2.0,float(payload.get("speed",1.0) or 1.0)))
        final_out=out
        if abs(speed-1.0)>0.001:
            speed_out=GEN/f"voice_{ts}_speed.wav"
            cp=subprocess.run([FFMPEG,"-y","-hide_banner","-loglevel","error","-i",str(out),"-filter:a",atempo_chain(speed),str(speed_out)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,encoding="utf-8",errors="ignore",creationflags=hidden_flags())
            if cp.returncode!=0:raise RuntimeError(cp.stderr[-2000:] or "Không chỉnh được tốc độ voice.")
            final_out=speed_out
        aid=f"v{ts}";STATE["assets"][aid]=final_out
        return jsonify(ok=True,id=aid,url=f"/media/asset/{aid}?v={ts}",name=final_out.name,duration=wav_duration(final_out),speed=speed)
    except Exception as e:
        log=APP_DIR/"voice_error.log"; log.write_text(traceback.format_exc(),encoding="utf-8")
        return jsonify(ok=False,error=f"{type(e).__name__}: {e}",log=str(log))

def atempo_chain(speed):
    speed=max(.25,min(4,float(speed)));parts=[];x=speed
    while x>2:parts.append("atempo=2");x/=2
    while x<.5:parts.append("atempo=.5");x/=.5
    parts.append(f"atempo={x:.6f}");return ",".join(parts)


def _font_path():
    cands=[
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for p in cands:
        if Path(p).exists(): return p
    return None

def make_text_png(text, width, height, font_size=56, color="#ffffff", bg="#00000000",
                  x=0.5, y=0.85, padding=18):
    canvas=Image.new("RGBA",(width,height),(0,0,0,0))
    draw=ImageDraw.Draw(canvas)
    fp=_font_path()
    font=ImageFont.truetype(fp,int(font_size)) if fp else ImageFont.load_default()
    bbox=draw.multiline_textbbox((0,0),text,font=font,align="center",spacing=6)
    tw=max(1,bbox[2]-bbox[0]); th=max(1,bbox[3]-bbox[1])
    px=int(max(0,min(width-tw, x*width-tw/2)))
    py=int(max(0,min(height-th, y*height-th/2)))
    if bg and len(bg)>=7 and bg.lower() not in ("transparent","#00000000"):
        # support #RRGGBB or #RRGGBBAA
        hx=bg.lstrip("#")
        if len(hx)==6: hx += "B3"
        try:
            rgba=tuple(int(hx[i:i+2],16) for i in (0,2,4,6))
            draw.rounded_rectangle((px-padding,py-padding,px+tw+padding,py+th+padding),radius=14,fill=rgba)
        except: pass
    draw.multiline_text((px,py),text,font=font,fill=color,align="center",spacing=6,
                        stroke_width=max(1,int(font_size*0.035)),stroke_fill="#000000")
    return canvas


def check_ffmpeg():
    try:
        if not FFMPEG or not Path(FFMPEG).exists():
            return False, f"Không tìm thấy FFmpeg: {FFMPEG}"
        cp=subprocess.run([FFMPEG,"-version"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          text=True,encoding="utf-8",errors="ignore",
                          timeout=20,creationflags=hidden_flags())
        first=(cp.stdout or cp.stderr or "").splitlines()
        return cp.returncode==0, (first[0] if first else "FFmpeg không trả thông tin")
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def render_project(project,src,out,meta,progress_cb=None):
    ok_ff, ff_info = check_ffmpeg()
    if not ok_ff: raise RuntimeError("FFmpeg lỗi: "+ff_info)
    clips=project.get("clips") or []
    if not clips:raise RuntimeError("Timeline không có clip.")
    ratio=project.get("ratio","9:16")
    sw,sh=int(meta["width"]),int(meta["height"])
    sar=sw/max(1,sh)
    target_ar={"9:16":9/16,"4:5":4/5,"1:1":1.0,"16:9":16/9}.get(ratio,sar)
    if ratio=="original" or abs(sar-target_ar)<0.015:
        tw,th=sw,sh
    else:
        sizes={"9:16":(720,1280),"4:5":(720,900),"1:1":(720,720),"16:9":(1280,720)}
        tw,th=sizes.get(ratio,(sw,sh))
    total=sum((float(c["end"])-float(c["start"]))/max(.25,float(c.get("speed",1))) for c in clips)
    fc=[];vs=[];als=[];has_audio=bool(meta.get("has_audio"))
    for i,c in enumerate(clips):
        s=float(c["start"]);e=float(c["end"]);sp=max(.25,float(c.get("speed",1)))
        vf=[f"trim=start={s}:end={e}",f"setpts=(PTS-STARTPTS)/{sp}"]
        if c.get("flipH"):vf.append("hflip")
        if c.get("flipV"):vf.append("vflip")
        rot=float(c.get("rotate",0))
        if abs(rot)>.01:vf.append(f"rotate={rot}*PI/180:ow=rotw(iw):oh=roth(ih):c=black")
        z=max(.5,min(3,float(c.get("zoom",1))))
        if z>1.001:vf.append(f"scale=iw*{z}:ih*{z},crop=iw/{z}:ih/{z}")
        if project.get("fit","contain")=="cover":vf.append(f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}")
        else:vf.append(f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:black")
        fc.append(f"[0:v]{','.join(vf)}[v{i}]");vs.append(f"[v{i}]")
        if has_audio:
            vol=0 if c.get("mute") else float(c.get("volume",100))/100
            fc.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS,{atempo_chain(sp)},volume={vol}[a{i}]");als.append(f"[a{i}]")
    fc.append("".join(vs)+f"concat=n={len(clips)}:v=1:a=0[vcat]")
    if has_audio:fc.append("".join(als)+f"concat=n={len(clips)}:v=0:a=1[abase]")
    else:fc.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={total}[abase]")

    cmd=[FFMPEG,"-y","-hide_banner","-loglevel","error","-nostdin","-i",str(src)]
    input_idx=1;audio_layers=[];text_layers=[]
    for li,L in enumerate(project.get("layers",[])):
        if L.get("enabled",True) is False:continue
        if L.get("type") in ("audio","voice") and L.get("assetId") in STATE["assets"]:
            cmd += ["-i",str(STATE["assets"][L["assetId"]])];audio_layers.append((input_idx,L));input_idx+=1
        elif L.get("type")=="text" and (L.get("text") or L.get("name")):
            png=make_text_png(L.get("text") or L.get("name"),tw,th,li)
            if png:
                cmd += ["-loop","1","-i",str(png)];text_layers.append((input_idx,L));input_idx+=1

    vcur='vcat'
    for k,(ii,L) in enumerate(text_layers):
        st=max(0,float(L.get("start",0)));en=max(st+.05,min(total,float(L.get("end",total))))
        nxt=f"vtxt{k}"
        fc.append(f"[{vcur}][{ii}:v]overlay=(W-w)/2:H-h-90:enable='between(t,{st},{en})':shortest=1[{nxt}]")
        vcur=nxt


    mix_labels=["[abase]"]
    for j,(ii,L) in enumerate(audio_layers):
        st=max(0,float(L.get("start",0)));en=float(L.get("end",total));dur=max(.05,en-st);vol=float(L.get("volume",100))/100;delay=int(st*1000)
        fc.append(f"[{ii}:a]atrim=0:{dur},asetpts=PTS-STARTPTS,volume={vol},adelay={delay}|{delay}[lay{j}]");mix_labels.append(f"[lay{j}]")
    if len(mix_labels)>1:fc.append("".join(mix_labels)+f"amix=inputs={len(mix_labels)}:duration=longest:dropout_transition=0,atrim=duration={total}[aout]")
    else:fc.append("[abase]anull[aout]")

    cmd += ["-filter_complex",";".join(fc),"-map",f"[{vcur}]","-map","[aout]",
            "-c:v","libx264","-preset","ultrafast","-crf","22","-pix_fmt","yuv420p",
            "-c:a","aac","-b:a","160k","-movflags","+faststart",
            "-progress","pipe:1","-nostats",str(out)]
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                          encoding="utf-8",errors="ignore",creationflags=hidden_flags(),bufsize=1)
    last_pct=0.0
    for line in proc.stdout:
        line=line.strip()
        if line.startswith("out_time_ms="):
            try:
                sec=int(line.split("=",1)[1] or 0)/1_000_000.0
                pct=max(0.0,min(99.0,sec/max(total,0.01)*100.0))
                if pct>=last_pct+0.5:
                    last_pct=pct
                    if progress_cb: progress_cb(pct)
            except: pass
        elif line=="progress=end":
            if progress_cb: progress_cb(100.0)
    rc=proc.wait()
    stderr=proc.stderr.read() if proc.stderr else ""
    if rc!=0:
        debug=APP_DIR/"ffmpeg_export_debug.txt"
        try:
            debug.write_text(
                "FFMPEG="+str(FFMPEG)+"\n\nFILTER_COMPLEX:\n"+";".join(fc)+
                "\n\nCOMMAND:\n"+" ".join(map(str,cmd))+"\n\nSTDERR:\n"+stderr,
                encoding="utf-8"
            )
        except: pass
        raise RuntimeError((stderr[-5000:] if stderr else "FFmpeg export lỗi.") + f"\nDebug: {debug}")


@app.route("/api/check_ffmpeg", methods=["GET"])
def api_check_ffmpeg():
    ok,info=check_ffmpeg()
    return jsonify(ok=ok, info=info, path=str(FFMPEG))



@app.route("/download_export/<job_id>")
def download_export(job_id):
    job=EXPORT_JOBS.get(job_id)
    if not job or job.get("status")!="done":
        return ("Export chưa sẵn sàng",404)
    p=Path(job.get("path",""))
    if not p.exists():
        return ("Không tìm thấy file export",404)
    return send_file(p,as_attachment=True,download_name=p.name)

def _run_export_job(job_id, project, src, out, meta):
    job=EXPORT_JOBS[job_id]
    try:
        job["status"]="running"; job["progress"]=1.0
        render_project(project,src,out,meta,progress_cb=lambda p: job.update(progress=round(float(p),1)))
        job["progress"]=100.0; job["status"]="done"; job["path"]=str(out)
    except Exception as e:
        log=APP_DIR/"render_error.log"
        try: log.write_text(traceback.format_exc(),encoding="utf-8")
        except: pass
        job["status"]="error"; job["error"]=f"{type(e).__name__}: {e}"; job["log"]=str(log)

@app.route("/api/export",methods=["POST"])
def api_export():
    try:
        if not STATE.get("video"):
            return jsonify(ok=False,error="Chưa chọn video.")
        project=request.get_json(force=True) or {}
        src=Path(STATE["video"])
        stamp=time.strftime("%Y%m%d_%H%M%S")
        out=EXPORT_DIR / f"{src.stem}_EDIT_{stamp}.mp4"
        job_id=f"ex{int(time.time()*1000)}"
        EXPORT_JOBS[job_id]={
            "status":"queued",
            "progress":0.0,
            "path":str(out),
            "error":"",
            "download_url":f"/download_export/{job_id}"
        }
        threading.Thread(
            target=_run_export_job,
            args=(job_id,project,src,out,dict(STATE["meta"])),
            daemon=True
        ).start()
        return jsonify(ok=True,job_id=job_id)
    except Exception as e:
        log=APP_DIR/"render_error.log"
        try: log.write_text(traceback.format_exc(),encoding="utf-8")
        except: pass
        return jsonify(ok=False,error=f"{type(e).__name__}: {e}",log=str(log))

@app.route("/api/export_status/<job_id>",methods=["GET"])
def api_export_status(job_id):
    job=EXPORT_JOBS.get(job_id)
    if not job:return jsonify(ok=False,error="Không tìm thấy job export.")
    return jsonify(ok=True,**job)

def find_free_port():
    s=socket.socket();s.bind(("127.0.0.1",0));port=s.getsockname()[1];s.close();return port

def main():
    port=find_free_port()
    url=f"http://127.0.0.1:{port}/"
    def opener():
        time.sleep(0.8)
        webbrowser.open(url,new=1)
    threading.Thread(target=opener,daemon=True).start()
    print("="*62)
    print("AUTO REVIEW VIDEO V4.9.3.1 - BROWSER EDITOR")
    print("Editor:",url)
    print("Dong cua so nay de tat backend.")
    print("="*62)
    serve(app,host="127.0.0.1",port=port,threads=8)

if __name__=="__main__":
    main()
