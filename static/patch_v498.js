(()=>{
  const q=id=>document.getElementById(id);
  let fontList=[];

  // Hidden font picker.
  let picker=q('fontFileInput');
  if(!picker){
    picker=document.createElement('input');picker.id='fontFileInput';picker.type='file';picker.accept='.ttf,.otf,.ttc';picker.style.display='none';document.body.appendChild(picker);
  }

  function fontFamily(id){return id?'ARV_'+id.replace(/[^a-zA-Z0-9_-]/g,'_'):''}

  function registerFont(f){
    if(!f||!f.id)return;
    const fam=fontFamily(f.id);
    if(document.getElementById('fontcss_'+fam))return;
    const st=document.createElement('style');st.id='fontcss_'+fam;
    st.textContent=`@font-face{font-family:"${fam}";src:url("${f.url}") format("truetype");font-display:swap}`;
    document.head.appendChild(st);
  }

  async function loadFonts(selectId){
    try{
      const r=await fetch('/api/fonts',{cache:'no-store'}).then(x=>x.json());
      if(!r.ok)return;
      fontList=r.fonts||[];fontList.forEach(registerFont);
      const sel=q('tFontFamily');if(!sel)return;
      const current=selectId??sel.value;
      sel.innerHTML='<option value="">Font mặc định</option>'+fontList.map(f=>`<option value="${f.id.replace(/"/g,'&quot;')}">${f.name}</option>`).join('');
      if(current&&fontList.some(f=>f.id===current))sel.value=current;
    }catch(e){console.warn('font library',e)}
  }

  function ensureFontControls(){
    const p=q('textStylePanel');if(!p||q('textFontRow'))return;
    const row=document.createElement('div');row.className='row';row.id='textFontRow';
    row.innerHTML='<label>Font</label><select id="tFontFamily" class="grow"><option value="">Font mặc định</option></select><button id="uploadFontBtn" type="button">📁 Tải font</button>';
    p.insertBefore(row,p.firstChild);
    q('tFontFamily').addEventListener('change',()=>{
      if(selectedLayer>=0&&layers[selectedLayer]?.type==='text'){
        if(typeof pushHistory==='function')pushHistory();
        layers[selectedLayer].fontId=q('tFontFamily').value||'';
        if(typeof applyTextStyle==='function')applyTextStyle(false);
        if(typeof updateTextOverlay==='function')updateTextOverlay();
      }
    });
    q('uploadFontBtn').addEventListener('click',()=>picker.click());
    loadFonts();
  }

  picker.addEventListener('change',async()=>{
    const f=picker.files&&picker.files[0];if(!f)return;
    const fd=new FormData();fd.append('file',f);
    if(typeof setStatus==='function')setStatus('Đang lưu font...');
    try{
      const r=await fetch('/api/upload_font',{method:'POST',body:fd}).then(x=>x.json());
      if(!r.ok){alert(r.error||'Không lưu được font');return}
      await loadFonts(r.id);
      if(selectedLayer>=0&&layers[selectedLayer]?.type==='text'){
        layers[selectedLayer].fontId=r.id;
        q('tFontFamily').value=r.id;
        updateTextOverlay();
      }
      if(typeof setStatus==='function')setStatus('Đã lưu font: '+r.name);
    }catch(e){alert('Lỗi tải font: '+e.message)}
    finally{picker.value=''}
  });

  // Extend text inspector with the saved font field.
  const oldLoad=window.loadLayerInspector;
  if(typeof oldLoad==='function')window.loadLayerInspector=function(render=true){
    oldLoad(render);ensureFontControls();
    if(selectedLayer>=0&&layers[selectedLayer]?.type==='text'){
      const L=layers[selectedLayer];if(L.fontId==null)L.fontId='';
      loadFonts(L.fontId);
    }
  };

  const oldApply=window.applyTextStyle;
  if(typeof oldApply==='function')window.applyTextStyle=function(render=false){
    if(selectedLayer>=0&&layers[selectedLayer]?.type==='text'&&q('tFontFamily'))layers[selectedLayer].fontId=q('tFontFamily').value||'';
    return oldApply(render);
  };

  const oldOverlay=window.updateTextOverlay;
  if(typeof oldOverlay==='function')window.updateTextOverlay=function(){
    oldOverlay();
    const el=q('previewTextOverlay');if(!el)return;
    let active=null;
    for(const L of layers){if(L.type==='text'&&L.enabled!==false&&playhead>=L.start&&playhead<L.end)active=L}
    el.style.fontFamily=active?.fontId?`"${fontFamily(active.fontId)}", sans-serif`:'';
  };

  // Refresh clone library on every app start/update. Saved clones live outside source files.
  setTimeout(()=>{try{if(typeof loadVoiceLibrary==='function')loadVoiceLibrary()}catch(_){}},250);
  ensureFontControls();
  loadFonts();
})();
