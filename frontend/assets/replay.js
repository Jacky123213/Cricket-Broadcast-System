(function(){
 'use strict';
 const $=id=>document.getElementById(id),panel=$('replayPanel'),slider=$('replayPosition'),note=$('replayNote');
 new ResizeObserver(entries=>{document.documentElement.style.setProperty('--transport-height',entries[0].target.getBoundingClientRect().height+'px');}).observe($('replayTransport'));
 const views=new Map();let review=null,names=new Map(),playing=false,buffering=false,position=0,rate=1,anchor=0,anchorPosition=0,generation=0,program=null,preview=null,focused=null,lastThumb=0,lastDispatch=0;
 function current(){return review?Math.min(review.end_ms-review.start_ms-1,playing&&!buffering?anchorPosition+(performance.now()-anchor)*rate:position):0;}
 function pause(align=true){position=current();playing=false;buffering=false;for(const v of views.values())v.player.pause();$('replayState').textContent='PAUSED';if(align&&review)sync(true);return review?review.start_ms+position:null;}
 function play(){if(!review)return;buffering=false;for(const v of views.values())v.player.retry();if(position>=review.end_ms-review.start_ms-2)position=0;anchorPosition=position;anchor=performance.now();playing=true;$('replayState').textContent='PLAYING';sync(true);}
 function seek(ms){if(!review)return;pause(false);position=Math.max(0,Math.min(review.end_ms-review.start_ms-1,ms));sync(true);paint();}
 function sync(force=false){
  if(!review)return;const offset=current(),t=review.start_ms+offset;
  for(const v of views.values())v.player.update(t,playing&&!buffering,rate,force);
  const selected=[...views.entries()].filter(([id,v])=>id===program||id===preview||!v.player.muted).map(([,v])=>v.player);
  if(playing&&selected.some(p=>p.error)){pause(false);$('replayState').textContent='LOAD ERROR';note.textContent='A selected angle could not load this frame. Press Play to retry; no footage has been invented.';return;}
  if(playing&&selected.some(p=>p.waiting)){
   if(!buffering){position=offset;buffering=true;for(const v of views.values())v.player.pause();}
   $('replayState').textContent='BUFFERING';
  }else if(playing&&buffering){buffering=false;anchorPosition=position;anchor=performance.now();$('replayState').textContent='PLAYING';}
 }
 function exitFocus(){closePicker();$('focusAudio').hidden=true;focused=null;panel.classList.remove('focus-mode');document.body.classList.remove('angle-focused');for(const v of views.values())v.tile.classList.remove('is-focused');$('programSlot').classList.remove('focus-host');$('previewSlot').classList.remove('focus-host');$('exitFocus').hidden=true;if(document.fullscreenElement===panel)document.exitFullscreen?.().catch(()=>{});}
 async function focus(id){exitFocus();focused=id;const v=views.get(id);if(!v)return;panel.classList.add('focus-mode');document.body.classList.add('angle-focused');v.tile.classList.add('is-focused');v.tile.parentElement.classList.add('focus-host');$('exitFocus').hidden=false;setupFocusAudio(id,v.stage);try{await panel.requestFullscreen?.();}catch(e){note.textContent='Expanded view active; browser fullscreen unavailable.';}}
 document.addEventListener('fullscreenchange',()=>{if(!document.fullscreenElement&&focused)exitFocus();});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(!$('cameraPicker').hidden){e.stopImmediatePropagation();closePicker();}else exitFocus();}});
 let pickerSlot=null,pickerOpener=null;
 function closePicker(){if(!$('cameraPicker').hidden){$('cameraPicker').hidden=true;pickerOpener?.focus();}pickerSlot=null;}
 function chooseCamera(slot){
  if(!review)return;if(focused)exitFocus();pickerSlot=slot;pickerOpener=document.activeElement;
  $('pickerTitle').textContent='Choose camera for '+(slot==='preview'?'View 1':'View 2');
  const select=$('pickerCamera');select.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent='Empty slot';select.append(empty);
  for(const [id] of views){const option=document.createElement('option');option.value=id;const other=slot==='preview'?program:preview;option.textContent=(names.get(id)||id)+(other===id?' — move from other view':'');select.append(option);}
  select.value=(slot==='preview'?preview:program)||'';$('cameraPicker').hidden=false;select.focus();
 }
 $('pickerCancel').onclick=closePicker;
 $('pickerApply').onclick=()=>{const slot=pickerSlot;if(!slot)return;const id=$('pickerCamera').value||null;closePicker();if(slot==='preview'){if(id&&id===program)program=null;preview=id;}else{if(id&&id===preview)preview=null;program=id;}layout();};
 $('cameraPicker').addEventListener('keydown',e=>{if(e.key==='Tab'){const controls=[$('pickerCamera'),$('pickerApply'),$('pickerCancel')],i=controls.indexOf(document.activeElement);e.preventDefault();controls[(i+(e.shiftKey?2:1))%3].focus();}});
 $('previewEmpty').onclick=()=>chooseCamera('preview');$('programEmpty').onclick=()=>chooseCamera('program');
 function layout(){
  for(const [id,v] of views){v.tile.classList.remove('program-angle','preview-angle');v.thumb.classList.toggle('on-program',id===program);v.thumb.classList.toggle('on-preview',id===preview);$('angleParking').append(v.tile);}
  const slots=[['program',program],['preview',preview]];
  for(const [name,id] of slots){const v=views.get(id);$(name+'Empty').hidden=!!v;if(v){$(name+'Slot').append(v.tile);v.tile.classList.add(name+'-angle');v.badge.textContent=name==='preview'?'VIEW 1':'VIEW 2';}}
  sync();
 }
 function createView(id,clips){
  const tile=document.createElement('article');tile.className='replay-angle';
  const header=document.createElement('header');header.className='angle-header';const badge=document.createElement('span');badge.className='angle-badge';const title=document.createElement('strong');title.textContent=names.get(id)||id;const change=document.createElement('button');change.className='btn change-camera';change.textContent='Change camera';change.onclick=()=>chooseCamera(id===preview?'preview':'program');header.append(badge,title,change);
  const stage=document.createElement('div');stage.className='angle-viewport';const layer=document.createElement('div');layer.className='angle-layer';const canvas=document.createElement('canvas');canvas.className='detection-overlay';const message=document.createElement('div');message.className='angle-message';stage.append(layer,message);const toolbar=document.createElement('div');toolbar.className='angle-toolbar';
  const player=new window.DRSPlayback.AnglePlayer(clips,()=>{const video=document.createElement('video');video.playsInline=true;video.muted=true;video.preload='auto';video.hidden=true;layer.append(video);return video;},text=>{message.textContent=text;message.hidden=!text;});layer.append(canvas);
  const listen=document.createElement('button');listen.className='btn';listen.textContent='Listen';listen.onclick=()=>{const wasMuted=player.muted;for(const v of views.values()){v.player.muted=true;v.listen.textContent='Listen';for(const s of v.player.slots)s.video.muted=true;}player.muted=!wasMuted;listen.textContent=player.muted?'Listen':'Mute';if(!player.muted)play();};toolbar.append(listen);
  window.DRSViewControls(stage,layer,toolbar,()=>focus(id));tile.append(header,stage,toolbar);
  const thumb=document.createElement('article');thumb.className='angle-thumb';const image=document.createElement('canvas');image.width=320;image.height=180;const name=document.createElement('strong');name.textContent=title.textContent;const actions=document.createElement('div');
  actions.textContent='Tap an empty view or Change camera to select';thumb.append(image,name,actions);$('replayWall').append(thumb);
  const view={tile,stage,layer,canvas,player,badge,thumb,image,listen,label:message,get video(){return player.video;}};views.set(id,view);
 }
 async function leave(){generation++;pause(false);exitFocus();const old=review;panel.append($('focusAudio'));review=null;for(const v of views.values())v.player.destroy();views.clear();$('replayWall').replaceChildren();$('angleParking').replaceChildren();for(const s of ['previewSlot','programSlot'])$(s).querySelectorAll('.replay-angle').forEach(v=>v.remove());$('previewEmpty').hidden=false;$('programEmpty').hidden=false;program=preview=null;panel.hidden=true;document.body.classList.remove('replaying');$('cameraGrid').hidden=false;window.dispatchEvent(new CustomEvent('drs-review',{detail:null}));if(old)fetch('/api/replays/'+old.id,{method:'DELETE'}).catch(()=>{});}
 async function open(seconds,start,end){
  await leave();const token=++generation;panel.hidden=false;document.body.classList.add('replaying');$('cameraGrid').hidden=true;note.textContent='Preparing replay…';$('replayState').textContent='LOADING';panel.scrollIntoView({block:'start'});
  try{
   window.DRSFlushCameras?.();await new Promise(r=>setTimeout(r,1000));if(token!==generation)return;
   const query=new URLSearchParams({seconds});if(start!==undefined){query.set('start_ms',start);query.set('end_ms',end);}
   const r=await fetch('/api/replays?'+query,{method:'POST'}),data=await r.json();if(!r.ok)throw Error(data.detail);
   if(token!==generation){fetch('/api/replays/'+data.id,{method:'DELETE'}).catch(()=>{});return;}
   review=data;position=0;slider.max=data.end_ms-data.start_ms-1;
   const ids=[...new Set(data.clips.map(c=>c.device_id))];for(const id of ids)createView(id,data.clips.filter(c=>c.device_id===id));
   program=null;preview=null;layout();
   note.textContent=`${(data.live_delay_ms/1000).toFixed(1)} s behind live · timing approximate · gaps stay visible`;
   window.dispatchEvent(new CustomEvent('drs-review',{detail:data}));$('replayState').textContent='PAUSED';sync(true);paint();
  }catch(e){if(token===generation){note.textContent=e.message;$('replayState').textContent='UNAVAILABLE';}}
 }
 function muteAll(){for(const v of views.values()){v.player.muted=true;v.listen.textContent='Listen';for(const s of v.player.slots)s.video.muted=true;}}
 function setupFocusAudio(id,stage){
  const select=$('focusAudioSource');select.replaceChildren();
  const ids=new Set([...views.keys(),...Object.keys(review.audio||{})]);
  for(const source of ids){const o=document.createElement('option');o.value=source;o.textContent=(names.get(source)||source)+(review.audio?.[source]?.length?'':' (no waveform)');select.append(o);}
  select.value=id;stage.append($('focusAudio'));$('focusAudio').hidden=false;$('focusAudioListen').textContent='Listen to source';drawFocusAudio();
 }
 function drawFocusAudio(){
  if(!focused||!review)return;$('focusAudioListen').textContent=views.get($('focusAudioSource').value)?.player.muted===false?'Mute source':'Listen to source';const points=review.audio?.[$('focusAudioSource').value]||[],canvas=$('focusWaveform'),ctx=canvas.getContext('2d');
  ctx.clearRect(0,0,canvas.width,canvas.height);const x=t=>(t-review.start_ms)/(review.end_ms-review.start_ms)*canvas.width;
  ctx.strokeStyle='#74deb9';ctx.beginPath();for(const p of points){ctx.moveTo(x(p.t),32-p.peak*28);ctx.lineTo(x(p.t),32+p.peak*28);}ctx.stroke();
  ctx.strokeStyle='#ff9b75';ctx.beginPath();for(const p of points)if(p.impact){ctx.moveTo(x(p.t),0);ctx.lineTo(x(p.t),8);}ctx.stroke();
  ctx.strokeStyle='#fff';ctx.beginPath();ctx.moveTo(x(review.start_ms+current()),0);ctx.lineTo(x(review.start_ms+current()),64);ctx.stroke();
  $('focusAudioStatus').textContent=points.length?'Tap waveform to seek · '+(current()/1000).toFixed(2)+' s':'No recorded waveform for this source';
 }
 $('focusAudioSource').onchange=()=>{if($('focusAudioListen').textContent==='Mute source'){muteAll();const v=views.get($('focusAudioSource').value);if(v){v.player.muted=false;v.listen.textContent='Mute';}else $('focusAudioListen').textContent='Listen to source';}drawFocusAudio();};
 $('focusAudioListen').onclick=()=>{const listening=$('focusAudioListen').textContent==='Mute source';muteAll();$('focusAudioListen').textContent='Listen to source';if(!listening){const v=views.get($('focusAudioSource').value);if(v){v.player.muted=false;v.listen.textContent='Mute';$('focusAudioListen').textContent='Mute source';play();}else $('focusAudioStatus').textContent='No recorded video/audio clip for this source';}};
 $('focusWaveform').onclick=e=>{if(!review)return;const r=e.currentTarget.getBoundingClientRect();if(r.width)seek((e.clientX-r.left)/r.width*(review.end_ms-review.start_ms));};
 $('focusWaveform').onkeydown=e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();seek(current()+(e.key==='ArrowLeft'?-500:500));}};
 function paint(){if(!review)return;position=current();slider.value=position;$('replayTime').textContent=(position/1000).toFixed(2)+' / '+((review.end_ms-review.start_ms)/1000).toFixed(1)+' s';const now=performance.now();
  if(now-lastThumb>500){lastThumb=now;for(const v of views.values()){const ctx=v.image.getContext('2d'),video=v.video;ctx.fillStyle='#070b10';ctx.fillRect(0,0,320,180);if(!video.hidden&&video.readyState>=2&&video.videoWidth){const r=window.DRSPlayback.fit(video.videoWidth,video.videoHeight,320,180);ctx.drawImage(video,r.x,r.y,r.width,r.height);}else{ctx.fillStyle='#a6adb7';ctx.font='14px sans-serif';ctx.fillText('No frame available',80,90);}}}
  // Align overlays with the contained video image, including portrait footage.
  for(const v of views.values()){const video=v.video;if(!video.videoWidth)continue;const r=window.DRSPlayback.fit(video.videoWidth,video.videoHeight,v.stage.clientWidth,v.stage.clientHeight);Object.assign(v.canvas.style,{left:r.x+'px',top:r.y+'px',width:r.width+'px',height:r.height+'px'});}
  if(now-lastDispatch>160){lastDispatch=now;window.dispatchEvent(new CustomEvent('drs-position',{detail:{target:review.start_ms+position,views}}));}
  drawFocusAudio();
  if(playing&&position>=Number(slider.max))pause();
 }
 setInterval(()=>{if(review){sync();paint();}},100);
 $('returnLive').onclick=leave;$('exitFocus').onclick=exitFocus;$('replayPlay').onclick=play;$('replayPause').onclick=()=>pause();$('replayRestart').onclick=()=>seek(0);slider.oninput=()=>seek(Number(slider.value));
 $('replaySpeed').onchange=()=>{const wasPlaying=playing;pause(false);rate=Number($('replaySpeed').value);if(wasPlaying)play();};
 document.querySelectorAll('[data-replay-step]').forEach(b=>b.onclick=()=>seek(current()+Number(b.dataset.replayStep)));
 document.querySelectorAll('[data-replay-seconds]').forEach(b=>b.onclick=()=>open(Number(b.dataset.replaySeconds)));
 document.querySelectorAll('[data-pane]').forEach(b=>b.onclick=()=>{panel.dataset.pane=b.dataset.pane;document.querySelectorAll('[data-pane]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));});
 window.DRSReplay={pause,openWindow:(start,end)=>open(60,start,end),seek:t=>{if(review)seek(t-review.start_ms);}};
  async function bufferStatus(){
    try {
      const [r,d]=await Promise.all([fetch('/api/buffer'),fetch('/api/devices')]);
      if(!r.ok||!d.ok)throw Error('Status unavailable');
      const data=await r.json(),devices=(await d.json()).devices;
      window.dispatchEvent(new CustomEvent('drs-audio',{detail:data.audio||{}}));
      names=new Map(devices.map(v=>[v.device_id,v.name]));
      const box=document.getElementById('bufferStatus');box.replaceChildren();
      for(const [id,c] of Object.entries(data.cameras)){
        const row=document.createElement('p');const lag=(data.server_ms-c.end_ms)/1000;
        row.textContent=`${names.get(id)||id}: ${c.seconds.toFixed(0)} s buffered · latest ${lag.toFixed(1)} s ago · offset ${c.offset_ms.toFixed(1)} ms · network ±${c.uncertainty_ms.toFixed(1)} ms${lag>12?' · STALE':''}`;box.append(row);
      }
      for(const [id,r] of Object.entries(data.recorders||{})) {
        const row=document.createElement('p');row.textContent=(names.get(id)||id)+': '+r.message;box.append(row);
      }
      if(!box.children.length) box.textContent='No recorder has reported yet. On the phone press Start/retry replay.';
    }catch(e){document.getElementById('bufferStatus').textContent=e.message;}
  }
 bufferStatus();setInterval(bufferStatus,3000);
})();
