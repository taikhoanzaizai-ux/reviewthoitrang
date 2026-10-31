import sys, json, traceback, subprocess, os, re
from pathlib import Path
import imageio_ffmpeg


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
    return {'duration':dur,'width':w,'height':h,'fps':fps,'has_audio':' Audio: ' in txt}


def runs(mask,min_count=1):
    out=[];s=None
    for i,v in enumerate(mask):
        if v and s is None:s=i
        if (not v or i==len(mask)-1) and s is not None:
            e=i if not v else i+1
            if e-s>=min_count:out.append((s,e))
            s=None
    return out


def _norm(np,x,lo=8,hi=92):
    a,b=np.percentile(x,[lo,hi])
    if b<=a+1e-6:return np.zeros_like(x,dtype=float)
    return np.clip((x-a)/(b-a),0,1)


def analyze(path,strength,target):
    try:
        import cv2
        import numpy as np
    except Exception as e:
        raise RuntimeError('Auto Cut cần OpenCV. Chi tiết: '+str(e))
    try: cv2.setNumThreads(1)
    except: pass

    strength=max(1,min(3,int(strength)))
    target=max(5.0,float(target))
    meta=probe(path);dur=meta['duration'];srcfps=meta['fps']
    sample_fps=5.0 if dur<240 else 4.0
    every=max(1,int(round(srcfps/sample_fps)))
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened(): raise RuntimeError('Không mở được video để phân tích.')

    rows=[];prev=None;fi=0
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
            rows.append((fi/srcfps,bright,sharp,motion))
        fi+=1
    cap.release()
    if len(rows)<8:return [(0,min(dur,target))],[],{'duration':dur,'kept':min(dur,target),'samples':len(rows)}

    t=np.array([r[0] for r in rows]);bri=np.array([r[1] for r in rows]);shp=np.array([r[2] for r in rows]);mot=np.array([r[3] for r in rows])
    if len(mot)>=3: mot=np.convolve(mot,np.ones(3)/3,mode='same')
    if len(shp)>=3: shp=np.convolve(shp,np.ones(3)/3,mode='same')

    sharp_floor=max(4.0,float(np.percentile(shp,6)))
    severe=(bri<15)|(bri>249)|(shp<sharp_floor*.58)
    low_thr=max(1.0,float(np.percentile(mot[1:],{1:10,2:16,3:22}[strength])))
    low=mot<low_thr
    idle=np.zeros(len(rows),dtype=bool)
    min_idle=max(4,int(round(sample_fps*{1:2.0,2:1.55,3:1.20}[strength])))
    for s,e in runs(low,min_idle):idle[s:e]=True

    bad=severe|idle
    bridge=max(1,int(round(sample_fps*{1:.55,2:.42,3:.30}[strength])))
    for s,e in runs(bad,1):
        if e-s<=bridge and not np.any(severe[s:e]):bad[s:e]=False

    good=~bad
    min_good=max(3,int(round(sample_fps*{1:3.2,2:2.8,3:2.4}[strength])))
    regions=[]
    for s,e in runs(good,min_good):
        ss=max(0.0,t[s]-.18);ee=min(dur,t[e-1]+1/sample_fps+.18)
        if ee-ss>=2.3: regions.append((ss,ee))

    if not regions:
        return [(0,min(dur,target))],[(min(dur,target),dur)] if dur>target else [],{'duration':dur,'kept':min(dur,target),'samples':len(rows)}

    # Chia vùng tốt thành các clip review vừa phải.
    ideal={1:5.2,2:4.6,3:4.0}[strength]
    min_piece={1:3.4,2:3.0,3:2.7}[strength]
    max_piece={1:6.2,2:5.6,3:5.0}[strength]
    pieces=[]
    for rs,re in regions:
        cur=rs
        while re-cur>=min_piece:
            remain=re-cur
            ln=min(max_piece,ideal,remain)
            if remain-ln<min_piece*.65: ln=remain
            ln=min(ln,max_piece)
            pe=min(re,cur+ln)
            pieces.append((cur,pe))
            cur=pe
        if cur<re and pieces and re-pieces[-1][1]<=min_piece:
            ps,pe=pieces[-1]
            if re-ps<=max_piece+1.0: pieces[-1]=(ps,re)

    # Chấm điểm TẤT CẢ clip trên toàn bộ video, không ưu tiên clip đầu.
    sharp_n=_norm(np,shp,8,92)
    bright_good=np.clip(1-np.abs(bri-145)/130,0,1)
    motion_n=_norm(np,mot,12,88)
    shaky=mot>max(float(np.percentile(mot,98)),low_thr*8)
    quality=.46*sharp_n+.34*bright_good+.20*motion_n-.18*shaky
    quality[severe]-=1.5; quality[idle]-=.7

    scored=[]
    for s,e in pieces:
        i=int(np.searchsorted(t,s,'left')); j=int(np.searchsorted(t,e,'right'))
        i=max(0,min(len(t)-1,i)); j=max(i+1,min(len(t),j))
        q=float(np.mean(quality[i:j]))
        mid=(s+e)/2
        scored.append({'s':s,'e':e,'q':q,'mid':mid})

    # Trải lựa chọn trên toàn video: mỗi vùng thời gian lấy clip tốt nhất trước,
    # sau đó mới điền thêm các clip điểm cao toàn cục.
    wanted=max(1,int(round(target/max(3.0,ideal))))
    bins=max(1,min(wanted,8))
    selected=[];used=set()
    for bi in range(bins):
        bs=dur*bi/bins; be=dur*(bi+1)/bins
        cand=[(idx,p) for idx,p in enumerate(scored) if bs<=p['mid']<(be if bi<bins-1 else be+1e-6)]
        if not cand: continue
        idx,p=max(cand,key=lambda z:z[1]['q'])
        selected.append(p);used.add(idx)

    for idx,p in sorted(enumerate(scored),key=lambda z:z[1]['q'],reverse=True):
        if idx in used:continue
        if sum(x['e']-x['s'] for x in selected)>=target*1.03:break
        selected.append(p);used.add(idx)

    # Nếu mục tiêu ngắn, bỏ bớt clip điểm thấp nhất nhưng vẫn giữ độ phủ đầu-giữa-cuối.
    while len(selected)>1 and sum(x['e']-x['s'] for x in selected)>target*1.30:
        worst=min(range(len(selected)),key=lambda k:selected[k]['q'])
        trial=selected[:worst]+selected[worst+1:]
        if len(trial)>=max(1,min(3,bins)):
            selected=trial
        else:break

    final=sorted((p['s'],p['e']) for p in selected)
    if not final:final=[pieces[0]]

    drops=[];cur=0.0
    for s,e in final:
        if s-cur>.12:drops.append((cur,s))
        cur=e
    if dur-cur>.12:drops.append((cur,dur))
    kept=sum(e-s for s,e in final)
    return final,drops,{'duration':dur,'kept':kept,'dropped':dur-kept,'samples':len(rows),
                       'idle_seconds':float(np.sum(idle)/sample_fps),'segments':len(final),
                       'strategy':'best_clips_across_full_video'}


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
