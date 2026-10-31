(()=>{
  const q=id=>document.getElementById(id);
  const style=document.createElement('style');
  style.textContent=`
  #previewTextOverlay.fx-fade{animation:textFade .45s ease both}
  #previewTextOverlay.fx-pop{animation:textPop .35s ease both}
  #previewTextOverlay.fx-slide{animation:textSlide .4s ease both}
  @keyframes textFade{from{opacity:0}to{opacity:1}}
  @keyframes textPop{from{opacity:0;transform:scale(.72)}to{opacity:1;transform:scale(1)}}
  @keyframes textSlide{from{opacity:0;transform:translateY(28px)}to{opacity:1;transform:translateY(0)}}`;
  document.head.appendChild(style);

  function addTextControls(){
    const ed=q('layerEditor');if(!ed||q('textStylePanel'))return;
    const panel=document.createElement('div');panel.id='textStylePanel';panel.style.display='none';
    panel.innerHTML=`
      <div class="row"><label>Size</label><input id="tFontSize" type="number" min="12" max="120" step="1" value="28"></div>
      <div class="row"><label>Màu</label><input id="tColor" type="color" value="#ffffff"><label>Viền</label><input id="tStroke" type="color" value="#000000"></div>
      <div class="row"><label>Vị trí</label><select id="tPos"><option value="top">Trên</option><option value="center">Giữa</option><option value="bottom" selected>Dưới</option></select></div>
      <div class="row"><label>Hiệu ứng</label><select id="tFx"><option value="none">Không</option><option value="fade">Fade</option><option value="pop">Pop</option><option value="slide">Slide Up</option></select></div>`;
    const textRow=q('textRow'); if(textRow) textRow.insertAdjacentElement('afterend',panel); else ed.appendChild(panel);
    ['tFontSize','tColor','tStroke','tPos','tFx'].forEach(id=>q(id)?.addEventListener('input',()=>applyTextStyle(true)));
    q('ltext')?.addEventListener('input',()=>applyTextStyle(true));
  }

  function normalizeTextLayer(L){
    if(!L)return L;
    if(L.fontSize==null)L.fontSize=28;
    if(!L.color)L.color='#ffffff';
    if(!L.stroke)L.stroke='#000000';
    if(!L.position)L.position='bottom';
    if(!L.effect)L.effect='none';
    return L;
  }

  window.applyTextStyle=function(render=false){
    if(selectedLayer<0||!layers[selectedLayer]||layers[selectedLayer].type!=='text')return;
    const L=normalizeTextLayer(layers[selectedLayer]);
    if(q('ltext')){L.text=q('ltext').value;L.name=L.text}
    if(q('tFontSize'))L.fontSize=Math.max(12,Math.min(120,parseFloat(q('tFontSize').value)||28));
    if(q('tColor'))L.color=q('tColor').value;
    if(q('tStroke'))L.stroke=q('tStroke').value;
    if(q('tPos'))L.position=q('tPos').value;
    if(q('tFx'))L.effect=q('tFx').value;
    if(render&&typeof renderTimeline==='function')renderTimeline();
    if(typeof updateTextOverlay==='function')updateTextOverlay();
  };

  const oldLoad=window.loadLayerInspector;
  if(typeof oldLoad==='function')window.loadLayerInspector=function(render=true){
    oldLoad(render); addTextControls();
    const p=q('textStylePanel');
    if(selectedLayer<0||!layers[selectedLayer]){if(p)p.style.display='none';return}
    const L=layers[selectedLayer];
    if(L.type!=='text'){if(p)p.style.display='none';return}
    normalizeTextLayer(L); if(p)p.style.display='block';
    q('ltext').value=L.text||'';q('tFontSize').value=L.fontSize;q('tColor').value=L.color;q('tStroke').value=L.stroke;q('tPos').value=L.position;q('tFx').value=L.effect;
  };

  const oldAdd=window.addText;
  window.addText=function(){
    const text=prompt('Nội dung text:','ƯU ĐIỂM NỔI BẬT ✨');if(!text)return;
    if(typeof pushHistory==='function')pushHistory();
    layers.push({id:'t'+Date.now(),type:'text',text,name:text,start:playhead,end:Math.min(totalDur(),playhead+3),enabled:true,fontSize:28,color:'#ffffff',stroke:'#000000',position:'bottom',effect:'fade'});
    selectedLayer=layers.length-1;selected=-1;renderTimeline();loadLayerInspector();updateTextOverlay();
  };

  window.updateTextOverlay=function(){
    const el=q('previewTextOverlay'); if(!el)return;
    let active=null;
    for(const L0 of layers){const L=normalizeTextLayer(L0);if(L.type==='text'&&L.enabled!==false&&playhead>=L.start&&playhead<L.end)active=L}
    if(!active){el.textContent='';el.className='';return}
    el.textContent=active.text||active.name||'';
    el.style.color=active.color;el.style.fontSize=(active.fontSize||28)+'px';
    el.style.webkitTextStroke=`2px ${active.stroke||'#000000'}`;el.style.textShadow='0 2px 8px #000';
    el.style.top='';el.style.bottom='';el.style.transform='';
    if(active.position==='top'){el.style.top='8%';el.style.bottom='auto'}
    else if(active.position==='center'){el.style.top='50%';el.style.bottom='auto';el.style.transform='translateY(-50%)'}
    else{el.style.bottom='8%'}
    el.className=active.effect&&active.effect!=='none'?'fx-'+active.effect:'';
  };

  addTextControls();
})();
