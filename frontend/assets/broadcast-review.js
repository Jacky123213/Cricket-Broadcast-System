/* Finite review renderer shared by private preview and the clean program.
   All evidence is recorded media or explicitly labelled manual annotations. */
(function(root){'use strict';
 const labels={out:'OUT',not_out:'NOT OUT',not_given:'NOT GIVEN',inconclusive:'INCONCLUSIVE',not_assessed:'NOT ASSESSED',outside_off:'OUTSIDE OFF',outside_leg:'OUTSIDE LEG',in_line:'IN LINE',hitting:'HITTING',missing:'MISSING',uncertain:'UNCERTAIN'};
 const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 class ReviewOutput{
  constructor(mount,options={}){
   this.options=options;this.mount=mount;this.views=new Map();this.closed=false;this.ready=false;this.hasAudio=false;this.active=Boolean(options.private);this.muted=true;this.token=0;this.id=null;this.session=null;this.cache=null;this.request=null;this.loadState='loading';this.loadError='';this.lastFrame=null;this.drawing=false;this.guide=[];
   this.metrics=new root.DRSProgramHealth.PlaybackHealth();
   this.root=el('section','drs-surface');this.root.setAttribute('aria-label',options.private?'Private review preview':'Umpire review');this.root.dataset.visible=String(this.active);
   this.header=el('header','drs-heading');this.heading=el('strong','','UMPIRE REVIEW');this.original=el('span','drs-original');this.header.append(this.heading,this.original);
   this.body=el('div','drs-body');this.angles=el('div','drs-angles');this.assessment=el('aside','drs-lbw');this.body.append(this.angles,this.assessment);
   this.wave=el('section','drs-wave');this.waveTitle=el('strong','','AUDIO WAVEFORM');this.canvas=el('canvas');this.canvas.width=1000;this.canvas.height=90;this.wave.append(this.waveTitle,this.canvas,el('small','','Recorded microphone envelope · a spike is not proof of an edge'));
   this.footer=el('footer','drs-foot');this.kindLabel=el('span','drs-kind');this.reviewText=el('strong','drs-review-text','DECISION REVIEWED');this.time=el('span','drs-time');this.evidence=el('span','drs-evidence');this.footer.append(this.kindLabel,this.reviewText,this.time,this.evidence);
   this.decision=el('section','drs-decision');this.decision.hidden=true;this.decision.append(el('small','','UMPIRE DECISION · MANUALLY ENTERED'));this.verdict=el('strong');this.decision.append(this.verdict);
   this.busy=el('div','drs-processing');this.busy.setAttribute('role','status');this.busy.append(el('span','media-spinner'),el('strong','','Review processing'));this.progress=el('span');this.busy.append(this.progress);
   this.followNotice=el('p','drs-follow-notice');this.followNotice.hidden=true;this.root.dataset.private=String(Boolean(options.private));this.root.append(this.header,this.body,this.wave,this.footer,this.decision,this.busy,this.followNotice);mount.append(this.root);
   this.timer=setInterval(()=>this.tick(),100);this.reportTimer=setInterval(()=>this.report(),1000);
  }
  get player(){return this.views.get(this.session?.primary)?.player;}
  get audioVideo(){return this.views.get(this.session?.audio_source)?.player.active?.video;}
  videos(){return [...this.views.values()].flatMap(v=>v.player.slots.map(s=>s.video));}
  setOnAir(value){const previous=this.active;this.active=Boolean(value)||Boolean(this.options.private);if(this.active&&!previous)this.lastFrame=null;this.root.dataset.visible=String(this.active);if(!this.active)for(const v of this.views.values())v.player.pause();}
  async alignForAir(){
   if(this.aligning||this.airReady||!this.ready)return;this.aligning=true;const token=this.token;this.loadState='loading';
   try{for(const v of this.views.values())v.player.pause();const until=performance.now()+6000;while([...this.views.values()].some(v=>v.player.busy)){if(this.closed||token!==this.token)return;if(performance.now()>until)throw Error('Review decoder is still seeking');await new Promise(r=>setTimeout(r,30));}const at=this.manifest.start_ms+this.target(),required=this.required();const frames=await Promise.all([...this.views].filter(([id])=>required.has(id)).map(([,v])=>v.player.prepare(at)));if(this.closed||token!==this.token)return;if(frames.some(v=>!v))throw Error('Selected position has missing footage');this.airReady=true;this.loadState='ready';this.options.onReady?.();}
   catch(e){if(token===this.token&&!this.closed){this.loadState='error';this.loadError=e.message;this.options.onStatus?.('Cannot take review: '+e.message);}}
   finally{if(token===this.token){this.aligning=false;this.report();}}
  }
  setMuted(value){this.muted=Boolean(value);for(const [id,v] of this.views){v.player.muted=Boolean(this.options.private)||this.muted||id!==this.session?.audio_source;for(const s of v.player.slots)s.video.muted=v.player.muted;}}
  resume(){for(const v of this.views.values())v.player.retry();this.tick();}
  pauseForLinkLoss(){if(!this.session?.follow_controller||this.session.phase==='decision')return;const slot=this.player?.active,offset=slot?slot.clip.start_ms+slot.video.currentTime*1000-this.manifest.start_ms:this.target();this.update({...this.session,playing:false,position_ms:Math.max(0,offset),follow_status:'controller_lost'},this.serverTime,performance.now());this.tick();}
  target(){const s=this.session;return s?Math.min(s.duration_ms-1,Math.max(0,this.position+(s.playing?(performance.now()-this.anchor)*s.speed:0))):0;}
  required(){const s=this.session;return new Set([s?.primary,s?.layout==='split'?s.secondary||s.cameras.find(c=>c.id!==s.primary)?.id:null,s?.audio_source].filter(Boolean));}
  update(s,serverTime,local=performance.now()){
   if(this.closed)return;
   if(!s){this.reset();return;}
   const changed=s.id!==this.id,estimated=this.session?this.target():null;
   if(changed){this.reset();this.id=s.id;}
   this.force=changed||!this.session||this.session.primary!==s.primary||this.session.secondary!==s.secondary||this.session.playing!==s.playing||Math.abs((estimated??0)-s.position_ms)>180;
   this.session=s;this.position=s.position_ms;this.anchor=local;this.serverTime=serverTime;this.serverLocal=local;
   this.root.style.setProperty('--review-accent',/^#[\da-f]{6}$/i.test(s.color)?s.color:'#b8e34b');
   this.heading.textContent='UMPIRE REVIEW · '+s.label.toUpperCase();this.original.textContent='ORIGINAL DECISION · '+labels[s.original];
   this.kindLabel.textContent='DRS · '+s.label.toUpperCase();this.root.dataset.follow=String(Boolean(s.follow_controller));this.root.dataset.original=s.original;
   const colour=/^#[\da-f]{6}$/i.test(s.color)?s.color:'#b8e34b',rgb=[1,3,5].map(i=>parseInt(colour.slice(i,i+2),16));this.root.style.setProperty('--review-ink',rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722>150?'#101510':'#fff');
   this.root.dataset.layout=s.layout;this.root.dataset.kind=s.kind;
   this.wave.hidden=s.follow_controller?!s.show_waveform:s.kind!=='caught_behind';this.assessment.hidden=s.kind!=='lbw'||Boolean(s.follow_controller&&!s.show_assessment);this.original.hidden=Boolean(s.follow_controller&&!s.show_assessment&&s.phase!=='decision');
   if(s.kind==='lbw'){this.assessment.replaceChildren(el('small','','MANUAL ASSESSMENT · NOT BALL TRACKING'));for(const key of ['pitching','impact','wickets']){const row=el('div');row.append(el('small','',key.toUpperCase()),el('strong','',labels[s.lbw[key]]));this.assessment.append(row);}}
   this.decision.hidden=s.phase!=='decision';this.verdict.textContent=labels[s.verdict]||'';this.decision.dataset.verdict=s.verdict||'';
   const secondary=s.secondary||s.cameras.find(c=>c.id!==s.primary)?.id;
   for(const [id,v] of this.views){v.box.dataset.primary=String(id===s.primary);v.box.hidden=id!==s.primary&&(s.layout!=='split'||id!==secondary);v.box.style.order=id===s.primary?'0':'1';const z=s.zoom[id];v.layer.style.transform=`scale(${z.zoom})`;v.layer.style.transformOrigin=`${z.x*100}% ${z.y*100}%`;this.geometry(v,id);this.drawGuide(v,id);}
   this.followNotice.hidden=!s.follow_controller||s.follow_status==='ready'||s.phase==='decision';this.followNotice.textContent=s.follow_status==='controller_lost'?'Umpire controller disconnected · review paused on last received frame':'Umpire selecting / loading an angle · review paused';
   this.setMuted(this.muted);
   const waitingForUmpire=s.follow_controller&&s.follow_sequence<0;
   if(!waitingForUmpire&&(changed||!this.request&&!this.cache&&!this.ready&&this.loadState!=='error'))this.load(++this.token);
  }
  async load(token){
   this.ready=false;this.loadState='loading';this.loadError='';this.busy.hidden=false;this.progress.textContent='Downloading all recorded parts…';this.report();
   this.request=new AbortController();
   try{
    const r=await fetch('/api/broadcast/review',{cache:'no-store',signal:this.request.signal});if(!r.ok)throw Error('Review manifest unavailable');const data=await r.json();
    if(token!==this.token||this.closed)return;if(data.review?.id!==this.id)throw Error('Review has changed. Refresh the controls.');
    this.manifest=data.review.manifest;
    this.cache=new root.DRSClipCache(p=>{if(token===this.token)this.progress.textContent=`${p.completed}/${p.total} parts · ${(p.bytes/1048576).toFixed(1)} MB`;});
    const clips=await this.cache.load(this.manifest.clips);if(token!==this.token||this.closed)return;
    for(const camera of this.session.cameras){
     const box=el('article','drs-angle'),title=el('strong','drs-camera-name',camera.name),host=el('div','drs-viewport'),viewport=el('div','drs-crop'),layer=el('div','drs-image'),guide=document.createElementNS('http://www.w3.org/2000/svg','svg'),message=el('span','drs-angle-status');guide.setAttribute('viewBox','0 0 1000 1000');guide.setAttribute('preserveAspectRatio','none');guide.classList.add('drs-guide');layer.append(guide);viewport.append(layer);host.append(viewport,message);box.append(title,host);this.angles.append(box);
     const player=new root.DRSPlayback.AnglePlayer(clips.filter(c=>c.device_id===camera.id),()=>{const video=el('video');video.playsInline=true;video.preload='auto';video.muted=true;video.hidden=true;video.setAttribute('aria-label',camera.name+' recorded review');const play=video.play.bind(video);video.play=async()=>{try{return await play();}catch(e){if(e.name==='NotAllowedError'&&!video.muted&&!this.closed){this.setMuted(true);this.options.onMute?.();return play();}throw e;}};layer.prepend(video);return video;},text=>{if(token!==this.token)return;message.textContent=text;message.hidden=!text;},{seamless:true,onActive:video=>{if(camera.id===this.session?.audio_source)this.options.onAudioVideo?.(video);}});
     viewport.addEventListener('click',e=>this.clickGuide(e,camera.id,viewport));
     box.dataset.camera=camera.id;this.views.set(camera.id,{box,host,viewport,layer,guide,player,message});
    }
    const at=this.manifest.start_ms+this.target(),required=this.required();const prepared=await Promise.all([...this.views].map(async([id,v])=>{const clips=v.player.clips,point=required.has(id)||clips.some(c=>c.start_ms<=at&&at<c.end_ms)?at:Math.max(this.manifest.start_ms,clips[0]?.start_ms||at);const ok=await v.player.prepare(point);return !required.has(id)||ok;}));
    if(token!==this.token||this.closed)return;if(prepared.some(v=>!v))throw Error('No common recorded frame at this position. End and prepare a different window.');
    this.ready=true;this.loadState='ready';this.busy.hidden=true;this.update(this.session,this.serverTime,this.anchor);this.tick();this.report();this.options.onReady?.();
   }catch(e){if(token===this.token&&!this.closed){this.ready=false;this.loadState='error';this.loadError=e.message;for(const v of this.views.values())v.player.destroy();this.views.clear();this.cache?.destroy();this.progress.textContent='Review unavailable: '+e.message+' End this review and prepare again to retry.';this.busy.querySelector('.media-spinner').hidden=true;this.report();this.options.onStatus?.(this.progress.textContent);}}
  }
  fit(v){const video=v.player.video;return root.DRSPlayback.fit(video.videoWidth||16,video.videoHeight||9,v.viewport.clientWidth||16,v.viewport.clientHeight||9);}
  geometry(v,id){const aspect=this.session?.follow_controller?this.session.zoom[id]?.aspect:null;if(aspect&&v.host.clientWidth&&v.host.clientHeight){const r=root.DRSPlayback.fit(aspect,1,v.host.clientWidth,v.host.clientHeight);Object.assign(v.viewport.style,{left:r.x+'px',top:r.y+'px',width:r.width+'px',height:r.height+'px',right:'auto',bottom:'auto'});}else Object.assign(v.viewport.style,{left:'0',top:'0',right:'0',bottom:'0',width:'auto',height:'auto'});}
  drawGuide(v,id){
   const r=this.fit(v);Object.assign(v.guide.style,{left:r.x+'px',top:r.y+'px',width:r.width+'px',height:r.height+'px'});v.guide.replaceChildren();
   const crease=this.session?.crease;if(crease?.camera_id!==id)return;
   const line=document.createElementNS('http://www.w3.org/2000/svg','line'),[a,b]=crease.points;for(const [k,value] of Object.entries({x1:a[0]*1000,y1:a[1]*1000,x2:b[0]*1000,y2:b[1]*1000,stroke:'#f5d778','stroke-width':3,'vector-effect':'non-scaling-stroke'}))line.setAttribute(k,String(value));v.guide.append(line);
  }
  armGuide(){if(!this.options.private||!this.ready)return;this.drawing=true;this.guide=[];this.root.classList.add('drawing-crease');this.evidence.textContent='Tap two points along the crease in the primary angle · manual guide';}
  clickGuide(e,id,viewport){
   if(!this.drawing||id!==this.session?.primary)return;const v=this.views.get(id),rect=viewport.getBoundingClientRect(),r=this.fit(v),z=this.session.zoom[id];
   // Invert CSS zoom around the selected original-image anchor before mapping.
   const px=z.x*rect.width+(e.clientX-rect.left-z.x*rect.width)/z.zoom,py=z.y*rect.height+(e.clientY-rect.top-z.y*rect.height)/z.zoom;
   const point=[(px-r.x)/r.width,(py-r.y)/r.height];if(point.some(n=>!Number.isFinite(n)||n<0||n>1))return;this.guide.push(point);
   if(this.guide.length===2){this.drawing=false;this.root.classList.remove('drawing-crease');this.options.onGuide?.(this.guide);}
  }
  waveform(at){
   if(this.wave.hidden||!this.manifest)return;const ctx=this.canvas.getContext('2d'),s=this.session,w=this.canvas.width,h=this.canvas.height,points=this.manifest.audio?.[s.audio_source]||[];ctx.clearRect(0,0,w,h);ctx.strokeStyle='#9eaaa3';ctx.beginPath();ctx.moveTo(0,h/2);ctx.lineTo(w,h/2);ctx.stroke();
   ctx.strokeStyle='#b8e34b';ctx.beginPath();for(const p of points){const x=(p.t-this.manifest.start_ms)/s.duration_ms*w;ctx.moveTo(x,h/2-p.peak*40);ctx.lineTo(x,h/2+p.peak*40);}ctx.stroke();ctx.strokeStyle='#fff';const x=(at-this.manifest.start_ms)/s.duration_ms*w;ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();
   this.waveTitle.textContent=points.length?'AUDIO ENVELOPE':'NO AUDIO ANALYSIS';
  }
  tick(){
   if(this.closed||!this.ready||!this.session)return;const s=this.session,offset=this.target(),t=this.manifest.start_ms+offset,playing=this.active&&s.playing&&offset<s.duration_ms-1;
   for(const [id,v] of this.views){if(!this.aligning&&(this.active||this.force)&&this.required().has(id))v.player.update(t,playing,s.speed,this.force);this.geometry(v,id);this.drawGuide(v,id);}
   this.force=false;const slot=this.player?.active,audioSlot=this.views.get(s.audio_source)?.player.active;this.hasAudio=Boolean(audioSlot?.clip.audio);
   if(slot&&!slot.video.hidden&&slot.video.readyState>=2){const actual=slot.clip.start_ms+slot.video.currentTime*1000;
    this.time.textContent=(Math.max(0,actual-this.manifest.start_ms)/1000).toFixed(2)+' s · '+(playing?s.speed+'×':'PAUSED');
    if(!this.drawing)this.evidence.textContent=s.kind==='lbw'?'Manual assessment · no predicted trajectory':s.wicket_ms!==null?'WICKET BREAK · manually marked at '+(s.wicket_ms/1000).toFixed(2)+' s'+(s.crease?.points?' · manual crease guide':''):s.crease?.points?'MANUALLY ALIGNED CREASE GUIDE':'RECORDED REPLAY · gaps and camera timing uncertainty remain';
    this.waveform(this.views.get(s.audio_source)?.player.active?.clip?audioSlot.clip.start_ms+audioSlot.video.currentTime*1000:actual);
    if(!this.lastFrame||this.lastFrame.id!==slot.clip.id||Math.abs(this.lastFrame.at-actual)>1){this.lastFrame={id:slot.clip.id,at:actual};this.metrics.frame(actual,slot.video);if(this.active)this.options.onFrame?.({at:actual,delay:Math.max(0,(this.serverTime+performance.now()-this.serverLocal-actual)/1000),audio:this.hasAudio});}
   }
   for(const [id,v] of this.views)if(this.required().has(id)&&v.player.error){this.loadState='error';this.loadError=v.player.error;this.options.onStatus?.('Recorded review frame unavailable · '+v.player.error);}
   if(![...this.views].some(([id,v])=>this.required().has(id)&&v.player.error)&&this.ready){this.loadState='ready';this.loadError='';}
   this.metrics.errors(this.player);
  }
  healthSnapshot(now){return this.metrics.snapshot(this.manifest?.clips||[],now);}
  async report(){const s=this.session;if(!s||this.closed||!this.options.clientId)return;try{await fetch('/api/broadcast/review/ready',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({review_id:s.id,client_id:this.options.clientId,role:this.options.role||'browser',state:this.loadState,error:this.loadError.slice(0,200)}),signal:AbortSignal.timeout(2000)});}catch{/* Stale readiness is rejected by Take; never infer readiness from a failed report. */}}
  reset(){this.token++;this.request?.abort();this.request=null;for(const v of this.views.values())v.player.destroy();this.views.clear();this.cache?.destroy();this.cache=null;this.id=null;this.session=null;this.manifest=null;this.ready=false;this.airReady=false;this.aligning=false;this.lastFrame=null;this.angles.replaceChildren();this.busy.hidden=false;this.busy.querySelector('.media-spinner').hidden=false;this.decision.hidden=true;this.drawing=false;this.root.classList.remove('drawing-crease');this.root.dataset.visible=String(Boolean(this.options.private));}
  destroy(){if(this.closed)return;this.closed=true;clearInterval(this.timer);clearInterval(this.reportTimer);this.reset();this.root.remove();}
 }
 root.DRSReviewOutput=ReviewOutput;
})(window);
