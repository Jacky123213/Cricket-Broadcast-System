/* Native playback with two decoder slots per angle. No global seek loop. */
(function(root){
 'use strict';
 function fit(sw,sh,w,h){const s=Math.min(w/sw,h/sh);return {x:(w-sw*s)/2,y:(h-sh*s)/2,width:sw*s,height:sh*s};}
 function wait(video,event,action){return new Promise((resolve,reject)=>{let timer;const done=e=>{clearTimeout(timer);video.removeEventListener(event,ok);video.removeEventListener('error',bad);video.removeEventListener('drs-cancel',cancel);e?reject(e):resolve();};const ok=()=>done(),bad=()=>done(Error('Clip could not be decoded')),cancel=()=>done(Error('Player closed'));video.addEventListener(event,ok);video.addEventListener('error',bad);video.addEventListener('drs-cancel',cancel);timer=setTimeout(()=>done(Error('Clip loading timed out')),6000);try{action();}catch(e){done(e);}});}
 function presented(video){
  if(typeof video.requestVideoFrameCallback!=='function')return Promise.resolve();
  return new Promise((resolve,reject)=>{
   let callback,timer,finished=false;
   const done=error=>{if(finished)return;finished=true;clearTimeout(timer);if(callback!==undefined)video.cancelVideoFrameCallback?.(callback);video.removeEventListener('error',bad);video.removeEventListener('drs-cancel',cancel);error?reject(error):resolve();};
   const bad=()=>done(Error('Clip could not be decoded')),cancel=()=>done(Error('Player closed'));
   video.addEventListener('error',bad);video.addEventListener('drs-cancel',cancel);
   timer=setTimeout(()=>done(Error('Camera decoder did not present a frame')),3000);
   callback=video.requestVideoFrameCallback(()=>done());
   // Warm the replacement silently behind the outgoing video. canplay and
   // loadeddata are not proof that Safari has submitted a displayed frame.
   video.muted=true;video.play().catch(done);
  });
 }
 class AnglePlayer{
  constructor(clips,makeVideo,status=()=>{},options={}){this.clips=clips;this.status=status;this.continuous=Boolean(options.continuous);this.onActive=options.onActive||(()=>{});this.slots=[0,1].map(()=>({video:makeVideo(),clip:null,promise:null}));this.active=null;this.desired=null;this.busy=false;this.closed=false;this.lastCorrection=0;this.failures=new Map();this.muted=true;this.ready=false;this.playing=false;this.waiting=false;this.error=null;}
  get video(){return this.active?.video||this.slots[0].video;}
  end(slot){return Math.min(slot.clip.end_ms,Number.isFinite(slot.video.duration)?slot.clip.start_ms+slot.video.duration*1000:Infinity);}
  covers(slot,t){return slot?.clip&&slot.clip.start_ms<=t&&t<this.end(slot);}
  async load(slot,clip){
   if(slot.clip?.id===clip.id){if(slot.promise)await slot.promise;return;}
   if(slot.promise)await slot.promise.catch(()=>{});
   if(this.closed)return;
   slot.clip=clip;slot.preparedFor=null;slot.requestedRate=null;slot.video.pause();slot.video.hidden=!this.continuous;if(slot.video.style)slot.video.style.zIndex='0';
   // Keep ownership until data is decoded, not just until metadata arrives.
   // Replacing src during this wait cancels Safari's in-flight media request.
   slot.promise=(async()=>{await wait(slot.video,'loadedmetadata',()=>{slot.video.src=clip.url;slot.video.load();});if(slot.video.readyState<2)await wait(slot.video,'loadeddata',()=>{});})();
   try{await slot.promise;}catch(e){slot.clip=null;throw e;}finally{slot.promise=null;}
  }
  async seek(slot,t){if(slot.preparing)await slot.preparing;const seconds=Math.max(0,(t-slot.clip.start_ms)/1000);if(Math.abs(slot.video.currentTime-seconds)>.025)await wait(slot.video,'seeked',()=>{slot.video.currentTime=seconds;});if(slot.video.readyState<2)await wait(slot.video,'loadeddata',()=>{});}
  play(slot){slot.video.muted=this.muted;if(slot.video.paused&&!slot.playPromise){slot.playPromise=slot.video.play().catch(e=>this.status('Tap Play to resume: '+e.message)).finally(()=>{slot.playPromise=null;});}}
  update(t,playing,rate=1,force=false){this.playing=playing;this.desired={t,playing,rate,force:force||this.desired?.force};if(!this.busy)this.pump();}
  async pump(){
   if(this.closed||!this.desired)return;this.busy=true;const request=this.desired;this.desired=null;
   let {t,rate,force}=request;
   try{
    if(!this.covers(this.active,t)){
     this.ready=false;this.waiting=true;this.error=null;this.status('Loading next frame…');
     if(this.active&&!this.continuous)this.active.video.pause();
     const candidates=[...this.clips].reverse().filter(c=>c.start_ms<=t&&t<c.end_ms&&(this.failures.get(c.id)||0)<Date.now());
     // An overlapping newer clip is not a reason to discard footage already
     // being downloaded and prepared for this boundary.
     if(this.continuous&&!force){const priority=c=>this.slots.some(s=>s!==this.active&&s.clip?.id===c.id&&(s.preparing||s.preparedFor===c.id))?0:1;candidates.sort((a,b)=>priority(a)-priority(b));}
     let chosen=null;
     for(const clip of candidates){
      const slot=this.slots.find(s=>s.clip?.id===clip.id)||this.slots.find(s=>s!==this.active)||this.slots[0];
      try{
       // Foreground handover and background preloading share two decoders.
       // Never swap a decoder's source while its preparation still owns it.
       if(slot.preparing)await slot.preparing;
       await this.load(slot,clip);if(this.closed)return;
       if(this.continuous&&!force&&this.desired&&!this.desired.force){
        // If downloading took longer than this clip's whole remaining window,
        // let the queued current request choose footage instead of briefly
        // playing an expired clip and immediately loading another one.
        if(!this.covers(slot,this.desired.t))return;
        t=this.desired.t;rate=this.desired.rate;this.desired=null;
       }
       if(!this.covers(slot,t))continue;
       const prepared=this.continuous&&!force&&slot.preparedFor===clip.id&&Math.abs(clip.start_ms+slot.video.currentTime*1000-t)<=250;
       if(!prepared)await this.seek(slot,t);
       if(this.playing&&slot.video.readyState<3)await wait(slot.video,'canplay',()=>{});
       if(this.continuous&&this.playing&&slot!==this.active)await presented(slot.video);
       if(this.closed)return;
       chosen=slot;break;
      }catch(e){this.failures.set(clip.id,Date.now()+10000);this.error=e.message;this.status(e.message);}
     }
     if(!chosen){if(this.active){this.active.video.pause();if(!this.continuous)this.active.video.hidden=true;}const exists=this.clips.some(c=>c.start_ms<=t&&t<c.end_ms);this.error=exists?(this.error||'Recorded clip cannot provide this frame'):null;this.status(exists?'Clip unavailable — press Play to retry':'No footage at this time');return;}
     if(this.active&&this.active!==chosen){this.active.video.pause();this.active.video.hidden=true;if(this.active.video.style)this.active.video.style.zIndex='0';}if(this.active!==chosen){this.active=chosen;this.onActive(chosen.video);}if(chosen.video.style)chosen.video.style.zIndex='1';this.error=null;
    }else if(force){this.waiting=true;this.active.video.pause();await this.seek(this.active,t);}
    if(this.closed)return;
    // A scrub arriving during a network load supersedes this old frame.
    if(this.desired?.force){this.active.video.hidden=true;return;}
    const v=this.active.video;if(this.playing&&v.readyState<3){this.waiting=true;this.status('Buffering this angle…');await wait(v,'canplay',()=>{});}v.hidden=false;v.muted=this.muted;this.ready=true;
    let wantedRate=rate;
    if(this.playing){
     const drift=(this.active.clip.start_ms+v.currentTime*1000)-t;
     const correctionLimit=this.continuous?1500:300;
     if(performance.now()-this.lastCorrection>1000&&Math.abs(drift)>correctionLimit){this.lastCorrection=performance.now();await this.seek(this.active,t);}
     if(this.continuous){
      // Resetting to 1x and then nudging on each 100 ms tick churns native
      // playback rates (especially on iPad). Ignore normal frame/clock jitter;
      // keep a correction steady and reconsider it at most once per second.
      if(this.active.requestedRate!==rate||force||performance.now()-(this.active.rateCorrectionAt??-Infinity)>=1000){
       this.active.wantedRate=Math.abs(drift)>250&&Math.abs(drift)<=correctionLimit?rate*Math.max(.95,Math.min(1.05,1-drift/1500)):rate;
       this.active.requestedRate=rate;this.active.rateCorrectionAt=performance.now();
      }
      wantedRate=this.active.wantedRate;
     }else if(Math.abs(drift)>60&&Math.abs(drift)<=correctionLimit)wantedRate=rate*Math.max(.92,Math.min(1.08,1-drift/1500));
     if(!Number.isFinite(v.playbackRate)||Math.abs(v.playbackRate-wantedRate)>.005)v.playbackRate=wantedRate;
     this.play(this.active);
    }else{if(v.playbackRate!==rate)v.playbackRate=rate;v.pause();}
    this.status(v.readyState<3&&this.playing?'Buffering this angle…':'');
    const next=this.clips.find(c=>c.start_ms>this.active.clip.start_ms&&c.end_ms>this.end(this.active)&&c.start_ms<=this.end(this.active)+50);
    if(next&&this.end(this.active)-t<3500){
     const standby=this.slots.find(s=>s!==this.active),handover=this.end(this.active);
     if(!standby.preparing&&standby.preparedFor!==next.id&&(this.failures.get(next.id)||0)<Date.now()){
      standby.preparing=(async()=>{await this.load(standby,next);if(this.closed)return;const seconds=Math.max(0,(handover-next.start_ms)/1000);if(Math.abs(standby.video.currentTime-seconds)>.025)await wait(standby.video,'seeked',()=>{standby.video.currentTime=seconds;});if(standby.video.readyState<3)await wait(standby.video,'canplay',()=>{});standby.preparedFor=next.id;})().catch(()=>{this.failures.set(next.id,Date.now()+1500);}).finally(()=>{standby.preparing=null;});
     }
    }
   }catch(e){this.ready=false;this.error=e.message;this.status('Clip load failed — press Play to retry: '+e.message);}
   finally{this.waiting=false;this.busy=false;if(this.desired&&!this.closed)this.pump();}
  }
  retry(){this.failures.clear();this.error=null;}
  pause(){this.playing=false;if(this.desired)this.desired.playing=false;for(const s of this.slots)s.video.pause();}
  destroy(){this.closed=true;this.desired=null;for(const s of this.slots){s.video.dispatchEvent(new Event('drs-cancel'));s.video.pause();s.video.removeAttribute('src');s.video.load();s.video.remove();}}
 }
 const api={AnglePlayer,fit};if(typeof module!=='undefined')module.exports=api;else root.DRSPlayback=api;
})(typeof window!=='undefined'?window:globalThis);
