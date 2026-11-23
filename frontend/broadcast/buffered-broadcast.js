/* Adaptive 8-10 second playout from complete files in the rolling replay ring. */
(function(){
  'use strict';
  window.DRSBufferedBroadcast = class {
    constructor(id,mount,callbacks,delay=8000){
      this.id=id;this.mount=mount;this.callbacks=callbacks;this.minDelay=delay;this.maxDelay=Math.max(delay,10000);this.delay=delay;
      this.closed=false;this.busy=false;this.anchor=null;this.controller=null;this.clockSamples=[];this.manifest=[];
      this.buffering=true;this.stalledAt=null;this.lastFrame=null;this.lastRecovery=-Infinity;this.recoveries=0;this.downloadErrors=0;this.lastError=null;this.lastDownloadError=null;this.muted=true;this.inTick=false;this.holdUsed=false;
      this.health=window.DRSProgramHealth?new window.DRSProgramHealth.PlaybackHealth():null;
      this.transition=window.DRSProgramTransition?new window.DRSProgramTransition(mount,()=>{if(!this.closed&&this.buffering)callbacks.onBuffering();}):null;
      this.cache=window.DRSLiveClipCache?new window.DRSLiveClipCache(()=>{this.readyClips();this.tick();},error=>{this.downloadErrors++;this.lastDownloadError=error.message;}):null;
      this.makePlayer();this.poll();this.tickTimer=setInterval(()=>this.tick(),100);
    }
    makePlayer(){
      this.player=new window.DRSPlayback.AnglePlayer([],()=>{
        const video=document.createElement('video');video.className='program-video';video.playsInline=true;video.preload='auto';video.hidden=true;video.muted=this.muted;video.setAttribute('aria-label','Delayed program camera');
        const nativePlay=video.play.bind(video);video.play=async()=>{try{return await nativePlay();}catch(error){if(error.name==='NotAllowedError'&&!video.muted&&!this.closed){this.setMuted(true);this.callbacks.onMute(true);return nativePlay();}throw error;}};
        this.mount.append(video);return video;
      },message=>{if(!this.closed&&message&&this.buffering)this.callbacks.onStatus(message);},{continuous:true,onActive:video=>this.callbacks.onVideo?.(video)});
      this.player.muted=this.muted;
    }
    now(){return this.anchor?this.anchor.server+performance.now()-this.anchor.local:null;}
    syncClock(server,started,ended){
      if(!Number.isFinite(server))throw Error('Invalid buffer clock');this.clockSamples=this.clockSamples.filter(s=>ended-s.at<60000);
      this.clockSamples.push({server,local:(started+ended)/2,rtt:ended-started,at:ended});const best=this.clockSamples.reduce((a,b)=>a.rtt<b.rtt?a:b),estimate=best.server+ended-best.local,previous=this.now();
      this.anchor={server:previous===null?estimate:previous+Math.max(-25,Math.min(25,estimate-previous)),local:ended};
    }
    readyClips(){if(!this.player||this.closed)return;this.player.clips=this.cache?this.cache.ready(this.manifest):this.manifest;}
    async poll(){
      if(this.closed||this.busy)return;this.busy=true;const started=performance.now();this.controller=new AbortController();const timeout=setTimeout(()=>this.controller?.abort(),3000);
      try{const response=await fetch('/api/broadcast/camera/'+encodeURIComponent(this.id),{cache:'no-store',signal:this.controller.signal});if(!response.ok)throw Error('Camera buffer HTTP '+response.status);const data=await response.json();if(this.closed)return;
        this.syncClock(data.server_ms,started,performance.now());this.health?.ingest(data.clips,this.now(),this.delay);if(this.health)this.health.available=data.available_seconds??null;
        this.manifest=data.clips;this.cache?.update(data.clips,this.now(),this.now()-this.delay,this.player.slots.map(s=>s.clip?.source_url).filter(Boolean));this.readyClips();
        if(!data.clips.length)this.callbacks.onStatus(data.recorder?.message||'Waiting for complete camera clips');this.tick();
      }catch(error){if(!this.closed){if(this.health)this.health.poll++;this.callbacks.onStatus('Buffer connection: '+error.message);}}
      finally{clearTimeout(timeout);this.busy=false;if(!this.closed)this.pollTimer=setTimeout(()=>this.poll(),500);}
    }
    target(now){
      let at=now-this.delay;
      if(!this.player.clips.some(c=>c.start_ms<=at&&at<c.end_ms)){
        const usable=this.player.clips.map(c=>Math.min(at,c.end_ms-100)).filter(t=>t>=now-this.maxDelay&&t<=now-this.minDelay&&this.player.clips.some(c=>c.start_ms<=t&&t<c.end_ms));
        if(usable.length){at=Math.max(...usable);this.delay=Math.max(this.delay,Math.min(this.maxDelay,now-at));}
      }
      // Growing the buffer must not rewind a picture already put on air.
      return Math.max(at,this.lastFrame?.at??-Infinity);
    }
    holdFrame(){if(this.holdUsed)return;this.holdUsed=true;this.transition?.hold(this.player.active?.video||null);}
    recover(target){
      this.holdFrame();this.health?.errors(this.player);if(this.player.lastError||this.player.error)this.lastError=this.player.lastError||this.player.error;
      const failures=new Map(this.player.failures||[]);this.callbacks.onRecovery?.();this.player.destroy();this.recoveries++;this.lastRecovery=performance.now();
      this.makePlayer();this.player.failures=failures;this.readyClips();this.player.update(target,true,1);this.callbacks.onStatus('Recovering camera playback - target '+(this.delay/1000).toFixed(1)+' s');
    }
    tick(){
      const now=this.now();if(this.closed||now===null||this.inTick)return;this.inTick=true;
      try{const target=this.target(now);this.player.update(target,true,1);this.health?.errors(this.player);if(this.player.lastError)this.lastError=this.player.lastError;
        const active=this.player.active;
        if(active?.clip&&!active.video.hidden&&active.video.readyState>=3&&!active.video.paused&&!active.video.ended){
          const at=active.clip.start_ms+active.video.currentTime*1000,progressing=!this.lastFrame||at>this.lastFrame.at+1;
          if(progressing){this.lastFrame={clip:active.clip.id,at};this.stalledAt=null;this.buffering=false;this.holdUsed=false;this.transition?.reveal();this.health?.frame(at,active.video);
            this.callbacks.onFrame({at,delay:Math.max(0,(now-at)/1000),audio:Boolean(active.clip.audio)});return;}
        }
        // The initial delay is intentional: do not reset a healthy decoder or
        // grow the buffer before the camera has recorded the target time.
        if(!this.lastFrame&&!this.player.clips.some(c=>c.start_ms<=target&&target<c.end_ms)){this.stalledAt=null;return;}
        if(this.stalledAt===null)this.stalledAt=performance.now();const stalled=performance.now()-this.stalledAt;
        if(stalled>=750&&!this.buffering){this.buffering=true;this.holdFrame();if(!this.transition?.holding)this.callbacks.onBuffering();}
        if(stalled>=1500&&this.delay<this.maxDelay)this.delay=Math.min(this.maxDelay,this.minDelay+Math.floor(stalled/1000)*1000);
        const retryAt=this.target(now);
        if(stalled>=2500&&performance.now()-this.lastRecovery>=4000&&this.player.clips.some(c=>c.start_ms<=retryAt&&retryAt<c.end_ms))this.recover(retryAt);
      }finally{this.inTick=false;}
    }
    setMuted(muted){this.muted=muted;this.player.muted=muted;for(const slot of this.player.slots)slot.video.muted=muted;}
    resume(){this.player.retry?.();if(this.player.active)this.player.play(this.player.active);this.tick();}
    healthSnapshot(){const clips=this.player.clips,spans=window.DRSProgramHealth?.intervals?.(clips)||[];return {...(this.health?.snapshot(clips,this.now()??Date.now())||{}),target_delay_seconds:this.delay/1000,cached_seconds:spans.reduce((n,[a,b])=>n+(b-a)/1000,0),clip_download_ms:this.cache?.lastLoadMs??null,download_errors:this.downloadErrors,recovery_attempts:this.recoveries,last_decode_error:this.lastError?String(this.lastError).slice(0,240):null,last_download_error:this.lastDownloadError?String(this.lastDownloadError).slice(0,240):null};}
    destroy(){this.closed=true;clearInterval(this.tickTimer);clearTimeout(this.pollTimer);this.controller?.abort();this.transition?.clear();this.player.destroy();this.cache?.destroy();}
  };
})();
