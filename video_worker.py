import sys, json, traceback, subprocess, os, re
import imageio_ffmpeg
from pathlib import Path


def write(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')


def _hidden_flags():
    return 0x08000000 if os.name=='nt' else 0


def probe(path):
    ff=imageio_ffmpeg.get_ffmpeg_exe()
    cp=subprocess.run([ff,'-hide_banner','-i',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                      text=True,encoding='utf-8',errors='ignore',timeout=15,creationflags=_hidden_flags())
    txt=cp.stderr or ''
    md=re.search(r'Duration:\s*(\d+):(\d+):([\d.]+)',txt)
    if not md: raise RuntimeError('FFmpeg không đọc được thời lượng video.')
    dur=int(md.group(1))*3600+int(md.group(2))*60+float(md.group(3))
    video_line=next((x for x in txt.splitlines() if ' Video: ' in x),'')
    if not video_line: raise RuntimeError('FFmpeg không tìm thấy luồng video.')
    dims=re.findall(r'(?<!\d)(\d{2,5})x(\d{2,5})(?!\d)',video_line)
    if not dims: raise RuntimeError('FFmpeg không đọc được kích thước video.')
    w=h=0
    for a,b in dims:
        aa,bb=int(a),int(b)
        if aa>=64 and bb>=64: w,h=aa,bb; break
    if w<=0 or h<=0: w,h=map(int,dims[-1])
    mfps=re.search(r'([\d.]+)\s*fps\b',video_line)
    fps=float(mfps.group(1)) if mfps else 30.0
    if fps<=0 or fps>240: fps=30.0
    has_audio=' Audio: ' in txt
    return {'duration':dur,'width':w,'height':h,'fps':fps,'has_audio':has_audio}


def runs(mask,min_count=1):
    out=[];s=None
    for i,v in enumerate(mask):
        if v and s is None:s=i
        if (not v or i==len(mask)-1) and s is not None:
            e=i if not v else i+1
            if e-s>=min_count:out.append((s,e))
            s=None
    return out


def _smooth(np,x,n=3):
    if len(x)<n:return x.copy()
    k=np.ones(n,dtype=float)/n
    return np.convolve(x,k,mode='same')


def _best_window(np,quality,s,e,count):
    count=max(1,min(count,e-s))
    if e-s<=count:return s,e
    vals=np.convolve(quality[s:e],np.ones(count),mode='valid')
    k=int(np.argmax(vals))
    return s+k,s+k+count


def analyze(path,strength,target):
    try:
        import cv2
        import numpy as np
    except Exception as e:
        raise RuntimeError('Auto Cut cần OpenCV. Chi tiết: '+str(e))
    try:cv2.setNumThreads(1)
    except:pass

    strength=max(1,min(3,int(strength)))
    target=max(5,float(target))
    meta=probe(path);dur=meta['duration'];srcfps=meta['fps']
    sample_fps=5.0 if dur<180 else (4.0 if dur<600 else 3.0)
    every=max(1,int(round(srcfps/sample_fps)))
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():raise RuntimeError('Không mở được video để phân tích.')

    face=None
    try:face=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    except:pass
    rows=[];prev=None;fi=0;si=0
    while True:
        ok=cap.grab()
        if not ok:break
        if fi%every==0:
            ok,fr=cap.retrieve()
            if not ok:break
            sm=cv2.resize(fr,(192,108),interpolation=cv2.INTER_AREA)
            gray=cv2.cvtColor(sm,cv2.COLOR_BGR2GRAY)
            bright=float(gray.mean())
            sharp=float(cv2.Laplacian(gray,cv2.CV_64F).var())
            motion=0.0 if prev is None else float(cv2.absdiff(gray,prev).mean())
            prev=gray
            hsv=cv2.cvtColor(sm,cv2.COLOR_BGR2HSV)
            hist=cv2.calcHist([hsv],[0],None,[16],[0,180]);cv2.normalize(hist,hist)
            novelty=0.0 if not rows else float(cv2.compareHist(rows[-1]['hist'],hist,cv2.HISTCMP_BHATTACHARYYA))
            fc=0
            if face is not None and si%4==0:
                try:fc=len(face.detectMultiScale(gray,1.18,4,minSize=(22,22)))
                except:pass
            rows.append({'t':fi/srcfps,'bright':bright,'sharp':sharp,'motion':motion,'novelty':novelty,'face':fc,'hist':hist})
            si+=1
        fi+=1
    cap.release()
    if len(rows)<8:return [(0,min(dur,target))],[],{'duration':dur,'kept':min(dur,target),'samples':len(rows)}

    mot=np.array([r['motion'] for r in rows],float)
    shp=np.array([r['sharp'] for r in rows],float)
    bri=np.array([r['bright'] for r in rows],float)
    nov=np.array([r['novelty'] for r in rows],float)
    mot_s=_smooth(np,mot,3);shp_s=_smooth(np,shp,3)

    def norm(x,lo=10,hi=90):
        a,b=np.percentile(x,[lo,hi])
        if b<=a+1e-6:return np.zeros_like(x)
        return np.clip((x-a)/(b-a),0,1)

    nm=norm(mot_s,10,90);ns=norm(shp_s,8,92);nn=norm(nov,15,92)
    bright_good=np.clip(1-np.abs(bri-145)/130,0,1)
    face_bonus=np.array([0.08 if r['face']>0 else 0 for r in rows])

    sharp_floor=max(5.0,float(np.percentile(shp_s,7)))
    severe=(bri<16)|(bri>248)|(shp_s<sharp_floor*0.62)

    idle_pct={1:12,2:18,3:24}[strength]
    low_thr=max(1.15,float(np.percentile(mot_s[1:],idle_pct)))
    low=mot_s<low_thr
    idle=np.zeros(len(rows),dtype=bool)
    idle_sec={1:1.7,2:1.35,3:1.05}[strength]
    for s,e in runs(low,max(3,int(round(idle_sec*sample_fps)))):
        idle[s:e]=True

    # Do not punish normal movement. Only extremely shaky/high-motion samples get a mild penalty.
    hi_motion=float(np.percentile(mot_s,98))
    shaky=mot_s>max(hi_motion,low_thr*8)
    quality=0.34*ns+0.28*nm+0.18*bright_good+0.12*nn+face_bonus-0.12*shaky
    quality[severe]-=1.5
    quality[idle]-={1:.25,2:.45,3:.65}[strength]

    # Continuous-good segmentation: this is intentionally less aggressive than the old
    # fixed 2.25-3s window picker. Good takes stay together, so viewers have time to see them.
    good=(~severe)&(~idle)

    # Fill short harmless holes so one tiny pause does not create another cut.
    max_hole=max(1,int(round(sample_fps*{1:.85,2:.65,3:.45}[strength])))
    bad_runs=runs(~good,1)
    for s,e in bad_runs:
        if e-s<=max_hole and not np.any(severe[s:e]):good[s:e]=True

    # Remove tiny isolated good islands; they are usually accidental flashes between bad takes.
    min_good_sec={1:3.8,2:3.4,3:3.0}[strength]
    min_good=max(3,int(round(min_good_sec*sample_fps)))
    for s,e in runs(good,1):
        if e-s<min_good:good[s:e]=False

    regions=[]
    pad={1:.45,2:.35,3:.28}[strength]
    for s,e in runs(good,min_good):
        ss=max(0.0,rows[s]['t']-pad)
        ee=min(dur,rows[min(len(rows)-1,e-1)]['t']+1/sample_fps+pad)
        if ee-ss>=2.7:regions.append([ss,ee,s,e])

    # Merge nearby good regions to reduce preview seek hiccups and preserve context.
    merged=[];merge_gap={1:1.05,2:.82,3:.62}[strength]
    for r in regions:
        if merged and r[0]-merged[-1][1]<=merge_gap:
            merged[-1][1]=r[1];merged[-1][3]=r[3]
        else:merged.append(r[:])
    regions=merged

    if not regions:
        return [(0,min(dur,target))],[(min(dur,target),dur)] if dur>target else [],{'duration':dur,'kept':min(dur,target),'samples':len(rows),'idle_seconds':float(np.sum(idle)/sample_fps)}

    # Rank continuous takes, but keep them chronological in the final timeline.
    scored=[]
    for ss,ee,s,e in regions:
        q=float(np.mean(quality[s:e]))
        ln=ee-ss
        q+=min(0.22,ln/40.0)  # modest preference for a complete, longer take
        scored.append((q,ss,ee,s,e))
    scored.sort(key=lambda x:x[0],reverse=True)

    chosen=[];kept=0.0
    min_show={1:4.8,2:4.2,3:3.6}[strength]
    max_piece={1:10.0,2:8.5,3:7.5}[strength]
    max_clips=max(2,int(np.ceil(target/min_show))+1)
    for q,ss,ee,s,e in scored:
        if len(chosen)>=max_clips:break
        ln=ee-ss
        remain=target-kept
        if remain<=0 and kept>=target*.92:break
        want=min(ln,max_piece,max(min_show,remain+0.8 if remain>0 else min_show))
        if ln>want+.3:
            cnt=max(1,int(round(want*sample_fps)))
            bs,be=_best_window(np,quality,s,e,cnt)
            ss=max(0.0,rows[bs]['t']-.25)
            ee=min(dur,rows[min(len(rows)-1,be-1)]['t']+1/sample_fps+.25)
        if ee-ss<2.8:continue
        chosen.append((ss,ee));kept+=ee-ss
        if kept>=target*1.05:break

    chosen.sort()
    # One final merge keeps nearby shots together and reduces playback hiccups.
    final=[]
    for s,e in chosen:
        if final and s-final[-1][1]<.55:
            final[-1]=(final[-1][0],e)
        else:final.append((s,e))

    # Avoid cutting a correct shot to a tiny tail just to hit the target exactly.
    if sum(e-s for s,e in final)>target*1.35 and len(final)>1:
        while len(final)>1 and sum(e-s for s,e in final[:-1])>=target*.90:
            final.pop()

    drops=[];cur=0.0
    for s,e in final:
        if s-cur>.12:drops.append((cur,s))
        cur=e
    if dur-cur>.12:drops.append((cur,dur))
    kept=sum(e-s for s,e in final)
    return final,drops,{'duration':dur,'kept':kept,'dropped':dur-kept,'samples':len(rows),
                       'low_motion_threshold':low_thr,'idle_seconds':float(np.sum(idle)/sample_fps),
                       'segments':len(final),'strategy':'continuous_good_takes'}


def main():
    if len(sys.argv)<4:raise SystemExit(2)
    mode=sys.argv[1];src=sys.argv[2];out=sys.argv[-1]
    try:
        if mode=='probe':obj={'ok':True,'meta':probe(src)}
        elif mode=='analyze':
            strength=int(sys.argv[3]);target=int(sys.argv[4]);keep,drop,stats=analyze(src,strength,target);obj={'ok':True,'keep':keep,'drop':drop,'stats':stats}
        else:raise RuntimeError('Mode worker không hợp lệ.')
    except Exception as e:
        obj={'ok':False,'error':f'{type(e).__name__}: {e}\n{traceback.format_exc()}'}
    write(out,obj)

if __name__=='__main__':main()
