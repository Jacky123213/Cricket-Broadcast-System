/* Finite, fully preloaded wicket reel. The server filters match/innings/kind. */
window.CricketFieldingReel=class{
 constructor(program,mount,options={}){
  this.options=options;this.closed=false;this.ready=false;this.hasAudio=false;this.clips=[];this.metrics=new window.DRSProgramHealth.PlaybackHealth();this.item=-1;this.muted=true;this.lastFrame=null;
  this.root=document.createElement('div');this.root.className='fielding-reel';mount.append(this.root);
  this.caption=document.createElement('aside');this.caption.className='fielding-caption';this.caption.hidden=true;this.badge=document.createElement('aside');this.badge.className='fielding-break';this.root.append(this.caption,this.badge);
  this.loading=document.createElement('div');this.loading.className='fielding-processing';this.loading.textContent='Loading fielding-side wicket highlights…';this.root.append(this.loading);
  this.cache=new window.DRSClipCache(p=>this.loading.textContent=`Loading fielding highlights · ${p.completed}/${p.total} parts · ${(p.bytes/1048576).toFixed(1)} MB`);
  this.player=new window.DRSPlayback.AnglePlayer([],()=>{const v=document.createElement('video');v.className='program-video';v.playsInline=true;v.preload='auto';v.hidden=true;v.muted=true;const native=v.play.bind(v);v.play=async()=>{try{return await native();}catch(e){if(e.name==='NotAllowedError'&&!v.muted&&!this.closed){this.setMuted(true);options.onMute?.();return native();}throw e;}};this.root.prepend(v);return v;},text=>{if(text)options.onStatus?.(text);},{seamless:true,onActive:v=>options.onAudioVideo?.(v)});
  this.apply(program,performance.now());this.timer=setInterval(()=>this.tick(),100);this.load();
 }
 get audioVideo(){return this.player.active?.video;}
 videos(){return this.player.slots.map(s=>s.video);}
 apply(program,local){const estimated=this.program?this.target():null;this.force=!this.program||this.program.playing!==program.playing||Math.abs((estimated??0)-program.position_ms)>200;this.program=program;this.position=program.position_ms;this.anchor=local;}
 target(){return Math.min(this.program.review.end_ms-1,Math.max(0,this.position+(this.program.playing?(performance.now()-this.anchor)*this.program.speed:0)));}
 async load(){try{this.clips=await this.cache.load(this.program.review.clips);if(this.closed)return;this.player.clips=this.clips.filter(c=>c.reel_item===0);if(!await this.player.prepare(0))throw Error('The first wicket clip could not be decoded');if(this.closed)return;this.ready=true;this.loading.hidden=true;this.tick();}catch(e){if(!this.closed){this.player.error=e.message;this.loading.textContent='Highlights unavailable · '+e.message+' · Return to live to leave the reel.';this.options.onStatus?.(this.loading.textContent);}}}
 text(tag,text){const e=document.createElement(tag);e.textContent=text;return e;}
 details(item){const r=this.program.review;this.caption.replaceChildren(this.text('small','FIELDING HIGHLIGHTS · '+r.fielding_team),this.text('strong',(item.batter||'WICKET')+(item.runs!==null&&item.runs!==undefined?'  '+item.runs+' ('+(item.balls??'—')+')':'')),this.text('span',item.dismissal||item.title));this.caption.style.borderColor=r.fielding_color;this.badge.replaceChildren();if(r.batting_logo){const img=document.createElement('img');img.src=r.batting_logo;img.alt='';this.badge.append(img);}const copy=this.text('div','');copy.append(this.text('small','INNINGS BREAK'),this.text('strong',r.batting_team),this.text('b',r.total));this.badge.style.color=r.batting_color;this.badge.append(copy);this.caption.hidden=false;}
 tick(){if(this.closed||!this.ready)return;const p=this.program,t=this.target(),item=p.review.items.findIndex(i=>i.start_ms<=t&&t<i.end_ms);if(item!==this.item&&item>=0){this.item=item;this.player.clips=this.clips.filter(c=>c.reel_item===item);this.force=true;}this.player.update(t,p.playing&&t<p.review.end_ms-1,p.speed,this.force);this.force=false;const slot=this.player.active;this.metrics.errors(this.player);if(slot&&!slot.video.hidden&&slot.video.readyState>=2){const actual=slot.clip.start_ms+slot.video.currentTime*1000;if(!this.lastFrame||this.lastFrame.id!==slot.clip.id||Math.abs(this.lastFrame.at-actual)>1){this.lastFrame={id:slot.clip.id,at:actual};this.metrics.frame(actual,slot.video);this.options.onFrame?.({at:actual,delay:0,audio:slot.clip.audio});}this.hasAudio=Boolean(slot.clip.audio);const shown=p.review.items[slot.clip.reel_item];if(shown)this.details(shown);}}
 setMuted(value){this.muted=value;this.player.muted=value;for(const s of this.player.slots)s.video.muted=value;}
 resume(){this.player.retry();this.tick();}
 healthSnapshot(now){return this.metrics.snapshot(this.clips,now);}
 destroy(){this.closed=true;clearInterval(this.timer);this.cache.destroy();this.player.destroy();this.root.remove();}
};
