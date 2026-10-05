const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function context(fetch){
 const c={window:{},performance:{timeOrigin:100000,now:()=>0},fetch,AbortController,URLSearchParams,Blob,Uint8Array,console,
 setTimeout:()=>1,clearTimeout:()=>{},setInterval:()=>1,clearInterval:()=>{}};
 vm.createContext(c);vm.runInContext(fs.readFileSync('frontend/assets/recording.js','utf8'),c);return c;
}
test('clock uses smallest round trip sample and rejects stale estimates',async()=>{
 let n=0,t=0;
 const c=context(async()=>{t+=n++===0?20:100;return {ok:true,json:async()=>({received_ms:100510,sent_ms:100510})};});
 c.performance.now=()=>t;
 const clock=new c.window.DRSClock();await clock.sample();assert.equal(clock.offset,500);assert.equal(clock.uncertainty,10);
 await clock.sample();assert.equal(clock.offset,500);t=100000;assert.equal(clock.fresh(),false);
});
test('independent recording uploads measured interval and stops without restarting',async()=>{
 const uploads=[];let t=0;
 const c=context(async(url,options)=>{uploads.push({url,options});return {ok:true};});
 c.performance.now=()=>t;
 class Recorder{
   static isTypeSupported(){return true;}
   constructor(){this.state='inactive';}
   start(){this.state='recording';}
   stop(){this.state='inactive';this.ondataavailable({data:new Blob(['encoded'])});this.onstop();}
 }
 c.MediaRecorder=Recorder;c.window.MediaRecorder=Recorder;
 const rec=new c.window.DRSRecorder('phone',{getVideoTracks:()=>[{getSettings:()=>({frameRate:30})}],getAudioTracks:()=>[{readyState:'live'}]},()=>{});
 rec.clock.sync=async()=>{rec.clock.checked=100000;rec.clock.offset=500;rec.clock.uncertainty=3;};
 await rec.start();t=4900;rec.stop();await new Promise(r=>setImmediate(r));
 assert.equal(uploads.length,1);const url=new URL(uploads[0].url,'http://local');
 assert.equal(url.searchParams.get('start_ms'),'100500');assert.equal(url.searchParams.get('end_ms'),'105400');assert.equal(rec.running,false);
 assert.equal(url.searchParams.get('audio'),'true');
 assert.equal(await uploads[0].options.body.text(),'encoded');
});
test('clock remains finite without performance.timeOrigin',async()=>{
 const c=context(async()=>({ok:true,json:async()=>({received_ms:Date.now()+500,sent_ms:Date.now()+500})}));
 c.performance.timeOrigin=undefined;
 vm.runInContext(fs.readFileSync('frontend/assets/recording.js','utf8'),c);
 const clock=new c.window.DRSClock();await clock.sample();assert.ok(Number.isFinite(clock.offset));assert.ok(clock.fresh());
});
test('recorder watchdog reports missing browser stop callback',async()=>{
 const c=context(async()=>({ok:true}));const timers=[],messages=[];
 c.setTimeout=(fn,ms)=>{timers.push({fn,ms});return timers.length;};
 class Recorder {static isTypeSupported(){return true;} start(){this.state='recording';} stop(){this.state='inactive';}}
 c.MediaRecorder=Recorder;c.window.MediaRecorder=Recorder;
 const rec=new c.window.DRSRecorder('p',{},m=>messages.push(m));
 rec.clock.sync=async()=>{rec.clock.checked=100000;rec.clock.uncertainty=2;};await rec.start();
 timers.find(t=>t.ms===3000).fn();timers.find(t=>t.ms===10000).fn();
 assert.ok(messages.some(m=>m.includes('Recorder stalled')));assert.equal(rec.running,false);
});
test('new recorder starts one second before previous recording stops',async()=>{
 const c=context(async()=>({ok:true})),timers=[],records=[];let t=0;
 c.performance.now=()=>t;c.setTimeout=(fn,ms)=>{timers.push({fn,ms});return timers.length;};
 class Recorder{static isTypeSupported(){return true;}constructor(){records.push(this);}start(){this.state='recording';}stop(){this.state='inactive';this.ondataavailable({data:new Blob(['encoded'])});this.onstop();}}
 c.MediaRecorder=Recorder;c.window.MediaRecorder=Recorder;
 const r=new c.window.DRSRecorder('p',{getVideoTracks:()=>[{getSettings:()=>({frameRate:30})}]},()=>{});
 r.clock.sync=async()=>{r.clock.checked=100000;r.clock.uncertainty=2;};await r.start();
 t=2000;timers.find(t=>t.ms===2000).fn();assert.equal(records.length,2);assert.ok(records.every(r=>r.state==='recording'));
 t=3000;timers.find(t=>t.ms===3000).fn();assert.equal(records[0].state,'inactive');assert.equal(records[1].state,'recording');r.stop();
});

test('recording bitrate scales with capture and stays bounded',async()=>{
 for(const [width,height,frameRate,expected] of [[640,480,30,2500000],[1920,1080,30,7464960],[3840,2160,60,8000000]]){
  const c=context(async()=>({ok:true}));let options;
  class Recorder{static isTypeSupported(){return true;}constructor(s,o){options=o;}start(){this.state='recording';}stop(){this.state='inactive';}}
  c.MediaRecorder=Recorder;c.window.MediaRecorder=Recorder;
  const r=new c.window.DRSRecorder('p',{getVideoTracks:()=>[{getSettings:()=>({width,height,frameRate})}]},()=>{});
  r.clock.sync=async()=>{r.clock.checked=100000;r.clock.uncertainty=2;};await r.start();assert.equal(options.videoBitsPerSecond,expected);r.stop();
 }
});
