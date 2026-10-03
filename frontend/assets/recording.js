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
      this.id=id;this.stream=stream;this.report=report;this.clock=new Clock();
      this.running=false;this.cancelled=false;this.pending=0;this.records=new Set();
    }
    async start() {
      this.report('Checking recorder support…');
      if(!window.MediaRecorder) throw Error('This browser cannot record replay clips');
      this.mime=['video/mp4','video/webm;codecs=vp8,opus','video/webm'].find(t=>MediaRecorder.isTypeSupported(t));
      if(!this.mime) throw Error('No supported recording codec');
      await this.clock.sync(this.report);
      if(this.cancelled)return;
      this.running=true;
      this.interval=setInterval(()=>this.clock.sample().catch(e=>this.report(e.message)),10000);
      this.next();
    }
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
      const entry={recorder,start,end:start,chunks:[],offset,error};this.records.add(entry);
      recorder.ondataavailable=e=>{if(e.data.size)entry.chunks.push(e.data);};
      recorder.onerror=()=>{this.report('Encoder error — reconnect camera');this.stop();};
      recorder.onstop=()=>{
        clearTimeout(entry.watchdog);clearTimeout(entry.stopTimer);this.records.delete(entry);
        this.upload(entry).catch(e=>this.report('Replay gap: '+e.message));
      };
      try {recorder.start();}
      catch(e){this.records.delete(entry);this.report('Overlap not supported or encoder busy: '+e.message);this.nextTimer=setTimeout(()=>this.next(),1000);return;}
      this.report('Recording · '+this.mime+' · target '+(bitrate/1000000).toFixed(1)+' Mbps');
      // New recorder begins one second BEFORE this one stops; no stop/start hole.
      this.nextTimer=setTimeout(()=>this.next(),4000);
      entry.stopTimer=setTimeout(()=>this.finish(entry),5000);
    }
    finish(entry){
      if(!['recording','paused'].includes(entry.recorder.state))return;
      entry.end=localNow()+entry.offset;
      entry.watchdog=setTimeout(()=>{
        this.report('Recorder stalled: no final clip. Keep screen awake and retry replay.');
        this.running=false;clearInterval(this.interval);clearTimeout(this.nextTimer);
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
        const params=new URLSearchParams({start_ms:e.start,end_ms:e.end,uncertainty_ms:e.error,offset_ms:e.offset,fps});
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
    }
  };
}());
