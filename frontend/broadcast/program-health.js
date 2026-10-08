/* Measurements of decoded program playback, not camera-setting promises. */
(function(root){
  'use strict';
  function intervals(clips){const result=[];for(const clip of [...clips].sort((a,b)=>a.start_ms-b.start_ms)){const a=clip.start_ms,b=clip.end_ms;if(b<=a)continue;if(result.length&&a<=result.at(-1)[1])result.at(-1)[1]=Math.max(b,result.at(-1)[1]);else result.push([a,b]);}return result;}
  class PlaybackHealth {
    constructor(){this.seen=null;this.quality=new WeakMap();this.failures=new Map();this.late=0;this.decode=0;this.poll=0;this.dropped=null;this.total=null;this.frameAt=null;this.frameLocal=null;this.available=null;}
    ingest(clips,now,delay){const ids=new Set(clips.map(c=>c.id));if(this.seen)for(const c of clips)if(!this.seen.has(c.id)&&c.end_ms<=now-delay)this.late++;this.seen=ids;}
    frame(at,video,local=performance.now()){
      this.frameAt=at;this.frameLocal=local;
      try{const q=video?.getVideoPlaybackQuality?.();if(!q||!Number.isInteger(q.droppedVideoFrames)||!Number.isInteger(q.totalVideoFrames)||q.droppedVideoFrames<0||q.totalVideoFrames<0)return;
        const source=video.currentSrc||video.src||'',old=this.quality.get(video)||{dropped:0,total:0,source},reset=old.source!==source||q.totalVideoFrames<old.total||q.droppedVideoFrames<old.dropped;
        this.dropped=(this.dropped||0)+(reset?q.droppedVideoFrames:q.droppedVideoFrames-old.dropped);this.total=(this.total||0)+(reset?q.totalVideoFrames:q.totalVideoFrames-old.total);this.quality.set(video,{dropped:q.droppedVideoFrames,total:q.totalVideoFrames,source});
      }catch{/* Unsupported frame statistics remain unavailable, never guessed zero. */}
    }
    errors(player){for(const [id,until] of player.failures||[]){if(this.failures.get(id)!==until){this.decode++;this.failures.set(id,until);}}}
    snapshot(clips,now,local=performance.now()){
      const spans=intervals(clips),at=this.frameAt,span=at===null?null:spans.find(([a,b])=>a<=at&&at<=b);
      return {delay_seconds:at===null?null:Math.max(0,(now-at)/1000),available_seconds:this.available??spans.reduce((sum,[a,b])=>sum+(b-a)/1000,0),headroom_seconds:span?Math.max(0,(span[1]-at)/1000):null,last_frame_age_ms:this.frameLocal===null?null:Math.max(0,local-this.frameLocal),dropped_frames:this.dropped,total_frames:this.total,late_clips:this.late,decode_errors:this.decode,poll_errors:this.poll};
    }
  }
  class AudioMeter {
    constructor(){this.context=null;this.nodes=new Map();this.activeVideo=null;this.outputMuted=true;this.state='unavailable';}
    async start(videos){
      const Context=root.AudioContext||root.webkitAudioContext;
      if(!Context)return false;
      try{if(!this.context)this.context=new Context();for(const video of videos){if(this.nodes.has(video))continue;const source=this.context.createMediaElementSource(video),analyser=this.context.createAnalyser(),gain=this.context.createGain();analyser.fftSize=1024;gain.gain.value=this.outputMuted||this.activeVideo!==video?0:1;source.connect(analyser);analyser.connect(gain);gain.connect(this.context.destination);this.nodes.set(video,{source,analyser,gain,data:new Float32Array(analyser.fftSize)});}await this.context.resume();this.state=this.context.state==='running'?'active':'suspended';return this.state==='active';}catch{this.state='unavailable';return false;}
    }
    select(video){this.activeVideo=video;this.mute(this.outputMuted);}
    mute(muted){this.outputMuted=muted;for(const [video,n] of this.nodes)n.gain.gain.value=muted||this.activeVideo!==video?0:1;}
    sample(video,hasAudio){
      if(!hasAudio)return {meter_state:'no_audio',meter_dbfs:null};
      const n=this.nodes.get(video);if(!this.context||!n)return {meter_state:this.state,meter_dbfs:null};
      if(this.context.state!=='running')return {meter_state:'suspended',meter_dbfs:null};
      try{n.analyser.getFloatTimeDomainData(n.data);const rms=Math.sqrt(n.data.reduce((s,v)=>s+v*v,0)/n.data.length);return {meter_state:'active',meter_dbfs:Math.max(-120,Math.min(0,20*Math.log10(Math.max(1e-6,rms))))};}catch{return {meter_state:'unavailable',meter_dbfs:null};}
    }
    reset(){for(const n of this.nodes.values()){n.source.disconnect();n.analyser.disconnect();n.gain.disconnect();}this.nodes.clear();this.activeVideo=null;}
    close(){this.reset();this.context?.close().catch(()=>{});this.context=null;}
  }
  const api={PlaybackHealth,AudioMeter,intervals};if(typeof module!=='undefined')module.exports=api;else root.DRSProgramHealth=api;
})(typeof window!=='undefined'?window:globalThis);
