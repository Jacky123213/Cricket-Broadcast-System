(function () {
  'use strict';
  async function timedFetch(url, options, timeout, json = false) {
    const controller = new AbortController();
    const timer=setTimeout(()=>controller.abort(),timeout);
    try {
      const response = await fetch(url,Object.assign({},options,{signal:controller.signal}));
      if (!json) return response;
      if (!response.ok) throw Error("HTTP " + response.status);
      return await response.json();
    }
    finally { clearTimeout(timer); }
  }
  const epoch = Number.isFinite(performance.timeOrigin) ? performance.timeOrigin : Date.now() - performance.now();
  const localNow = () => epoch + performance.now();
  class Clock {
    constructor() { this.samples = []; this.offset = 0; this.uncertainty = Infinity; this.checked = 0; }
    async sample() {
      const t0 = localNow();
      const data = await timedFetch('/api/clock', {cache:'no-store'},4000,true), t3 = localNow();
      if (![t0,t3,data.received_ms,data.sent_ms].every(Number.isFinite)) throw Error('Invalid clock response — reload camera and server');
      const rtt = Math.max(0, (t3-t0)-(data.sent_ms-data.received_ms));
      this.samples = this.samples.filter(s => t3-s.at < 60000);
      this.samples.push({at:t3,offset:((data.received_ms-t0)+(data.sent_ms-t3))/2,rtt});
      const best = this.samples.reduce((a,b)=>a.rtt<b.rtt?a:b);
      this.offset = best.offset; this.uncertainty = best.rtt/2; this.checked = t3;
    }
    async sync(report = () => {}) { for(let i=0;i<5;i++) { report("Measuring clock " + (i+1) + "/5…"); await this.sample(); } }
    now() { return localNow()+this.offset; }
    fresh() { return localNow()-this.checked < 45000 && Number.isFinite(this.uncertainty); }
  }
  window.DRSClock = Clock;
  window.DRSRecorder = class {
    constructor(id, stream, report) {
      this.id=id;this.stream=stream;this.originalStream=stream;this.report=report;this.clock=new Clock();this.timing=null;
      this.running=false;this.cancelled=false;this.pending=0;this.records=new Set();
    }
    async start() {
      this.report('Checking recorder support…');
      if(!window.MediaRecorder) throw Error('This browser cannot record replay clips');
      try {
      await this.videoTimingTrack();
      // Firefox waits indefinitely for audio when Opus is requested without
      // an audio track (Mozilla 1881826). Never request a missing track kind.
      const audio=this.stream.getAudioTracks?.().some(t=>t.readyState==='live')||false;
      this.mime=['video/mp4',audio?'video/webm;codecs=vp8,opus':'video/webm;codecs=vp8','video/webm'].find(t=>MediaRecorder.isTypeSupported(t));
      if(!this.mime) throw Error('No supported recording codec');
      await this.clock.sync(this.report);
      if(this.cancelled){this.closeTimingTrack();return;}
      this.running=true;
      this.interval=setInterval(()=>this.clock.sample().catch(e=>this.report(e.message)),10000);
      this.next();
      }catch(error){this.closeTimingTrack();throw error;}
    }
    async videoTimingTrack(){
      if(this.timing||this.originalStream.getAudioTracks?.().some(t=>t.readyState==='live')||!/Firefox\//i.test(window.navigator?.userAgent||''))return;
      const Context=window.AudioContext||window.webkitAudioContext;
      if(!Context||typeof MediaStream==='undefined')return;
      let context;
      try{
        context=new Context();const resumed=await Promise.race([context.resume().then(()=>true),new Promise(resolve=>setTimeout(()=>resolve(false),750))]);
        if(!resumed||context.state!=='running'||this.cancelled){context.close().catch(()=>{});return;}
        const source=context.createConstantSource(),gain=context.createGain(),destination=context.createMediaStreamDestination();source.offset.value=0;gain.gain.value=0;source.connect(gain);gain.connect(destination);source.start();
        this.timing={context,source,tracks:destination.stream.getAudioTracks()};
        this.stream=new MediaStream([...this.originalStream.getVideoTracks(),...this.timing.tracks]);
      }catch{context?.close().catch(()=>{});}
    }
    closeTimingTrack(){if(!this.timing)return;try{this.timing.source.stop();}catch{}for(const t of this.timing.tracks)t.stop();this.timing.context.close().catch(()=>{});this.timing=null;this.stream=this.originalStream;}
    next() {
      clearTimeout(this.nextTimer);
      if(!this.running)return;
      if(!this.clock.fresh()){this.report('Clock stale — paused');this.nextTimer=setTimeout(()=>this.next(),1000);return;}
      if(this.records.size>=2){this.report('Encoder behind — waiting for previous clip');this.nextTimer=setTimeout(()=>this.next(),200);return;}
      const start=this.clock.now(),offset=this.clock.offset,error=this.clock.uncertainty;
      const settings=this.stream.getVideoTracks?.()[0]?.getSettings?.()||{};
      const width=Number(settings.width)||1280,height=Number(settings.height)||720,fps=Number(settings.frameRate)||30;
      // A bounded encoding budget for fast motion; browsers may choose a different bitrate.
      const bitrate=Math.round(Math.max(2500000,Math.min(8000000,width*height*fps*.12)));
      let recorder;
      try {recorder=new MediaRecorder(this.stream,{mimeType:this.mime,videoBitsPerSecond:bitrate});}
      catch(e){this.report('Encoder unavailable: '+e.message);this.nextTimer=setTimeout(()=>this.next(),1000);return;}
      const entry={recorder,start,end:start,chunks:[],offset,error,audio:this.originalStream.getAudioTracks?.().some(t=>t.readyState==='live'&&t.enabled!==false)||false};this.records.add(entry);
      recorder.ondataavailable=e=>{if(e.data.size)entry.chunks.push(e.data);};
      recorder.onerror=()=>{this.report('Encoder error — reconnect camera');this.stop();};
      recorder.onstop=()=>{
        clearTimeout(entry.watchdog);clearTimeout(entry.stopTimer);this.records.delete(entry);
        this.upload(entry).catch(e=>this.report('Replay gap: '+e.message));
        if(this.cancelled&&!this.records.size)this.closeTimingTrack();
      };
      try {recorder.start();}
      catch(e){this.records.delete(entry);this.report('Overlap not supported or encoder busy: '+e.message);this.nextTimer=setTimeout(()=>this.next(),1000);return;}
      this.report('Recording · '+this.mime+' · target '+(bitrate/1000000).toFixed(1)+' Mbps');
      // Three-second clips arrive before adaptive delayed playout needs
      // them. Keep a one-second overlap for decoder handover, without changing
      // capture resolution/bitrate or separating audio from its video.
      this.nextTimer=setTimeout(()=>this.next(),2000);
      entry.stopTimer=setTimeout(()=>this.finish(entry),3000);
    }
    finish(entry){
      if(!['recording','paused'].includes(entry.recorder.state))return;
      entry.end=localNow()+entry.offset;
      entry.watchdog=setTimeout(()=>{
        this.report('Recorder stalled: no final clip. Keep screen awake and retry replay.');
        this.running=false;clearInterval(this.interval);clearTimeout(this.nextTimer);
        this.closeTimingTrack();
      },10000);
      entry.recorder.stop();
    }
    async upload(e){
      const blob=new Blob(e.chunks,{type:this.mime});
      if(!blob.size||e.end<=e.start||e.end-e.start>15000)throw Error('Delayed or empty clip');
      if(this.pending>=2||blob.size>12*1024*1024)throw Error('Upload backlog; lower resolution');
      this.pending++;
      try {
        const fps=this.stream.getVideoTracks()[0].getSettings().frameRate||30;
        const params=new URLSearchParams({start_ms:e.start,end_ms:e.end,uncertainty_ms:e.error,offset_ms:e.offset,fps,audio:e.audio});
        const response=await timedFetch('/api/clips/'+encodeURIComponent(this.id)+'?'+params,{method:'POST',headers:{'Content-Type':this.mime},body:blob},12000);
        if(!response.ok)throw Error('Upload HTTP '+response.status);
        this.report('Buffer active · overlapping clips · offset '+e.offset.toFixed(1)+' ms · network ±'+e.error.toFixed(1)+' ms');
      }finally{this.pending--;}
    }
    flush(){
      if(!this.running)return;
      const previous=[...this.records];
      if(previous.length<2)this.next();
      // Keep a newer recorder capturing while the older one is finalised.
      if(previous[0]&&this.records.size>1){clearTimeout(previous[0].stopTimer);this.finish(previous[0]);}
    }
    stop(){
      this.cancelled=true;this.running=false;clearInterval(this.interval);clearTimeout(this.nextTimer);
      for(const entry of this.records){clearTimeout(entry.stopTimer);this.finish(entry);}
      if(!this.records.size)this.closeTimingTrack();
    }
  };
}());
