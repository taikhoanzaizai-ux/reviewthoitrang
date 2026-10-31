(()=>{
  const q=id=>document.getElementById(id);
  const isTyping=()=>{
    const e=document.activeElement;
    return !!e && (e.tagName==='INPUT'||e.tagName==='TEXTAREA'||e.tagName==='SELECT'||e.isContentEditable);
  };

  // Q = trim đầu tới playhead, E = trim đuôi tới playhead, S = split.
  function sourceTimeAtPlayhead(i){
    if(i<0||!clips[i])return null;
    const st=starts();
    const c=clips[i];
    const tl0=st[i],tl1=tl0+outDur(c);
    if(playhead<tl0||playhead>tl1)return null;
    return c.start+(playhead-tl0)*Math.max(.25,Number(c.speed)||1);
  }
  function trimSelectedHead(){
    if(selected<0||!clips[selected])return;
    const c=clips[selected],src=sourceTimeAtPlayhead(selected);
    if(src==null||src<=c.start+.03||src>=c.end-.08)return;
    if(typeof pushHistory==='function')pushHistory();
    c.start=Math.min(c.end-.05,src);
    if(typeof renderTimeline==='function')renderTimeline();
    if(typeof loadInspector==='function')loadInspector();
    if(typeof seekTimeline==='function')seekTimeline(Math.min(playhead,totalDur()));
  }
  function trimSelectedTail(){
    if(selected<0||!clips[selected])return;
    const c=clips[selected],src=sourceTimeAtPlayhead(selected);
    if(src==null||src<=c.start+.08||src>=c.end-.03)return;
    if(typeof pushHistory==='function')pushHistory();
    c.end=Math.max(c.start+.05,src);
    if(typeof renderTimeline==='function')renderTimeline();
    if(typeof loadInspector==='function')loadInspector();
    if(typeof seekTimeline==='function')seekTimeline(Math.min(playhead,totalDur()));
  }
  document.addEventListener('keydown',e=>{
    if(e.ctrlKey||e.metaKey||e.altKey||isTyping())return;
    const k=e.key.toLowerCase();
    if(k==='q'){e.preventDefault();trimSelectedHead()}
    else if(k==='e'){e.preventDefault();trimSelectedTail()}
    else if(k==='s'){e.preventDefault();if(typeof splitAtPlayhead==='function')splitAtPlayhead()}
  },true);

  // Voice studio speed label + persistence.
  const vs=q('voiceSpeed'),vsv=q('voiceSpeedV');
  function syncVoiceStudioSpeed(){
    if(!vs)return;
    let v=parseFloat(vs.value);if(!Number.isFinite(v))v=1;v=Math.max(.5,Math.min(2,v));vs.value=v;
    if(vsv)vsv.textContent=v.toFixed(2)+'x';
    const n=q('voiceSpeedNum');if(n&&document.activeElement!==n)n.value=v;
  }
  if(vs){vs.addEventListener('input',syncVoiceStudioSpeed);vs.addEventListener('change',syncVoiceStudioSpeed);syncVoiceStudioSpeed()}

  // Ensure generated Voice remembers the actual speed and timeline playback honors it.
  const oldAddLastVoice=window.addLastVoice;
  window.addLastVoice=function(){
    if(!lastVoice){alert('Tạo voice trước.');return}
    if(typeof pushHistory==='function')pushHistory();
    const sp=1; // synth_voice already bakes Voice Studio speed into generated audio
    layers.push({id:lastVoice.id,type:'voice',assetId:lastVoice.id,url:lastVoice.url,name:'VieNeu Voice',start:playhead,end:Math.min(totalDur(),playhead+lastVoice.duration),volume:100,enabled:true,speed:sp,sourceOffset:0});
    selectedLayer=layers.length-1;selected=-1;renderTimeline();loadLayerInspector();setStatus('Đã thêm voice vào timeline');
  };

  // Force Audio/Voice inspector speed to update layer immediately.
  const ls=q('lspeed');
  if(ls){
    const apply=()=>{
      if(selectedLayer<0||!layers[selectedLayer]||!['voice','audio'].includes(layers[selectedLayer].type))return;
      let v=parseFloat(ls.value);if(!Number.isFinite(v))v=1;v=Math.max(.25,Math.min(4,v));
      layers[selectedLayer].speed=v;ls.value=v;
      const lv=q('lspeedv');if(lv)lv.textContent=v.toFixed(2)+'x';
      if(typeof syncLayers==='function')syncLayers(!!playing);
    };
    ls.addEventListener('input',apply);ls.addEventListener('change',apply);
  }

  // Pre-buffer the next cut in a hidden second video so clip changes look less choppy.
  const frame=q('frame');
  let pre=q('nextPreview');
  if(frame&&!pre){
    pre=document.createElement('video');pre.id='nextPreview';pre.muted=true;pre.preload='auto';pre.playsInline=true;
    Object.assign(pre.style,{position:'absolute',inset:'0',width:'100%',height:'100%',objectFit:'contain',background:'#000',display:'none',zIndex:'2'});
    frame.insertBefore(pre,q('previewTextOverlay'));
  }
  let preparedIndex=-1,prepared=false,swapTimer=null;
  function prepareNext(i){
    if(!pre||i<0||i>=clips.length||preparedIndex===i)return;
    preparedIndex=i;prepared=false;
    try{
      if(pre.src!==video.src)pre.src=video.src;
      pre.playbackRate=Math.max(.25,Number(clips[i].speed)||1);
      pre.currentTime=Math.max(0,clips[i].start+.01);
    }catch(_){}
  }
  if(pre){pre.addEventListener('seeked',()=>{prepared=true})}

  const oldTick=window.tick;
  window.tick=function(){
    if(!playing)return;
    let c=clips[activeClip],st=starts(),tl=st[activeClip]+(video.currentTime-c.start)/c.speed;
    playhead=Math.max(st[activeClip],Math.min(st[activeClip]+outDur(c),tl));updatePlayhead();
    const remain=c.end-video.currentTime;
    if(activeClip+1<clips.length&&remain<.42)prepareNext(activeClip+1);
    if(video.currentTime>=c.end-.035){
      activeClip++;
      if(activeClip>=clips.length){pauseTimeline();playhead=totalDur();updatePlayhead();return}
      c=clips[activeClip];
      if(pre&&prepared&&preparedIndex===activeClip){
        pre.style.objectFit=(q('fit')?.value==='cover')?'cover':'contain';
        pre.style.transform=video.style.transform||'';pre.style.display='block';
        pre.playbackRate=Math.max(.25,Number(c.speed)||1);pre.play().catch(()=>{});
      }
      try{video.currentTime=c.start+.01}catch(_){}
      video.playbackRate=Math.max(.25,Number(c.speed)||1);applyVisual(c);
      const showMain=()=>{
        video.play().catch(()=>pauseTimeline());
        if(pre){clearTimeout(swapTimer);swapTimer=setTimeout(()=>{pre.pause();pre.style.display='none';prepared=false;preparedIndex=-1},120)}
      };
      if(video.readyState>=2)showMain();else video.addEventListener('canplay',showMain,{once:true});
    }
    syncLayers(true);raf=requestAnimationFrame(window.tick);
  };

  // Shortcut hint.
  const hint=document.querySelector('.card .status:last-child');
  const cards=[...document.querySelectorAll('.card')];
  const tlCard=cards.find(c=>c.querySelector('h3')?.textContent.trim()==='Timeline');
  if(tlCard){const s=tlCard.querySelector('.status');if(s)s.textContent='Q = cắt thừa đầu • E = cắt thừa đuôi • S = tách • Space = phát/dừng • Ctrl+Z = hoàn tác';}
})();
