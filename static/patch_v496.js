(()=>{
  const q=id=>document.getElementById(id);
  const clone=v=>JSON.parse(JSON.stringify(v));
  let undoStack=[], redoStack=[], restoring=false;
  const multiClip=new Set(), multiLayer=new Set();

  function ensureIds(){
    (clips||[]).forEach(c=>{if(!c._uid)c._uid='c_'+Date.now()+'_'+Math.random().toString(36).slice(2)});
    (layers||[]).forEach(L=>{if(!L._uid)L._uid='l_'+Date.now()+'_'+Math.random().toString(36).slice(2);if(L.sourceOffset==null)L.sourceOffset=0;if(L.speed==null)L.speed=1});
  }
  function snapshot(){ensureIds();return {clips:clone(clips),layers:clone(layers),selected,selectedLayer,playhead};}
  function sig(s){return JSON.stringify([s.clips,s.layers]);}
  function pushHistory(){
    if(restoring)return;
    const s=snapshot(), last=undoStack[undoStack.length-1];
    if(!last||sig(last)!==sig(s)){undoStack.push(s);if(undoStack.length>80)undoStack.shift();}
    redoStack=[];
  }
  function restore(s){
    if(!s)return; restoring=true; pauseTimeline();
    clips=clone(s.clips);layers=clone(s.layers);selected=s.selected;selectedLayer=s.selectedLayer;playhead=Math.min(s.playhead||0,totalDur());
    multiClip.clear();multiLayer.clear();
    ensureIds();renderTimeline();
    if(selected>=0&&clips[selected])loadInspector();else if(selectedLayer>=0&&layers[selectedLayer])loadLayerInspector();else{hideLayerEditor();}
    if(clips.length)seekTimeline(Math.min(playhead,totalDur()));
    restoring=false;
  }
  function undo(){if(!undoStack.length)return;const cur=snapshot(),prev=undoStack.pop();redoStack.push(cur);restore(prev);setStatus('Đã Undo');}
  function redo(){if(!redoStack.length)return;const cur=snapshot(),next=redoStack.pop();undoStack.push(cur);restore(next);setStatus('Đã Redo');}

  // History buttons
  const top=document.querySelector('.top');
  if(top&&!q('undoBtn')){
    const ref=[...top.querySelectorAll('button')].find(b=>b.textContent.includes('Tách clip'));
    const u=document.createElement('button');u.id='undoBtn';u.textContent='↶ Undo';u.onclick=undo;
    const r=document.createElement('button');r.id='redoBtn';r.textContent='↷ Redo';r.onclick=redo;
    if(ref){top.insertBefore(r,ref);top.insertBefore(u,r)}else{top.append(u,r)}
  }

  // Multi-select with Ctrl/Shift click across video/audio/voice/text.
  function refreshMulti(){
    ensureIds();
    document.querySelectorAll('.block').forEach(el=>{
      const i=+el.dataset.i, kind=el.dataset.kind;
      const obj=kind==='clip'?clips[i]:layers[i];
      const on=obj&&(kind==='clip'?multiClip.has(obj._uid):multiLayer.has(obj._uid));
      el.classList.toggle('multiSelected',!!on);
      if(on)el.style.boxShadow='0 0 0 2px #60a5fa inset';else el.style.boxShadow='';
    });
    const n=multiClip.size+multiLayer.size;if(n>1)setStatus(`Đang chọn ${n} mục • Ctrl/Shift+click`);
  }
  document.addEventListener('pointerdown',e=>{
    const el=e.target.closest&&e.target.closest('.block');if(!el)return;
    if(!(e.ctrlKey||e.metaKey||e.shiftKey)){
      multiClip.clear();multiLayer.clear();return;
    }
    e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();
    ensureIds();const i=+el.dataset.i,kind=el.dataset.kind,obj=kind==='clip'?clips[i]:layers[i];if(!obj)return;
    const set=kind==='clip'?multiClip:multiLayer;
    if(set.has(obj._uid))set.delete(obj._uid);else set.add(obj._uid);
    if(kind==='clip'){selected=i;selectedLayer=-1;loadInspector();hideLayerEditor()}else{selectedLayer=i;selected=-1;loadLayerInspector()}
    refreshMulti();
  },true);

  const oldRender=window.renderTimeline;
  window.renderTimeline=function(){oldRender();ensureIds();setTimeout(refreshMulti,0)};

  // Save one snapshot at start of mouse edits / numeric edits.
  document.addEventListener('pointerdown',e=>{if(e.target.closest&&e.target.closest('.block,.card input[type=range]'))pushHistory()},true);
  document.addEventListener('focusin',e=>{if(e.target.matches&&e.target.matches('input,textarea,select'))pushHistory()},true);

  function wrapHistory(name){const old=window[name];if(typeof old!=='function')return;window[name]=function(...args){pushHistory();return old.apply(this,args)}}
  ['moveSelected','addText','toggleProp','toggleLayerEnabled','pasteSelected'].forEach(wrapHistory);

  // Multi-delete. Normal delete still works when only one item is selected.
  const oldDelete=window.deleteSelected;
  window.deleteSelected=function(){
    if(multiClip.size+multiLayer.size>0){
      pushHistory();ensureIds();
      if(multiClip.size){const remain=clips.filter(c=>!multiClip.has(c._uid));if(remain.length)clips=remain;}
      if(multiLayer.size)layers=layers.filter(L=>!multiLayer.has(L._uid));
      multiClip.clear();multiLayer.clear();selected=clips.length?Math.min(Math.max(selected,0),clips.length-1):-1;selectedLayer=-1;renderTimeline();
      if(selected>=0)loadInspector();else hideLayerEditor();seekTimeline(Math.min(playhead,totalDur()));return;
    }
    pushHistory();return oldDelete();
  };

  // Split VIDEO or selected AUDIO/VOICE/TEXT layer at playhead.
  const oldSplit=window.splitAtPlayhead;
  window.splitAtPlayhead=function(){
    if(selectedLayer>=0&&layers[selectedLayer]){
      const L=layers[selectedLayer];if(playhead<=L.start+.05||playhead>=L.end-.05)return;
      pushHistory();
      const idx=selectedLayer, speed=Math.max(.25,Number(L.speed)||1), cut=playhead;
      const left={...L,end:cut,_uid:'l_'+Date.now()+'_a'};
      const right={...L,start:cut,_uid:'l_'+Date.now()+'_b'};
      if(['audio','voice'].includes(L.type))right.sourceOffset=(Number(L.sourceOffset)||0)+(cut-L.start)*speed;
      layers.splice(idx,1,left,right);selectedLayer=idx+1;selected=-1;renderTimeline();loadLayerInspector();setStatus('Đã tách layer tại playhead');return;
    }
    pushHistory();return oldSplit();
  };

  // Preview source offset for split audio + speed.
  window.syncLayers=function(shouldPlay){
    for(const [id,a] of audioPlayers.entries())a.__used=false;
    for(const L of layers){
      if(!['voice','audio'].includes(L.type)||!L.url)continue;
      let a=audioPlayers.get(L.id);if(!a){a=new Audio(L.url);a.preload='auto';audioPlayers.set(L.id,a)}
      a.__used=true;const speed=Math.max(.25,Math.min(4,Number(L.speed)||1));a.playbackRate=speed;
      const allowed=L.enabled!==false&&(soloId==null||soloId===L.id),inside=playhead>=L.start&&playhead<L.end;
      if(allowed&&inside){
        const desired=Math.max(0,(Number(L.sourceOffset)||0)+(playhead-L.start)*speed);
        if(Math.abs(a.currentTime-desired)>.18)a.currentTime=desired;
        a.volume=Math.max(0,Math.min(1,(L.volume??100)/100));if(shouldPlay&&a.paused)a.play().catch(()=>{});
      }else if(!a.paused)a.pause();
    }
    for(const [id,a] of audioPlayers.entries())if(!a.__used&&!a.paused)a.pause();
  };

  // Extract original video audio into AUDIO track.
  if(top&&!q('detachAudioBtn')){
    const ref=[...top.querySelectorAll('button')].find(b=>b.textContent.includes('Audio'));
    const b=document.createElement('button');b.id='detachAudioBtn';b.textContent='🎵 Tách âm';b.title='Tách âm thanh gốc của video xuống track AUDIO';
    b.onclick=async()=>{
      if(!meta)return alert('Chọn video trước');pushHistory();setStatus('Đang tách âm thanh...');
      const r=await fetch('/api/extract_video_audio',{method:'POST'}).then(x=>x.json());if(!r.ok){alert(r.error);return}
      clips.forEach(c=>c.mute=true);
      layers.push({id:r.id,_uid:'l_'+Date.now(),type:'audio',assetId:r.id,url:r.url,name:'Audio gốc video',start:0,end:Math.min(totalDur(),r.duration||totalDur()),sourceOffset:0,speed:1,volume:100,enabled:true});
      selectedLayer=layers.length-1;selected=-1;renderTimeline();loadLayerInspector();setStatus('Đã tách audio xuống timeline');
    };
    if(ref)ref.insertAdjacentElement('afterend',b);else top.appendChild(b);
  }

  // Persistent export folder chooser.
  if(top&&!q('exportFolderBtn')){
    const exp=[...top.querySelectorAll('button')].find(b=>b.textContent.includes('XUẤT MP4'));
    const b=document.createElement('button');b.id='exportFolderBtn';b.textContent='📁 Thư mục lưu';b.title='Chọn và ghi nhớ thư mục xuất video';
    b.onclick=async()=>{const r=await fetch('/api/export_folder',{method:'POST'}).then(x=>x.json());if(r.ok){b.title='Đang lưu vào: '+r.path;setStatus('Thư mục xuất: '+r.path)}else if(!r.cancelled)alert(r.error||'Không chọn được thư mục')};
    if(exp)top.insertBefore(b,exp);else top.appendChild(b);
    fetch('/api/export_folder').then(x=>x.json()).then(r=>{if(r.ok&&r.path)b.title='Đang lưu vào: '+r.path}).catch(()=>{});
  }

  // Keyboard Undo / Redo. Capture phase so it wins over editor shortcuts.
  document.addEventListener('keydown',e=>{
    const tag=(document.activeElement?.tagName||'').toLowerCase();
    const mod=e.ctrlKey||e.metaKey;
    if(mod&&e.key.toLowerCase()==='z'){
      if(['input','textarea'].includes(tag)&&!e.shiftKey)return;
      e.preventDefault();e.stopImmediatePropagation();if(e.shiftKey)redo();else undo();return;
    }
    if(mod&&e.key.toLowerCase()==='y'){
      e.preventDefault();e.stopImmediatePropagation();redo();
    }
  },true);

  ensureIds();
})();
