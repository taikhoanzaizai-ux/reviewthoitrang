(()=>{
  const q=id=>document.getElementById(id);

  const top=document.querySelector('.top');
  if(top && !q('updateAppBtn')){
    const exportBtn=[...top.querySelectorAll('button')].find(b=>b.textContent.includes('XUẤT MP4'));
    const btn=document.createElement('button');
    btn.id='updateAppBtn';btn.textContent='⬆ UPDATE';btn.title='Cập nhật bản mới nhất từ GitHub';
    btn.onclick=async()=>{
      if(!confirm('Cập nhật tool từ GitHub? Tool sẽ tự đóng và mở lại sau khi update.'))return;
      btn.disabled=true;
      if(typeof setStatus==='function')setStatus('Đang mở updater...');
      let requestSent=false;
      try{
        requestSent=true;
        const resp=await fetch('/api/update_app',{method:'POST',cache:'no-store'});
        const txt=await resp.text();
        let r={};
        try{r=JSON.parse(txt)}catch(_){r={ok:resp.ok}}
        if(!resp.ok||r.ok===false){
          btn.disabled=false;
          alert(r.error||('Không cập nhật được. HTTP '+resp.status));
          return;
        }
        if(typeof setStatus==='function')setStatus('Updater đã mở • tool sẽ tự đóng...');
      }catch(e){
        // localhost can disappear immediately after UPDATE.bat starts. In that case
        // don't show a false failure: the updater is already being launched.
        if(requestSent){
          if(typeof setStatus==='function')setStatus('Đã gửi lệnh Update • chờ cửa sổ updater...');
        }else{
          btn.disabled=false;
          alert('Không gọi được updater: '+e.message);
        }
      }
    };
    if(exportBtn)top.insertBefore(btn,exportBtn);else top.appendChild(btn);
  }

  const numericDefs={
    zoom:{min:.5,max:3,step:.05,suffix:'x'},
    rotate:{min:-180,max:180,step:1,suffix:'°'},
    volume:{min:0,max:200,step:1,suffix:'%'},
    voiceSpeed:{min:.5,max:2,step:.05,suffix:'x'},
    tlzoom:{min:35,max:190,step:1,suffix:''}
  };
  function addNumberForRange(id,cfg){
    const r=q(id);if(!r||q(id+'Num'))return;
    const n=document.createElement('input');n.type='number';n.id=id+'Num';n.min=cfg.min;n.max=cfg.max;n.step=cfg.step;n.value=r.value;
    n.style.width='78px';n.style.flex='0 0 78px';n.title='Có thể nhập số trực tiếp';
    const syncFromRange=()=>{n.value=r.value};
    const syncToRange=()=>{
      let v=parseFloat(n.value);if(!Number.isFinite(v))return;
      v=Math.max(cfg.min,Math.min(cfg.max,v));n.value=v;r.value=v;
      r.dispatchEvent(new Event('input',{bubbles:true}));r.dispatchEvent(new Event('change',{bubbles:true}));
    };
    r.addEventListener('input',syncFromRange);n.addEventListener('change',syncToRange);n.addEventListener('keydown',e=>{if(e.key==='Enter')syncToRange()});
    r.parentElement.insertBefore(n,r.nextSibling);
  }
  Object.entries(numericDefs).forEach(([id,cfg])=>addNumberForRange(id,cfg));

  const layerEditor=q('layerEditor');
  if(layerEditor && !q('layerSpeedRow')){
    const row=document.createElement('div');row.className='row';row.id='layerSpeedRow';row.style.display='none';
    row.innerHTML='<label>Speed</label><input id="lspeed" type="number" min="0.25" max="4" step="0.05" value="1" style="width:100px"><span id="lspeedv">1.00x</span>';
    const volRow=q('layerVolRow');
    if(volRow)volRow.insertAdjacentElement('afterend',row);else layerEditor.appendChild(row);
  }

  const oldLoad=window.loadLayerInspector;
  if(typeof oldLoad==='function'){
    window.loadLayerInspector=function(render=true){
      oldLoad(render);
      if(selectedLayer<0||!layers[selectedLayer])return;
      const L=layers[selectedLayer],audio=['voice','audio'].includes(L.type),row=q('layerSpeedRow');
      if(row)row.style.display=audio?'flex':'none';
      if(audio&&q('lspeed')){q('lspeed').value=L.speed??1;q('lspeedv').textContent=(L.speed??1).toFixed(2)+'x'}
    }
  }
  const oldApply=window.applyLayerInspector;
  if(typeof oldApply==='function'){
    window.applyLayerInspector=function(render=true){
      if(selectedLayer>=0&&layers[selectedLayer]&&['voice','audio'].includes(layers[selectedLayer].type)&&q('lspeed')){
        let v=parseFloat(q('lspeed').value);if(!Number.isFinite(v))v=1;v=Math.max(.25,Math.min(4,v));
        layers[selectedLayer].speed=v;q('lspeed').value=v;q('lspeedv').textContent=v.toFixed(2)+'x';
      }
      oldApply(render);
    }
  }
  if(q('lspeed')){
    q('lspeed').addEventListener('input',()=>{if(selectedLayer>=0&&layers[selectedLayer]){layers[selectedLayer].speed=Math.max(.25,Math.min(4,parseFloat(q('lspeed').value)||1));q('lspeedv').textContent=layers[selectedLayer].speed.toFixed(2)+'x';syncLayers(false)}})
  }

  window.syncLayers=function(shouldPlay){
    for(const [id,a] of audioPlayers.entries())a.__used=false;
    for(const L of layers){
      if(!['voice','audio'].includes(L.type)||!L.url)continue;
      let a=audioPlayers.get(L.id);if(!a){a=new Audio(L.url);a.preload='auto';audioPlayers.set(L.id,a)}
      a.__used=true;
      const speed=Math.max(.25,Math.min(4,Number(L.speed)||1));a.playbackRate=speed;
      const allowed=L.enabled!==false&&(soloId==null||soloId===L.id),inside=playhead>=L.start&&playhead<L.end;
      if(allowed&&inside){
        const desired=Math.max(0,(playhead-L.start)*speed);
        if(Math.abs(a.currentTime-desired)>.22)a.currentTime=desired;
        a.volume=Math.max(0,Math.min(1,(L.volume??100)/100));
        if(shouldPlay&&a.paused)a.play().catch(()=>{});
      }else if(!a.paused)a.pause();
    }
    for(const [id,a] of audioPlayers.entries())if(!a.__used&&!a.paused)a.pause();
  };

  if(typeof video!=='undefined'&&video){video.preload='auto'}

  const oldTick=window.tick;
  window.tick=function(){
    if(!playing)return;
    let c=clips[activeClip],st=starts(),tl=st[activeClip]+(video.currentTime-c.start)/c.speed;
    playhead=Math.max(st[activeClip],Math.min(st[activeClip]+outDur(c),tl));updatePlayhead();
    if(video.currentTime>=c.end-.045){
      activeClip++;
      if(activeClip>=clips.length){pauseTimeline();playhead=totalDur();updatePlayhead();return}
      c=clips[activeClip];
      try{if(typeof video.fastSeek==='function')video.fastSeek(c.start);else video.currentTime=c.start}catch(_){video.currentTime=c.start}
      video.playbackRate=c.speed;applyVisual(c);video.play().catch(()=>pauseTimeline());
    }
    syncLayers(true);raf=requestAnimationFrame(window.tick);
  };

  for(const L of layers||[])if(L.speed==null)L.speed=1;
})();
