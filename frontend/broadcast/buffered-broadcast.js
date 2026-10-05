/* Five-second playout from the existing full-quality, timestamped replay ring.
   Native video decoders carry video and audio together; no canvas re-encoding. */
(function(){
  'use strict';
  window.DRSBufferedBroadcast = class {
    constructor(id, mount, callbacks, delay=5000) {
      this.id=id;this.callbacks=callbacks;this.delay=delay;this.closed=false;this.busy=false;
      this.anchor=null;this.controller=null;this.clockSamples=[];
      this.buffering=true;this.stalledAt=null;this.lastFrame=null;
      this.health=window.DRSProgramHealth?new window.DRSProgramHealth.PlaybackHealth():null;
      this.player=new window.DRSPlayback.AnglePlayer([],()=>{
        const video=document.createElement('video');video.className='program-video';
        video.playsInline=true;video.preload='auto';video.hidden=true;video.muted=true;
        video.setAttribute('aria-label','Delayed DRS program camera');
        const nativePlay=video.play.bind(video);
        video.play=async()=>{
          try{return await nativePlay();}
          catch(error){
            if(error.name==='NotAllowedError'&&!video.muted&&!this.closed){
              this.setMuted(true);callbacks.onMute(true);return nativePlay();
            }
            throw error;
          }
        };
        mount.append(video);return video;
      },message=>{if(!this.closed&&message&&this.buffering)callbacks.onStatus(message);},{continuous:true});
      this.poll();this.tickTimer=setInterval(()=>this.tick(),100);
    }
    now(){return this.anchor?this.anchor.server+performance.now()-this.anchor.local:null;}
    syncClock(server,started,ended){
      if(!Number.isFinite(server))throw Error('Invalid buffer clock');
      this.clockSamples=this.clockSamples.filter(sample=>ended-sample.at<60000);
      this.clockSamples.push({server,local:(started+ended)/2,rtt:ended-started,at:ended});
      const best=this.clockSamples.reduce((a,b)=>a.rtt<b.rtt?a:b);
      const estimate=best.server+ended-best.local;
      const previous=this.now();
      // Network spikes must not jerk the playback clock backwards/forwards.
      this.anchor={server:previous===null?estimate:previous+Math.max(-25,Math.min(25,estimate-previous)),local:ended};
    }
    async poll(){
      if(this.closed||this.busy)return;this.busy=true;
      const started=performance.now();this.controller=new AbortController();
      const timeout=setTimeout(()=>this.controller?.abort(),3000);
      try{
        const response=await fetch('/api/broadcast/camera/'+encodeURIComponent(this.id),{cache:'no-store',signal:this.controller.signal});
        if(!response.ok)throw Error('Camera buffer HTTP '+response.status);
        const data=await response.json();if(this.closed)return;
        this.syncClock(data.server_ms,started,performance.now());
        this.health?.ingest(data.clips,this.now(),this.delay);
        if(this.health)this.health.available=data.available_seconds??null;
        this.player.clips=data.clips;
        if(!data.clips.length)this.callbacks.onStatus(data.recorder?.message||'Waiting for recorded camera video — press Start/retry replay on the camera.');
        this.tick();
      }catch(error){if(!this.closed){if(this.health)this.health.poll++;this.callbacks.onStatus('Buffer connection: '+error.message);}}
      finally{clearTimeout(timeout);this.busy=false;if(!this.closed)this.pollTimer=setTimeout(()=>this.poll(),500);}
    }
    tick(){
      const now=this.now();if(this.closed||now===null)return;
      const target=now-this.delay;
      this.player.update(target,true,1);
      this.health?.errors(this.player);
      const active=this.player.active;
      if(active&&!active.video.hidden&&active.video.readyState>=3&&!active.video.paused&&!active.video.ended){
        const at=active.clip.start_ms+active.video.currentTime*1000;
        const progressing=!this.lastFrame||this.lastFrame.clip!==active.clip.id||at>this.lastFrame.at+1;
        if(progressing){this.lastFrame={clip:active.clip.id,at};this.stalledAt=null;this.buffering=false;
          this.health?.frame(at,active.video);
          this.callbacks.onFrame({at,delay:(now-at)/1000,audio:Boolean(active.clip.audio)});return;}
      }
      if(this.stalledAt===null)this.stalledAt=performance.now();
      // Decoder swaps can briefly pause/canplay. Keep the last real frame and
      // its graphics rather than flashing a full-screen notice on every swap.
      if(!this.buffering&&performance.now()-this.stalledAt>=750){this.buffering=true;this.callbacks.onBuffering();}
    }
    setMuted(muted){this.player.muted=muted;for(const slot of this.player.slots)slot.video.muted=muted;}
    resume(){if(this.player.active)this.player.play(this.player.active);this.tick();}
    healthSnapshot(){return this.health?.snapshot(this.player.clips,this.now()??Date.now())||{};}
    destroy(){this.closed=true;clearInterval(this.tickTimer);clearTimeout(this.pollTimer);this.controller?.abort();this.player.destroy();}
  };
})();
