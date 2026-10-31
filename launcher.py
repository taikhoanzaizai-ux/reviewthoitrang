import os, sys, json, copy, threading, subprocess, time
from pathlib import Path
import app as core

APP_DIR = Path(__file__).resolve().parent
VOICE_DAEMON = APP_DIR / 'voice_daemon.py'
SETTINGS_FILE = APP_DIR / 'data' / 'settings.json'

_voice_proc = None
_voice_lock = threading.Lock()


def _load_settings():
    try:
        data=json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data,dict) else {}
    except Exception:
        return {}


def _save_settings(data):
    SETTINGS_FILE.parent.mkdir(parents=True,exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def _apply_saved_export_dir():
    s=_load_settings(); p=s.get('export_dir')
    if p:
        pp=Path(p)
        try: pp.mkdir(parents=True,exist_ok=True); core.EXPORT_DIR=pp
        except Exception: pass

_apply_saved_export_dir()


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
    if not args: raise RuntimeError('Thiếu lệnh VieNeu.')
    if args[0]=='list':
        req={'cmd':'list','mode':args[1] if len(args)>1 else 'v3turbo'}
    elif args[0]=='synth':
        data=json.loads(Path(args[1]).read_text(encoding='utf-8'))
        req={'cmd':'synth','request':data}
    else:
        raise RuntimeError('Lệnh VieNeu không hợp lệ.')
    global _voice_proc
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
                try:p.kill()
                except:pass
                _voice_proc=None
                if attempt: raise


core.voice_call = voice_call_fast


_orig_render = core.render_project

def render_project_with_audio_speed(project,src,out,meta,progress_cb=None):
    proj=copy.deepcopy(project)
    created=[]
    for i,L in enumerate(proj.get('layers',[])):
        if L.get('type') not in ('audio','voice') or L.get('enabled',True) is False:
            continue
        speed=max(.25,min(4.0,float(L.get('speed',1.0) or 1.0)))
        offset=max(0.0,float(L.get('sourceOffset',0.0) or 0.0))
        aid=L.get('assetId'); original=core.STATE['assets'].get(aid)
        if not original or not Path(original).exists(): continue
        if abs(speed-1.0)<.001 and offset<.001: continue
        nid=f'spd_{int(time.time()*1000)}_{i}'
        dst=core.GEN/f'{nid}.wav'
        timeline_dur=max(.05,float(L.get('end',0))-float(L.get('start',0)))
        source_dur=max(.05,timeline_dur*speed)
        cmd=[core.FFMPEG,'-y','-hide_banner','-loglevel','error']
        if offset>0: cmd += ['-ss',f'{offset:.6f}']
        cmd += ['-i',str(original),'-t',f'{source_dur:.6f}']
        if abs(speed-1.0)>=.001: cmd += ['-filter:a',core.atempo_chain(speed)]
        cmd += [str(dst)]
        cp=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='ignore',creationflags=core.hidden_flags())
        if cp.returncode!=0:
            raise RuntimeError(cp.stderr[-1800:] or 'Không xử lý được tốc độ/điểm cắt Audio/Voice.')
        core.STATE['assets'][nid]=dst; L['assetId']=nid; L['sourceOffset']=0; L['speed']=1; created.append((nid,dst))
    try:
        return _orig_render(proj,src,out,meta,progress_cb=progress_cb)
    finally:
        for nid,dst in created:
            core.STATE['assets'].pop(nid,None)
            try:dst.unlink()
            except:pass

core.render_project = render_project_with_audio_speed


# Inject additive UI patches without rewriting the stable index.html.
def patched_index():
    html=(core.STATIC/'index.html').read_text(encoding='utf-8')
    tags='<script src="/patch_v495.js?v=495"></script><script src="/patch_v496.js?v=496"></script><script src="/patch_v497.js?v=497"></script>'
    return html.replace('</body>',tags+'</body>')
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
        time.sleep(1.2); os._exit(0)
    threading.Thread(target=quit_soon,daemon=True).start()
    return core.jsonify(ok=True)


@core.app.route('/api/extract_video_audio',methods=['POST'])
def extract_video_audio():
    try:
        src=core.STATE.get('video')
        if not src or not Path(src).exists(): return core.jsonify(ok=False,error='Chưa chọn video.')
        ts=int(time.time()*1000); out=core.GEN/f'video_audio_{ts}.m4a'
        cp=subprocess.run([core.FFMPEG,'-y','-hide_banner','-loglevel','error','-i',str(src),'-vn','-c:a','aac','-b:a','192k',str(out)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='ignore',creationflags=core.hidden_flags())
        if cp.returncode!=0: raise RuntimeError(cp.stderr[-2200:] or 'Không tách được audio khỏi video.')
        aid=f'va{ts}'; core.STATE['assets'][aid]=out
        dur=float((core.STATE.get('meta') or {}).get('duration',0) or 0)
        return core.jsonify(ok=True,id=aid,url=f'/media/asset/{aid}',name='Audio gốc video',duration=dur)
    except Exception as e:
        return core.jsonify(ok=False,error=f'{type(e).__name__}: {e}')


def _pick_folder_windows(initial=''):
    if os.name!='nt': return None
    ps=core.shutil.which('powershell') or core.shutil.which('pwsh')
    if not ps: raise RuntimeError('Không tìm thấy PowerShell.')
    init=(initial or '').replace("'","''")
    script="Add-Type -AssemblyName System.Windows.Forms\n$d=New-Object System.Windows.Forms.FolderBrowserDialog\n$d.Description='Chọn thư mục lưu video xuất'\n"
    if init: script += f"$d.SelectedPath='{init}'\n"
    script += "$r=$d.ShowDialog()\nif($r -eq [System.Windows.Forms.DialogResult]::OK){Write-Output $d.SelectedPath}\n"
    cp=subprocess.run([ps,'-NoProfile','-STA','-Command',script],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='ignore',creationflags=core.hidden_flags())
    if cp.returncode!=0: raise RuntimeError(cp.stderr.strip() or 'Không mở được hộp thoại chọn thư mục.')
    lines=[x.strip() for x in cp.stdout.splitlines() if x.strip()]
    return lines[-1] if lines else None


@core.app.route('/api/export_folder',methods=['GET','POST'])
def export_folder():
    try:
        settings=_load_settings(); current=settings.get('export_dir') or str(core.EXPORT_DIR)
        if core.request.method=='GET': return core.jsonify(ok=True,path=current)
        if os.name!='nt': return core.jsonify(ok=False,error='Chọn thư mục trực tiếp chỉ hỗ trợ Windows.')
        chosen=_pick_folder_windows(current)
        if not chosen:return core.jsonify(ok=False,cancelled=True,path=current)
        p=Path(chosen);p.mkdir(parents=True,exist_ok=True);settings['export_dir']=str(p);_save_settings(settings);core.EXPORT_DIR=p
        return core.jsonify(ok=True,path=str(p))
    except Exception as e:
        return core.jsonify(ok=False,error=f'{type(e).__name__}: {e}')


if __name__=='__main__':
    core.main()
