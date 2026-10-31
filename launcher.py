import os, sys, json, copy, threading, subprocess, time
from pathlib import Path
import app as core

APP_DIR = Path(__file__).resolve().parent
PATCH_JS = APP_DIR / 'static' / 'patch_v495.js'
VOICE_DAEMON = APP_DIR / 'voice_daemon.py'

_voice_proc = None
_voice_lock = threading.Lock()


def _voice_env():
    env=os.environ.copy()
    cache=core.AI_DATA/'cache'; hf=cache/'huggingface'
    for p in [cache,hf,hf/'hub',cache/'torch',core.AI_DATA/'temp']:
        p.mkdir(parents=True,exist_ok=True)
    env['HF_HOME']=str(hf); env['HF_HUB_CACHE']=str(hf/'hub'); env['HUGGINGFACE_HUB_CACHE']=str(hf/'hub')
    env['TORCH_HOME']=str(cache/'torch'); env['XDG_CACHE_HOME']=str(cache); env['PIP_CACHE_DIR']=str(cache/'pip')
    env['TEMP']=str(core.AI_DATA/'temp'); env['TMP']=str(core.AI_DATA/'temp'); env['PYTHONNOUSERSITE']='1'; env['PYTHONUTF8']='1'
    return env


def _ensure_voice_daemon():
    global _voice_proc
    if _voice_proc and _voice_proc.poll() is None:
        return _voice_proc
    if not core.VOICE_PYTHON.exists():
        raise RuntimeError('VieNeu chưa được cài. Hãy chạy INSTALL_AND_RUN.bat một lần.')
    _voice_proc=subprocess.Popen(
        [str(core.VOICE_PYTHON),str(VOICE_DAEMON)],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        text=True,encoding='utf-8',errors='ignore',bufsize=1,
        creationflags=core.hidden_flags(),env=_voice_env()
    )
    return _voice_proc


def voice_call_fast(args, timeout=1200):
    # Compatible with app.py's existing voice_call signature.
    if not args: raise RuntimeError('Thiếu lệnh VieNeu.')
    if args[0]=='list':
        req={'cmd':'list','mode':args[1] if len(args)>1 else 'v3turbo'}
    elif args[0]=='synth':
        data=json.loads(Path(args[1]).read_text(encoding='utf-8'))
        req={'cmd':'synth','request':data}
    else:
        raise RuntimeError('Lệnh VieNeu không hợp lệ.')
    with _voice_lock:
        for attempt in range(2):
            p=_ensure_voice_daemon()
            try:
                p.stdin.write(json.dumps(req,ensure_ascii=False)+'\n'); p.stdin.flush()
                line=p.stdout.readline()
                if not line: raise RuntimeError('VieNeu daemon không trả kết quả.')
                ans=json.loads(line)
                if not ans.get('ok'): raise RuntimeError(ans.get('error','VieNeu lỗi.'))
                return ans
            except Exception:
                global _voice_proc
                try:p.kill()
                except:pass
                _voice_proc=None
                if attempt: raise


# Keep VieNeu loaded between requests. First generation still loads the model;
# subsequent generations are much faster because the same Vieneu instance is reused.
core.voice_call = voice_call_fast


_orig_render = core.render_project

def render_project_with_audio_speed(project,src,out,meta,progress_cb=None):
    proj=copy.deepcopy(project)
    created=[]
    for i,L in enumerate(proj.get('layers',[])):
        if L.get('type') not in ('audio','voice') or L.get('enabled',True) is False:
            continue
        speed=max(.25,min(4.0,float(L.get('speed',1.0) or 1.0)))
        if abs(speed-1.0)<.001: continue
        aid=L.get('assetId'); original=core.STATE['assets'].get(aid)
        if not original or not Path(original).exists(): continue
        nid=f'spd_{int(time.time()*1000)}_{i}'
        dst=core.GEN/f'{nid}.wav'
        cp=subprocess.run([core.FFMPEG,'-y','-hide_banner','-loglevel','error','-i',str(original),
                           '-filter:a',core.atempo_chain(speed),str(dst)],
                          stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='ignore',
                          creationflags=core.hidden_flags())
        if cp.returncode!=0:
            raise RuntimeError(cp.stderr[-1800:] or 'Không chỉnh được tốc độ Audio/Voice.')
        core.STATE['assets'][nid]=dst; L['assetId']=nid; created.append((nid,dst))
    try:
        return _orig_render(proj,src,out,meta,progress_cb=progress_cb)
    finally:
        # Files are small temporary render assets; clean them after export.
        for nid,dst in created:
            core.STATE['assets'].pop(nid,None)
            try:dst.unlink()
            except:pass

core.render_project = render_project_with_audio_speed


# Inject the additive UI patch without rewriting the large stable index.html.
def patched_index():
    html=(core.STATIC/'index.html').read_text(encoding='utf-8')
    tag='<script src="/patch_v495.js?v=495"></script>'
    return html.replace('</body>',tag+'</body>')
core.app.view_functions['index']=patched_index


@core.app.route('/api/update_app',methods=['POST'])
def update_app():
    if os.name!='nt':
        return core.jsonify(ok=False,error='Nút Update trong app chỉ dùng cho bản Windows.')
    bat=APP_DIR/'UPDATE.bat'
    if not bat.exists():
        return core.jsonify(ok=False,error='Không tìm thấy UPDATE.bat trong thư mục tool.')
    subprocess.Popen(['cmd','/c','start','',str(bat)],cwd=APP_DIR,creationflags=core.hidden_flags())
    def quit_soon():
        time.sleep(1.2)
        os._exit(0)
    threading.Thread(target=quit_soon,daemon=True).start()
    return core.jsonify(ok=True)


if __name__=='__main__':
    core.main()
