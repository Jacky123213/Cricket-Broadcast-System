/* Native playback with two decoder slots per angle. No global seek loop. */
(function(root){
 'use strict';
 function fit(sw,sh,w,h){const s=Math.min(w/sw,h/sh);return {x:(w-sw*s)/2,y:(h-sh*s)/2,width:sw*s,height:sh*s};}
 function wait(video,event,action){return new Promise((resolve,reject)=>{let timer;const done=e=>{clearTimeout(timer);video.removeEventListener(event,ok);video.removeEventListener('error',bad);video.removeEventListener('drs-cancel',cancel);e?reject(e):resolve();};const ok=()=>done(),bad=()=>done(Error('Clip could not be decoded')),cancel=()=>done(Error('Player closed'));video.addEventListener(event,ok);video.addEventListener('error',bad);video.addEventListener('drs-cancel',cancel);timer=setTimeout(()=>done(Error('Clip loading timed out')),6000);try{action();}catch(e){done(e);}});}
 class AnglePlayer{
  constructor(clips,makeVideo,status=()=>{}){this.clips=clips;this.status=status;this.slots=[0,1].map(()=>({video:makeVideo(),clip:null,promise:null}));this.active=null;this.desired=null;this.busy=false;this.closed=false;this.lastCorrection=0;this.failures=new Map();this.muted=true;this.ready=false;this.playing=false;this.waiting=false;this.error=null;}
  get video(){return this.active?.video||this.slots[0].video;}
  end(slot){return Math.min(slot.clip.end_ms,Number.isFinite(slot.video.duration)?slot.clip.start_ms+slot.video.duration*1000:Infinity);}
  covers(slot,t){return slot?.clip&&slot.clip.start_ms<=t&&t<this.end(slot);}
  async load(slot,clip){
   if(slot.clip?.id===clip.id){if(slot.promise)await slot.promise;return;}
   if(slot.promise)await slot.promise.catch(()=>{});
   if(this.closed)return;
   slot.clip=clip;slot.preparedFor=null;slot.video.pause();slot.video.hidden=true;
   slot.promise=wait(slot.video,'loadedmetadata',()=>{slot.video.src=clip.url;slot.video.load();});
   try{await slot.promise;if(slot.video.readyState<2)await wait(slot.video,'loadeddata',()=>{});}catch(e){slot.clip=null;throw e;}finally{slot.promise=null;}
  }
  async seek(slot,t){if(slot.preparing)await slot.preparing;const seconds=Math.max(0,(t-slot.clip.start_ms)/1000);if(Math.abs(slot.video.currentTime-seconds)>.025)await wait(slot.video,'seeked',()=>{slot.video.currentTime=seconds;});if(slot.video.readyState<2)await wait(slot.video,'loadeddata',()=>{});}
  play(slot){slot.video.muted=this.muted;if(slot.video.paused&&!slot.playPromise){slot.playPromise=slot.video.play().catch(e=>this.status('Tap Play to resume: '+e.message)).finally(()=>{slot.playPromise=null;});}}
  update(t,playing,rate=1,force=false){this.playing=playing;this.desired={t,playing,rate,force:force||this.desired?.force};if(!this.busy)this.pump();}
  async pump(){
   if(this.closed||!this.desired)return;this.busy=true;const request=this.desired;this.desired=null;
   const {t,playing,rate,force}=request;
   try{
    if(!this.covers(this.active,t)){
     this.ready=false;this.waiting=true;this.error=null;this.status('Loading next frame…');
     if(this.active)this.active.video.pause();
     const candidates=[...this.clips].reverse().filter(c=>c.start_ms<=t&&t<c.end_ms&&(this.failures.get(c.id)||0)<Date.now());
     let chosen=null;
     for(const clip of candidates){const slot=this.slots.find(s=>s.clip?.id===clip.id)||this.slots.find(s=>s!==this.active)||this.slots[0];try{await this.load(slot,clip);if(this.closed)return;if(!this.covers(slot,t))continue;await this.seek(slot,t);if(this.playing&&slot.video.readyState<3)await wait(slot.video,'canplay',()=>{});chosen=slot;break;}catch(e){this.failures.set(clip.id,Date.now()+10000);this.error=e.message;this.status(e.message);}}
     if(!chosen){if(this.active)this.active.video.hidden=true;const exists=this.clips.some(c=>c.start_ms<=t&&t<c.end_ms);this.error=exists?(this.error||'Recorded clip cannot provide this frame'):null;this.status(exists?'Clip unavailable — press Play to retry':'No footage at this time');return;}
     if(this.active&&this.active!==chosen)this.active.video.hidden=true;this.active=chosen;this.error=null;
    }else if(force){this.waiting=true;this.active.video.pause();await this.seek(this.active,t);}
    if(this.closed)return;
    // A scrub arriving during a network load supersedes this old frame.
    if(this.desired?.force){this.active.video.hidden=true;return;}
    const v=this.active.video;if(this.playing&&v.readyState<3){this.waiting=true;this.status('Buffering this angle…');await wait(v,'canplay',()=>{});}v.hidden=false;v.playbackRate=rate;v.muted=this.muted;this.ready=true;
    if(this.playing){
     const drift=(this.active.clip.start_ms+v.currentTime*1000)-t;
     if(performance.now()-this.lastCorrection>1000&&Math.abs(drift)>300){this.lastCorrection=performance.now();await this.seek(this.active,t);}
     else if(Math.abs(drift)>60&&Math.abs(drift)<=300)v.playbackRate=rate*Math.max(.92,Math.min(1.08,1-drift/1500));
     this.play(this.active);
    }else v.pause();
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
