import sys, json, traceback, subprocess, os, re
import imageio_ffmpeg
from pathlib import Path


def write(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')


def _hidden_flags():
    return 0x08000000 if os.name=='nt' else 0


def probe(path):
    ff=imageio_ffmpeg.get_ffmpeg_exe()
    cp=subprocess.run([ff,'-hide_banner','-i',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='ignore',timeout=15,creationflags=_hidden_flags())
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
        if aa>=64 and bb>=64:w,h=aa,bb;break
    if w<=0 or h<=0:w,h=map(int,dims[-1])
    mfps=re.search(r'([\d.]+)\s*fps\b',video_line);fps=float(mfps.group(1)) if mfps else 30.0
    if fps<=0 or fps>240:fps=30.0
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


def _fill_short_false(mask,max_gap):
    mask=mask.copy();i=0;n=len(mask)
    while i<n:
        if mask[i]:i+=1;continue
        j=i
        while j<n and not mask[j]:j+=1
        if i>0 and j<n and j-i<=max_gap:mask[i:j]=True
        i=j
    return mask


def _remove_short_true(mask,min_len):
    mask=mask.copy()
    for s,e in runs(mask,1):
        if e-s<min_len:mask[s:e]=False
    return mask


def analyze(path,strength,target):
    try:
        import cv2
        import numpy as np
    except Exception as e:
        raise RuntimeError('Auto Cut cần OpenCV. Chi tiết: '+str(e))
    try:cv2.setNumThreads(1)
    except:pass

    strength=max(1,min(3,int(strength)));target=max(5,float(target))
    meta=probe(path);dur=meta['duration'];srcfps=meta['fps']
    sample_fps=5.0 if dur<240 else 4.0
    every=max(1,int(round(srcfps/sample_fps)))
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():raise RuntimeError('Không mở được video để phân tích.')

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
            jitter=0.0 if prev is None else float(cv2.absdiff(gray,prev).std())
            prev=gray
            rows.append({'t':fi/srcfps,'bright':bright,'sharp':sharp,'motion':motion,'jitter':jitter})
        fi+=1
    cap.release()
    if len(rows)<6:return [(0,dur)],[],{'duration':dur,'kept':dur,'samples':len(rows)}

    mot=np.array([r['motion'] for r in rows],float)
    shp=np.array([r['sharp'] for r in rows],float)
    bri=np.array([r['bright'] for r in rows],float)
    jit=np.array([r['jitter'] for r in rows],float)

    p10=float(np.percentile(shp,10));p20=float(np.percentile(shp,20))
    m20=float(np.percentile(mot[1:],20));m35=float(np.percentile(mot[1:],35));m95=float(np.percentile(mot[1:],95));j96=float(np.percentile(jit[1:],96))

    # Conservative: start from KEEP ALL and only remove sustained, confident failures.
    severe=(bri<13)|(bri>250)|(shp<max(4.0,p10*.55))
    soft_blur=shp<max(7.0,p20*.68)

    low_thr={1:max(.9,m20*.65),2:max(1.05,m20*.78),3:max(1.20,m35*.70)}[strength]
    idle=np.zeros(len(rows),dtype=bool)
    min_idle_sec={1:2.6,2:2.0,3:1.55}[strength]
    for s,e in runs(mot<low_thr,max(3,int(round(min_idle_sec*sample_fps)))):idle[s:e]=True

    shake=(mot>max(m95*1.30,11.0))&(jit>max(j96*.92,20.0))
    shake_bad=np.zeros(len(rows),dtype=bool)
    for s,e in runs(shake,max(2,int(round(.45*sample_fps)))):shake_bad[s:e]=True

    tech=np.zeros(len(rows),dtype=bool)
    tech_raw=severe | (soft_blur & shake_bad)
    for s,e in runs(tech_raw,max(2,int(round(.55*sample_fps)))):tech[s:e]=True

    bad=idle|tech|shake_bad
    pad=int(round({1:.08,2:.12,3:.18}[strength]*sample_fps))
    if pad:
        expanded=bad.copy()
        for i in np.where(bad)[0]:expanded[max(0,i-pad):min(len(bad),i+pad+1)]=True
        bad=expanded

    good=~bad
    # Keep short pauses inside an otherwise correct take.
    bridge=max(1,int(round({1:1.10,2:.90,3:.70}[strength]*sample_fps)))
    good=_fill_short_false(good,bridge)
    # Remove only very short isolated flashes.
    min_good_sec={1:3.2,2:2.8,3:2.4}[strength]
    good=_remove_short_true(good,max(2,int(round(min_good_sec*sample_fps))))

    segs=[]
    for s,e in runs(good,1):
        st=max(0.0,rows[s]['t']-.10);en=min(dur,rows[min(e-1,len(rows)-1)]['t']+1/sample_fps+.10)
        if en-st>=min_good_sec*.75:segs.append((st,en))
    if not segs:segs=[(0,min(dur,max(target,5.0)))]

    # Merge close good regions so preview has fewer seek points and context is preserved.
    merged=[];gap={1:1.25,2:1.0,3:.8}[strength]
    for s,e in segs:
        if merged and s-merged[-1][1]<=gap:merged[-1]=(merged[-1][0],e)
        else:merged.append((s,e))

    # The target is advisory. Do not discard good footage just to hit an exact duration.
    total_good=sum(e-s for s,e in merged)
    if total_good>max(target*1.8,target+18) and dur>target*2:
        # Keep the longest/cleanest complete takes, not tiny score windows.
        scored=[]
        for s,e in merged:
            idx=[i for i,r in enumerate(rows) if s<=r['t']<=e]
            if not idx:continue
            quality=float(np.mean(np.clip(shp[idx]/max(np.percentile(shp,75),1),0,1)))
            quality+=0.20*min(1.0,(e-s)/7.0)
            scored.append((quality,s,e))
        scored.sort(reverse=True)
        chosen=[];kept=0.0
        for _,s,e in scored:
            chosen.append((s,e));kept+=e-s
            if kept>=target*1.15:break
        merged=sorted(chosen)

    drops=[];cur=0.0
    for s,e in merged:
        if s-cur>.12:drops.append((cur,s))
        cur=e
    if dur-cur>.12:drops.append((cur,dur))
    kept=sum(e-s for s,e in merged)
    return merged,drops,{'duration':dur,'kept':kept,'dropped':max(0,dur-kept),'samples':len(rows),'idle_seconds':float(np.sum(idle)/sample_fps),'technical_bad_seconds':float(np.sum(tech)/sample_fps),'target_is_advisory':True,'strategy':'remove_confident_failures_only'}


def main():
    if len(sys.argv)<4:raise SystemExit(2)
    mode=sys.argv[1];src=sys.argv[2];out=sys.argv[-1]
    try:
        if mode=='probe':obj={'ok':True,'meta':probe(src)}
        elif mode=='analyze':
            strength=int(sys.argv[3]);target=int(sys.argv[4]);keep,drop,stats=analyze(src,strength,target);obj={'ok':True,'keep':keep,'drop':drop,'stats':stats}
        else:raise RuntimeError('Mode worker không hợp lệ.')
    except Exception as e:obj={'ok':False,'error':f'{type(e).__name__}: {e}\n{traceback.format_exc()}'}
    write(out,obj)

if __name__=='__main__':main()
