/* Shared Match Day output. Fixed-camera /broadcast URLs keep their legacy path. */
(function(){
  'use strict';
  const params=new URLSearchParams(location.search);if(params.get('follow')!=='1')return;
  const $=id=>document.getElementById(id),role=params.get('client')==='obs'?'obs':params.get('client')==='preview'?'preview':'browser',silent=role==='preview'||params.get('audio')==='0';
  const clientId=role+'-'+window.DRS.createClientId(),meter=new window.DRSProgramHealth.AudioMeter();
  let state=null,engine=null,key='',closed=false,blocked=false,meterRequested=false,pollTimer=null,reportTimer=null,graphics={kind:null,surge:false},programError=false;
  $('controls').hidden=params.get('clean')==='1';$('program').hidden=true;$('graphic').src='/overlay?program=1';
  function empty(title,detail=''){const box=$('empty');box.querySelector('strong').textContent=title;box.querySelector('span').textContent=detail;box.hidden=false;}
  function muted(){return silent||Boolean(state?.muted)||blocked;}
  function audioSettings(){if(!engine)return;meter.select?.(engine.player.active?.video||null);meter.mute(muted());const managed=!blocked&&meter.context?.state==='running'&&videos().every(v=>meter.nodes.has(v));engine.setMuted(managed?false:muted());$('mute').textContent=state?.muted?'Unmute program audio':'Mute program audio';}
  function videos(){return engine?.player?.slots.map(s=>s.video)||[];}
  async function enableMeter(){const list=videos();if(!list.length)return false;meterRequested=true;const active=await meter.start(list);if(closed)return false;const suspended=!active&&meter.context?.state==='suspended';$('audioNotice').hidden=active||silent||!suspended;if(suspended){blocked=true;$('audioNotice').textContent='Retry enabling audio / meter · OBS Interact';}if(active)blocked=false;audioSettings();if(active)engine?.resume?.();return active;}
  function onMute(){blocked=true;$('audioNotice').hidden=false;$('audioNotice').textContent='Enable camera audio / meter · open OBS Interact';audioSettings();}
  function frame(f){if(!engine)return;engine.hasAudio=Boolean(f.audio);$('empty').hidden=true;$('status').textContent=state?.mode==='replay'?'REPLAY · '+(state.playing?'PLAYING':'PAUSED'):'DELAYED '+f.delay.toFixed(1)+' s';$('sound').textContent=engine.hasAudio?(muted()?'Audio track received · muted here':'Audio track received · meter needed to verify activity'):'No audio track in displayed clip';
    if(engine.hasAudio&&!meterRequested&&!silent&&!blocked){$('audioNotice').hidden=false;$('audioNotice').textContent='Enable program audio meter · OBS Interact (setup)';}
    if(state?.mode==='live')$('graphic').contentWindow?.postMessage({type:'broadcast-time',at:f.at/1000},location.origin);
  }
  class ReplayOutput {
    constructor(program,local){this.closed=false;this.hasAudio=false;this.metrics=new window.DRSProgramHealth.PlaybackHealth();this.clips=program.review.clips.filter(c=>c.device_id===program.camera_id);this.player=new window.DRSPlayback.AnglePlayer(this.clips,()=>{const v=document.createElement('video');v.className='program-video';v.playsInline=true;v.preload='auto';v.hidden=true;v.muted=true;v.setAttribute('aria-label','Shared program replay');const native=v.play.bind(v);v.play=async()=>{try{return await native();}catch(e){if(e.name==='NotAllowedError'&&!v.muted&&!this.closed){this.setMuted(true);onMute();return native();}throw e;}};$('bufferedStage').append(v);return v;},text=>{if(text)$('status').textContent=text;},{onActive:video=>meter.select?.(video)});this.lastFrame=null;this.apply(program,local);this.timer=setInterval(()=>this.tick(),100);}
    apply(program,local){const estimated=this.program?this.target():null,changed=!this.program||this.program.playing!==program.playing||Math.abs((estimated??0)-program.position_ms)>250;this.program=program;this.anchor=local;this.position=program.position_ms;this.force=changed;}
    target(){const p=this.program;return Math.min(p.review.end_ms-p.review.start_ms-1,Math.max(0,this.position+(p.playing?(performance.now()-this.anchor)*p.speed:0)));}
    tick(){if(this.closed)return;const p=this.program,offset=this.target(),at=p.review.start_ms+offset,playing=p.playing&&offset<p.review.end_ms-p.review.start_ms-1;this.player.update(at,playing,p.speed,this.force);this.force=false;this.metrics.errors(this.player);const slot=this.player.active;
      if(slot&&!slot.video.hidden&&slot.video.readyState>=2){const actual=slot.clip.start_ms+slot.video.currentTime*1000;if(!this.lastFrame||this.lastFrame.id!==slot.clip.id||Math.abs(actual-this.lastFrame.at)>1){this.lastFrame={id:slot.clip.id,at:actual};this.metrics.frame(actual,slot.video);frame({at:actual,delay:Math.max(0,(Date.now()-actual)/1000),audio:slot.clip.audio});}this.hasAudio=Boolean(slot.clip.audio);}
      if(playing&&(this.metrics.frameLocal===null||performance.now()-this.metrics.frameLocal>750))empty('Replay footage unavailable / buffering','Missing or undecodable frames are not replaced with invented footage. Return to live to leave the replay.');
    }
    setMuted(value){this.player.muted=value;for(const s of this.player.slots)s.video.muted=value;}
    resume(){this.player.retry();this.tick();}
    healthSnapshot(now){return this.metrics.snapshot(this.clips,now);}
    destroy(){this.closed=true;clearInterval(this.timer);this.player.destroy();}
  }
  function stop(){engine?.destroy();engine=null;meter.reset();graphics={kind:null,surge:false};}
  function apply(data,midpoint){const p=data.program,roster=data.devices;state=p;programError=false;
    const choices=p.mode==='replay'?[...new Set(p.review.clips.map(c=>c.device_id))]:roster.map(d=>d.device_id),rows=choices.map(id=>Object.assign(document.createElement('option'),{value:id,textContent:roster.find(d=>d.device_id===id)?.name||id}));if(!choices.includes(p.camera_id))rows.unshift(Object.assign(document.createElement('option'),{value:p.camera_id||'',textContent:p.camera_id?'Selected camera offline':'Waiting for cameras…'}));const optionKey=JSON.stringify(rows.map(r=>[r.value,r.textContent]));if($('camera').dataset.rows!==optionKey){$('camera').dataset.rows=optionKey;$('camera').replaceChildren(...rows);}$('camera').value=p.camera_id||'';$('camera').disabled=!choices.length;
    const nextKey=[p.mode,p.camera_id,p.review_id,p.retry_token].join('|'),available=p.mode==='replay'?choices.includes(p.camera_id):roster.some(d=>d.device_id===p.camera_id);
    $('graphic').hidden=p.mode==='replay'||!$('showGraphic').checked;$('replayBadge').hidden=p.mode!=='replay';
    if(p.mode==='replay')$('graphic').contentWindow?.postMessage({type:'broadcast-suspend'},location.origin);
    if(nextKey!==key||!available&&engine){stop();key=nextKey;}
    if(!available){empty(p.camera_id?'Selected program camera offline':'Waiting for a program camera','Use Match Day to select a connected camera.');$('status').textContent='OFFLINE';return;}
    if(!engine){empty(p.mode==='replay'?'Loading program replay':'Buffering delayed program','Waiting for decoded camera footage.');
      if(p.mode==='live'){engine=new window.DRSBufferedBroadcast(p.camera_id,$('bufferedStage'),{onFrame:frame,onVideo:video=>meter.select?.(video),onMute,onStatus:message=>{$('status').textContent=message;},onBuffering:()=>empty('Program buffering','Waiting for the next decoded clip. Check the camera recorder and network.')});engine.hasAudio=false;}
      else {engine=new ReplayOutput(p,midpoint);engine.tick();}
      if(meterRequested)enableMeter().catch(()=>{});
    }else if(p.mode==='replay')engine.apply(p,midpoint);
    audioSettings();
  }
  let clock={server:Date.now(),local:performance.now()};
  function now(){return clock.server+performance.now()-clock.local;}
  async function poll(){if(closed)return;const began=performance.now();try{const r=await fetch('/api/broadcast/program',{cache:'no-store',signal:AbortSignal.timeout(3000)});if(!r.ok)throw Error('HTTP '+r.status);const data=await r.json();if(closed)return;const midpoint=(began+performance.now())/2;clock={server:data.server_ms,local:midpoint};apply(data,midpoint);}catch(e){if(!closed){programError=true;$('status').textContent='Program control link lost · '+e.message;}}finally{if(!closed)pollTimer=setTimeout(poll,750);}}
  function report(){const h=engine?.healthSnapshot(now())||{},video=engine?.player.active?.video,local=performance.now(),lastAge=h.last_frame_age_ms,decoded=video&&!video.hidden&&video.readyState>=2;
    const atEnd=state?.mode==='replay'&&engine?.target?.()>=state.review.end_ms-state.review.start_ms-1;
    const playback=!engine?'offline':programError?'error':state.mode==='replay'&&(!state.playing||atEnd)&&decoded&&engine.player.ready&&!engine.player.waiting&&!engine.player.error?'paused':lastAge!==null&&lastAge!==undefined&&lastAge<750&&decoded?'playing':'buffering';
    const sample=engine&&decoded?meter.sample(video,engine.hasAudio):{meter_state:'unavailable',meter_dbfs:null};
    const result={client_id:clientId,role,camera_id:state?.camera_id||'',revision:state?.revision||0,mode:state?.mode||'live',state:playback,...h,muted:muted(),audio_present:Boolean(engine?.hasAudio),...sample,graphics_kind:state?.mode==='replay'?'hidden':graphics.kind,graphics_surge:state?.mode==='live'&&graphics.surge};
    // A stopped/hidden player cannot leave a falsely active audio meter behind.
    if(playback!=='playing'){result.meter_state='unavailable';result.meter_dbfs=null;}
    if(blocked){result.meter_state='suspended';result.meter_dbfs=null;}
    if(result.last_frame_age_ms>3600000)result.last_frame_age_ms=null;
    if(result.delay_seconds>3600)result.delay_seconds=null;
    return result;
  }
  async function sendReport(){if(closed)return;try{await fetch('/api/broadcast/health',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(report()),signal:AbortSignal.timeout(2000)});}catch{/* A missing heartbeat becomes stale at the desk; never mark it healthy locally. */}finally{if(!closed)reportTimer=setTimeout(sendReport,1000);}}
  async function command(body){try{const r=await fetch('/api/broadcast/program',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(5000)});const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Command rejected');if(!closed)apply(data,performance.now());}catch(e){$('status').textContent=e.message;}}
  $('camera').onchange=()=>command({action:'camera',camera_id:$('camera').value});$('controls').onsubmit=e=>e.preventDefault();$('retry').onclick=()=>command({action:'retry'});$('mute').onclick=()=>command({action:'audio',muted:!state?.muted});$('audioNotice').onclick=()=>{blocked=false;enableMeter().then(()=>{audioSettings();engine?.resume?.();});};
  $('showGraphic').onchange=()=>{$('graphic').hidden=state?.mode==='replay'||!$('showGraphic').checked;};
  $('copyOutput').onclick=async()=>{const url=new URL(location.href);url.search='?follow=1&clean=1&client=obs&audio=1';try{await navigator.clipboard.writeText(url.href);$('copyOutput').textContent='Shared OBS link copied';}catch{$('status').textContent=url.href;}};
  window.addEventListener('message',e=>{if(e.source===$('graphic').contentWindow&&e.origin===location.origin&&e.data?.type==='broadcast-graphics-status'){graphics={kind:e.data.kind,surge:Boolean(e.data.surge)};}});
  window.CricketProgram={enableMeter,health:report};
  window.addEventListener('beforeunload',()=>{closed=true;clearTimeout(pollTimer);clearTimeout(reportTimer);stop();meter.close();});
  poll();sendReport();
})();
