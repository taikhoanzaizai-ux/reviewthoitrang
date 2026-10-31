import json, shutil, time, textwrap
from pathlib import Path
from werkzeug.utils import secure_filename


def install(core):
    font_dir=core.APP_DIR/'data'/'fonts'
    font_dir.mkdir(parents=True,exist_ok=True)
    voice_backup=core.APP_DIR/'data'/'voice_library_backup'
    voice_backup.mkdir(parents=True,exist_ok=True)

    # Restore saved clone voices if an older update ever removed the root voice_library.
    try:
        if not core.VOICE_LIBRARY_FILE.exists() and (voice_backup/'library.json').exists():
            for p in voice_backup.iterdir():
                dst=core.VOICE_LIBRARY_DIR/p.name
                if p.is_file(): shutil.copy2(p,dst)
    except Exception:
        pass

    def backup_voice_library():
        try:
            voice_backup.mkdir(parents=True,exist_ok=True)
            for p in core.VOICE_LIBRARY_DIR.iterdir():
                if p.is_file(): shutil.copy2(p,voice_backup/p.name)
        except Exception:
            pass

    backup_voice_library()
    old_save=core.save_voice_library
    def save_voice_library_safe(data):
        old_save(data)
        backup_voice_library()
    core.save_voice_library=save_voice_library_safe

    def font_files():
        out=[]
        for p in sorted(font_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in ('.ttf','.otf','.ttc'):
                out.append({'id':p.name,'name':p.stem,'url':'/media/font/'+p.name})
        return out

    @core.app.route('/api/fonts',methods=['GET'])
    def api_fonts():
        return core.jsonify(ok=True,fonts=font_files())

    @core.app.route('/api/upload_font',methods=['POST'])
    def api_upload_font():
        try:
            f=core.request.files.get('file')
            if not f or not f.filename:return core.jsonify(ok=False,error='Chưa chọn font.')
            ext=Path(f.filename).suffix.lower()
            if ext not in ('.ttf','.otf','.ttc'):
                return core.jsonify(ok=False,error='Chỉ hỗ trợ font .ttf / .otf / .ttc')
            base=secure_filename(Path(f.filename).stem) or 'font'
            name=f'{base}{ext}'
            dst=font_dir/name
            n=1
            while dst.exists():
                dst=font_dir/f'{base}_{n}{ext}';n+=1
            f.save(dst)
            return core.jsonify(ok=True,id=dst.name,name=dst.stem,url='/media/font/'+dst.name)
        except Exception as e:
            return core.jsonify(ok=False,error=f'{type(e).__name__}: {e}')

    @core.app.route('/media/font/<path:font_id>')
    def media_font(font_id):
        p=font_dir/Path(font_id).name
        return core.send_file(p,conditional=True) if p.exists() else ('No font',404)

    style_ctx={}
    old_make=core.make_text_png
    old_render=core.render_project

    def _font_path_for(layer):
        fid=(layer or {}).get('fontId') or ''
        if fid:
            p=font_dir/Path(fid).name
            if p.exists():return p
        try:
            fp=core._font_path()
            return Path(fp) if fp else None
        except Exception:
            return None

    def make_text_png_persistent(text,width,height,idx):
        L=style_ctx.get(idx,{})
        size=max(12,min(160,int(float(L.get('fontSize',56) or 56))))
        color=L.get('color') or '#ffffff'
        stroke=L.get('stroke') or '#000000'
        pos=L.get('position') or 'bottom'
        font_path=_font_path_for(L)
        try:
            font=core.ImageFont.truetype(str(font_path),size=size) if font_path else core.ImageFont.load_default()
        except Exception:
            font=core.ImageFont.load_default()
        canvas=core.Image.new('RGBA',(width,height),(0,0,0,0));draw=core.ImageDraw.Draw(canvas)
        maxw=int(width*.86)
        words=(text or '').split(); lines=[];cur=''
        for w in words:
            test=(cur+' '+w).strip()
            bb=draw.textbbox((0,0),test,font=font,stroke_width=max(1,int(size*.04)))
            if bb[2]-bb[0]<=maxw or not cur:cur=test
            else:lines.append(cur);cur=w
        if cur:lines.append(cur)
        if not lines:lines=[text or '']
        line_h=max(size+8,int(size*1.18)); total_h=line_h*len(lines)
        if pos=='top': y=max(24,int(height*.08))
        elif pos=='center': y=max(0,int((height-total_h)/2))
        else:y=max(0,int(height-total_h-height*.08))
        sw=max(1,int(size*.045))
        for line in lines:
            bb=draw.textbbox((0,0),line,font=font,stroke_width=sw)
            tw=bb[2]-bb[0];x=max(0,int((width-tw)/2))
            draw.text((x,y),line,font=font,fill=color,stroke_width=sw,stroke_fill=stroke)
            y+=line_h
        out=core.GEN/f'text_font_{idx}_{int(time.time()*1000)}.png'
        canvas.save(out)
        return out

    core.make_text_png=make_text_png_persistent

    def render_with_font_library(project,src,out,meta,progress_cb=None):
        style_ctx.clear()
        for i,L in enumerate(project.get('layers',[]) or []):
            if L.get('type')=='text':style_ctx[i]=L
        try:
            return old_render(project,src,out,meta,progress_cb=progress_cb)
        finally:
            style_ctx.clear()
    core.render_project=render_with_font_library
