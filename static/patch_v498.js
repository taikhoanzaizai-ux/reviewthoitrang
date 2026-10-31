(()=>{
  const q=id=>document.getElementById(id);
  let fontList=[];

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
    st.textContent=`@font-face{font-family:"${fam}";src:url("${f.url}");font-display:swap}`;
    document.head.appendChild(st);
  }

  async function fontBackendReady(showError=false){
    try{
      const resp=await fetch('/api/fonts',{cache:'no-store'});
      if(!resp.ok){
        if(showError)alert(`Backend Font chưa sẵn sàng (HTTP ${resp.status}).\nHãy đóng tool, chạy UPDATE rồi mở lại RUN.bat.`);
        return null;
      }
      const r=await resp.json();
      if(!r.ok){if(showError)alert(r.error||'Backend Font chưa sẵn sàng.');return null}
      return r;
    }catch(e){
      if(showError)alert('Không kết nối được backend Font. Hãy đóng tool rồi mở lại sau khi Update.\nChi tiết: '+e.message);
      return null;
    }
  }

  async function loadFonts(selectId){
    const r=await fontBackendReady(false);if(!r)return;
    fontList=r.fonts||[];fontList.forEach(registerFont);
    const sel=q('tFontFamily');if(!sel)return;
    const current=selectId??sel.value;
    sel.innerHTML='<option value="">Font mặc định</option>'+fontList.map(f=>`<option value="${f.id.replace(/"/g,'&quot;')}">${f.name}</option>`).join('');
    if(current&&fontList.some(f=>f.id===current))sel.value=current;
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
    q('uploadFontBtn').addEventListener('click',async()=>{
      const ok=await fontBackendReady(true);if(ok)picker.click();
    });
    loadFonts();
  }

  function uploadFontXHR(file){
    return new Promise(resolve=>{
      const fd=new FormData();fd.append('file',file);
      const xhr=new XMLHttpRequest();xhr.open('POST','/api/upload_font');
      xhr.upload.onprogress=e=>{
        if(e.lengthComputable&&typeof setStatus==='function')setStatus('Đang tải font... '+Math.round(e.loaded/e.total*100)+'%');
      };
      xhr.onload=()=>{
        let data=null;
        try{data=JSON.parse(xhr.responseText)}catch(_){
          resolve({ok:false,error:`Backend trả dữ liệu không hợp lệ (HTTP ${xhr.status}). Hãy đóng tool và mở lại sau Update.`});return;
        }
        if(xhr.status<200||xhr.status>=300){resolve({ok:false,error:data?.error||`HTTP ${xhr.status}`});return}
        resolve(data);
      };
      xhr.onerror=()=>resolve({ok:false,error:'Mất kết nối với backend khi tải font. Hãy đóng tool rồi mở lại.'});
      xhr.send(fd);
    });
  }

  picker.addEventListener('change',async()=>{
    const f=picker.files&&picker.files[0];if(!f)return;
    if(typeof setStatus==='function')setStatus('Đang lưu font...');
    try{
      const r=await uploadFontXHR(f);
      if(!r.ok){alert('Lỗi tải font: '+(r.error||'Không lưu được font'));return}
      await loadFonts(r.id);
      if(selectedLayer>=0&&layers[selectedLayer]?.type==='text'){
        layers[selectedLayer].fontId=r.id;
        if(q('tFontFamily'))q('tFontFamily').value=r.id;
        if(typeof updateTextOverlay==='function')updateTextOverlay();
      }
      if(typeof setStatus==='function')setStatus('Đã lưu font: '+r.name);
    }finally{picker.value=''}
  });

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

  setTimeout(()=>{try{if(typeof loadVoiceLibrary==='function')loadVoiceLibrary()}catch(_){}},250);
  ensureFontControls();loadFonts();
})();
