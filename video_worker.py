import sys, json, traceback, subprocess, os, re
import imageio_ffmpeg
from pathlib import Path


def write(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')


def _hidden_flags():
    return 0x08000000 if os.name=='nt' else 0


def probe(path):
    """Read basic video metadata with FFmpeg only.

    Opening/previewing a video must not depend on OpenCV. OpenCV is loaded lazily
    only by analyze(), so Codespaces can still open and play video even if the
    OpenCV analysis environment has a problem.
    """
    ff=imageio_ffmpeg.get_ffmpeg_exe()
    cp=subprocess.run(
        [ff,'-hide_banner','-i',str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, encoding='utf-8', errors='ignore',
        timeout=15, creationflags=_hidden_flags()
    )
    txt=cp.stderr or ''

    md=re.search(r'Duration:\s*(\d+):(\d+):([\d.]+)',txt)
    if not md:
        raise RuntimeError('FFmpeg không đọc được thời lượng video.')
    dur=int(md.group(1))*3600+int(md.group(2))*60+float(md.group(3))

    # Restrict dimension/fps search to the first video stream line.
    video_line=''
    for line in txt.splitlines():
        if ' Video: ' in line:
            video_line=line
            break
    if not video_line:
        raise RuntimeError('FFmpeg không tìm thấy luồng video.')

    dims=re.findall(r'(?<!\d)(\d{2,5})x(\d{2,5})(?!\d)',video_line)
    if not dims:
        raise RuntimeError('FFmpeg không đọc được kích thước video.')
    # Codec/profile numbers can appear earlier, so prefer a plausible image size.
    w=h=0
    for a,b in dims:
        aa,bb=int(a),int(b)
        if aa>=64 and bb>=64:
            w,h=aa,bb
            break
    if w<=0 or h<=0:
        w,h=map(int,dims[-1])

    mfps=re.search(r'([\d.]+)\s*fps\b',video_line)
    fps=float(mfps.group(1)) if mfps else 30.0
    if fps<=0 or fps>240:
        fps=30.0

    has_audio=' Audio: ' in txt
    if dur<=0 or w<=0 or h<=0:
        raise RuntimeError('Không đọc được metadata hợp lệ.')
    return {'duration':dur,'width':w,'height':h,'fps':fps,'has_audio':has_audio}


def runs(mask, min_count=1):
    out=[]; s=None
    for i,v in enumerate(mask):
        if v and s is None:s=i
        if (not v or i==len(mask)-1) and s is not None:
            e=i if not v else i+1
            if e-s>=min_count: out.append((s,e))
            s=None
    return out


def analyze(path,strength,target):
    # OpenCV/Numpy are needed only for Auto Cut, not for opening/previewing.
    try:
        import cv2
        import numpy as np
    except Exception as e:
        raise RuntimeError(
            'Auto Cut cần OpenCV nhưng môi trường hiện tại chưa tải được OpenCV. '
            'Video vẫn có thể mở và preview bình thường. Chi tiết: '+str(e)
        )
    try:
        cv2.setNumThreads(1)
    except Exception:
        pass

    meta=probe(path); dur=meta['duration']; srcfps=meta['fps']
    sample_fps=4.0 if dur<240 else 3.0
    every=max(1,int(round(srcfps/sample_fps)))
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened(): raise RuntimeError('Không mở được video để phân tích.')
    face=None
    try:
        face=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    except Exception: face=None
    rows=[]; prev=None; fi=0; si=0
    while True:
        ok=cap.grab()
        if not ok: break
        if fi%every==0:
            ok,fr=cap.retrieve()
            if not ok: break
            sm=cv2.resize(fr,(160,90),interpolation=cv2.INTER_AREA)
            gray=cv2.cvtColor(sm,cv2.COLOR_BGR2GRAY)
            bright=float(gray.mean()); sharp=float(cv2.Laplacian(gray,cv2.CV_64F).var())
            motion=0.0 if prev is None else float(cv2.absdiff(gray,prev).mean())
            prev=gray
            hsv=cv2.cvtColor(sm,cv2.COLOR_BGR2HSV)
            hist=cv2.calcHist([hsv],[0],None,[16],[0,180]); cv2.normalize(hist,hist)
            novelty=0.0
            if rows:
                novelty=float(cv2.compareHist(rows[-1]['hist'],hist,cv2.HISTCMP_BHATTACHARYYA))
            fc=0
            if face is not None and si%3==0:
                try: fc=len(face.detectMultiScale(gray,1.18,4,minSize=(18,18)))
                except Exception: fc=0
            rows.append({'t':fi/srcfps,'bright':bright,'sharp':sharp,'motion':motion,'novelty':novelty,'face':fc,'hist':hist})
            si+=1
        fi+=1
    cap.release()
    if len(rows)<4: return [(0,dur)],[],{'duration':dur,'kept':dur,'samples':len(rows)}
    mot=np.array([r['motion'] for r in rows],float); shp=np.array([r['sharp'] for r in rows],float); bri=np.array([r['bright'] for r in rows],float); nov=np.array([r['novelty'] for r in rows],float)
    def norm(x,lo=10,hi=90):
        a,b=np.percentile(x,[lo,hi])
        if b<=a+1e-6:return np.zeros_like(x)
        return np.clip((x-a)/(b-a),0,1)
    nm=norm(mot,10,90); ns=norm(shp,10,90); nn=norm(nov,20,90)
    bright_good=np.clip(1-np.abs(bri-145)/125,0,1)
    face_bonus=np.array([0.10 if r['face']>0 else 0 for r in rows])
    sharp_floor=np.percentile(shp,8 if strength>=3 else 5)
    severe=(bri<18)|(bri>246)|(shp<max(6,sharp_floor*0.75))
    pct={1:18,2:27,3:36}.get(int(strength),27)
    low_thr=max(1.5,float(np.percentile(mot[1:],pct)))
    low=mot<low_thr
    idle=np.zeros(len(rows),dtype=bool)
    min_idle=max(3,int(round(sample_fps*({1:1.6,2:1.25,3:0.9}[int(strength)]))))
    for s,e in runs(low,min_idle): idle[s:e]=True
    score=0.42*nm+0.23*ns+0.16*nn+0.19*bright_good+face_bonus
    score[severe]-=1.25
    score[idle]-={1:0.35,2:0.65,3:0.95}[int(strength)]
    clip_len={1:3.0,2:2.6,3:2.25}[int(strength)]
    win=max(4,int(round(clip_len*sample_fps)))
    candidates=[]
    for i in range(0,len(rows)-win+1):
        j=i+win
        bad=float(np.mean(severe[i:j])); wait=float(np.mean(idle[i:j]))
        if bad>0.22 or wait>({1:.65,2:.48,3:.34}[int(strength)]): continue
        sc=float(np.mean(score[i:j]) - 0.8*wait - 1.2*bad)
        candidates.append((sc,i,j))
    candidates.sort(reverse=True,key=lambda x:x[0])
    chosen=[]; need=max(1,int(np.ceil(float(target)/clip_len)))
    for sc,i,j in candidates:
        st=rows[i]['t']; en=min(dur,rows[j-1]['t']+1/sample_fps)
        if any(not (en<=a-0.30 or st>=b+0.30) for a,b in chosen): continue
        chosen.append((st,en))
        if len(chosen)>=need: break
    if not chosen: chosen=[(0,min(dur,float(target)))]
    chosen=sorted(chosen)
    merged=[]
    for s,e in chosen:
        if merged and s-merged[-1][1]<0.18: merged[-1]=(merged[-1][0],e)
        else: merged.append((s,e))
    total=sum(e-s for s,e in merged)
    if total>target*1.10:
        trimmed=[]; remain=float(target)
        for s,e in merged:
            if remain<=0:break
            ln=min(e-s,remain); trimmed.append((s,s+ln)); remain-=ln
        merged=trimmed
    drops=[]; cur=0.0
    for s,e in merged:
        if s-cur>0.12:drops.append((cur,s))
        cur=e
    if dur-cur>0.12:drops.append((cur,dur))
    kept=sum(e-s for s,e in merged)
    return merged,drops,{'duration':dur,'kept':kept,'dropped':dur-kept,'samples':len(rows),'low_motion_threshold':low_thr,'idle_seconds':float(np.sum(idle)/sample_fps)}


def main():
    if len(sys.argv)<4: raise SystemExit(2)
    mode=sys.argv[1]; src=sys.argv[2]; out=sys.argv[-1]
    try:
        if mode=='probe': obj={'ok':True,'meta':probe(src)}
        elif mode=='analyze':
            strength=int(sys.argv[3]); target=int(sys.argv[4]); keep,drop,stats=analyze(src,strength,target); obj={'ok':True,'keep':keep,'drop':drop,'stats':stats}
        else: raise RuntimeError('Mode worker không hợp lệ.')
    except Exception as e:
        obj={'ok':False,'error':f'{type(e).__name__}: {e}\n{traceback.format_exc()}'}
    write(out,obj)


if __name__=='__main__': main()
