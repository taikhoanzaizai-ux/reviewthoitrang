import sys, json, traceback
from pathlib import Path

_instances = {}

def get_tts(mode):
    from vieneu import Vieneu
    mode = mode or 'v3turbo'
    if mode not in _instances:
        _instances[mode] = Vieneu(mode=mode)
    return _instances[mode]

def handle(req):
    cmd = req.get('cmd')
    if cmd == 'list':
        tts = get_tts(req.get('mode','v3turbo'))
        voices=[]
        for item in tts.list_preset_voices():
            if isinstance(item,(list,tuple)) and len(item)>=2:
                voices.append({'label':str(item[0]),'id':str(item[1])})
            else:
                voices.append({'label':str(item),'id':str(item)})
        return {'ok':True,'voices':voices}
    if cmd == 'synth':
        data=req.get('request') or {}
        text=(data.get('text') or '').strip()
        if not text:
            raise RuntimeError('Lời review/Voice đang trống.')
        tts=get_tts(data.get('mode','v3turbo'))
        out_wav=data['out_wav']
        ref=data.get('ref_audio')
        voice=data.get('voice')
        if ref:
            audio=tts.infer(text,ref_audio=ref,denoise=True)
        else:
            audio=tts.infer(text,voice=voice or None)
        tts.save(audio,out_wav)
        p=Path(out_wav)
        if not p.exists() or p.stat().st_size<1000:
            raise RuntimeError('VieNeu không tạo được file voice hợp lệ.')
        return {'ok':True,'out_wav':out_wav}
    raise RuntimeError('Lệnh voice daemon không hợp lệ.')

def main():
    for line in sys.stdin:
        try:
            req=json.loads(line)
            ans=handle(req)
        except Exception as e:
            ans={'ok':False,'error':f'{type(e).__name__}: {e}','trace':traceback.format_exc()}
        sys.stdout.write(json.dumps(ans,ensure_ascii=False)+'\n')
        sys.stdout.flush()

if __name__=='__main__':
    main()
