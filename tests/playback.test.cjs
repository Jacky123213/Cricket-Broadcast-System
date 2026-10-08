const test=require('node:test'),assert=require('node:assert/strict');
const {AnglePlayer,fit}=require('../frontend/assets/replay-engine');
class Video extends EventTarget{
 constructor(){super();this._time=0;this.duration=5;this.paused=true;this.readyState=4;this.seeks=0;this.plays=0;this.pauses=0;this.loads=0;}
 get currentTime(){return this._time;}set currentTime(t){this._time=t;this.seeks++;queueMicrotask(()=>this.dispatchEvent(new Event('seeked')));}
 load(){this.loads++;queueMicrotask(()=>this.dispatchEvent(new Event('loadedmetadata')));}
 play(){this.paused=false;this.plays++;return Promise.resolve();}pause(){this.paused=true;this.pauses++;}
 removeAttribute(){}remove(){}
}
const settle=async()=>{for(let i=0;i<6;i++)await new Promise(r=>setImmediate(r));};
const clips=[{id:'a',url:'/a',start_ms:0,end_ms:5000},{id:'b',url:'/b',start_ms:4000,end_ms:9000}];
test('native playback advances without repeated seeks or pauses',async()=>{
 const p=new AnglePlayer(clips,()=>new Video());p.update(0,true);await settle();const v=p.video,pauses=v.pauses;
 for(let t=100;t<=2500;t+=100){v._time=t/1000;p.update(t,true);await settle();}
 assert.equal(v.seeks,0);assert.equal(v.pauses,pauses);assert.equal(v.plays,1);p.destroy();
});
test('preloads next overlapping clip and switches locally at boundary',async()=>{
 const p=new AnglePlayer(clips,()=>new Video());p.update(3000,true);await settle();const old=p.video;
 const standby=p.slots.find(s=>s.video!==old);assert.equal(standby.clip.id,'b');assert.equal(standby.video.loads,1);assert.equal(standby.video.currentTime,1);assert.equal(standby.preparedFor,'b');
 old._time=4.9;p.update(4900,true);await settle();assert.equal(p.video,old);
 p.update(5100,true);await settle();assert.equal(p.video,standby.video);assert.equal(p.video.currentTime,1.1);assert.equal(old.paused,true);p.destroy();
});
test('real gaps hide old footage; explicit scrub seeks to requested instant',async()=>{
 const messages=[];const p=new AnglePlayer(clips,()=>new Video(),m=>messages.push(m));p.update(2000,false,true);await settle();
 p.update(10000,false);await settle();assert.equal(p.video.hidden,true);assert.ok(messages.includes('No footage at this time'));
 p.update(1000,false,1,true);await settle();assert.equal(p.video.currentTime,1);assert.equal(p.video.hidden,false);p.destroy();
});
test('pause during asynchronous loading cannot restart playback',async()=>{
 const pending=[];const p=new AnglePlayer(clips,()=>{const v=new Video();v.load=()=>pending.push(v);return v;});
 p.update(2000,true);p.pause();pending[0].dispatchEvent(new Event('loadedmetadata'));await settle();assert.equal(p.video.paused,true);p.destroy();
});
test('portrait and landscape use proportional letterboxing',()=>{
 const portrait=fit(360,640,640,360);assert.equal(portrait.width/portrait.height,360/640);assert.ok(portrait.x>0);assert.equal(portrait.y,0);
 const wide=fit(1920,1080,375,400);assert.equal(wide.width,375);assert.ok(wide.y>0);assert.equal(wide.width/wide.height,1920/1080);
});

test('metadata alone is not a decoded frame; wait until data arrives',async()=>{
 const p=new AnglePlayer([clips[0]],()=>{const v=new Video();v.readyState=1;return v;});
 p.update(0,true);await settle();assert.equal(p.ready,false);assert.equal(p.waiting,true);
 const v=p.slots[0].video;v.readyState=4;v.dispatchEvent(new Event('loadeddata'));await settle();
 assert.equal(p.ready,true);assert.equal(p.waiting,false);assert.equal(v.paused,false);p.destroy();
});
test('decode failure is an error, not a genuine gap, and retry can recover',async()=>{
 let broken=true;const messages=[];
 const p=new AnglePlayer([clips[0]],()=>{const v=new Video();v.load=()=>queueMicrotask(()=>v.dispatchEvent(new Event(broken?'error':'loadedmetadata')));return v;},m=>messages.push(m));
 p.update(0,true);await settle();assert.ok(p.error);assert.equal(p.ready,false);assert.ok(!messages.includes('No footage at this time'));
 broken=false;p.retry();p.update(0,true);await settle();assert.equal(p.error,null);assert.equal(p.ready,true);p.destroy();
});

test('continuous broadcast swaps a prepared decoder without an extra boundary seek',async()=>{
 const p=new AnglePlayer(clips,()=>new Video(),()=>{},{continuous:true});p.update(3000,true);await settle();
 const old=p.video,standby=p.slots.find(s=>s.video!==old),seeks=standby.video.seeks;
 assert.equal(standby.preparedFor,'b');old._time=4.9;p.update(5100,true);await settle();
 assert.equal(p.video,standby.video);assert.equal(standby.video.seeks,seeks);assert.equal(old.paused,true);assert.equal(p.video.hidden,false);
 const count=p.video.seeks;p.lastCorrection=-10000;p.update(6300,true);await settle();
 assert.equal(p.video.seeks,count,'ordinary broadcast drift is corrected with bounded speed, not another seek');assert.ok(p.video.playbackRate<=1.05);p.destroy();
});

test('continuous loading keeps the outgoing decoder visible and playing until replacement is ready',async()=>{
 const p=new AnglePlayer([clips[0]],()=>new Video(),()=>{},{continuous:true});p.update(3000,true);await settle();const old=p.video;
 p.clips=clips;const standby=p.slots.find(s=>s.video!==old);standby.video.readyState=1;
 p.update(5100,true);await settle();assert.equal(old.paused,false);assert.equal(old.hidden,false);assert.equal(p.waiting,true);
 standby.video.readyState=4;standby.video.dispatchEvent(new Event('loadeddata'));await settle();
 assert.equal(p.video,standby.video);assert.equal(old.paused,true);assert.equal(old.hidden,true);p.destroy();
});

test('an overlapping arrival cannot replace a standby decoder while it is still preparing',async()=>{
 const p=new AnglePlayer([clips[0]],()=>new Video(),()=>{},{continuous:true});
 try{
  p.update(3000,true);await settle();const old=p.video,standby=p.slots.find(s=>s.video!==old);
  standby.video.readyState=1;p.clips=clips;p.update(3100,true);await settle();
  assert.equal(standby.clip.id,'b');assert.ok(standby.preparing);
  const newer={id:'c',url:'/c',start_ms:5000,end_ms:10000};p.clips=[...clips,newer];
  p.update(5100,true);await settle();
  assert.equal(standby.clip.id,'b','do not abort the preload by replacing its video source');
  assert.equal(standby.video.loads,1);
  standby.video.readyState=4;standby.video.dispatchEvent(new Event('loadeddata'));await settle();
  assert.equal(p.active.clip.id,'b','use the already preparing clip when it covers the handover');
  assert.equal(p.video.hidden,false);assert.equal(p.error,null);
 }finally{p.destroy();}
});

test('a slow continuous load hands over at the newest requested timestamp, not the obsolete one',async()=>{
 const p=new AnglePlayer([clips[0]],()=>new Video(),()=>{},{continuous:true});
 try{
  p.update(3000,true);await settle();const standby=p.slots.find(s=>s!==p.active);
  standby.video.readyState=1;p.clips=clips;p.update(5100,true);await settle();
  p.update(6700,true);await settle();
  standby.video.readyState=4;standby.video.dispatchEvent(new Event('loadeddata'));await settle();
  assert.equal(p.active.clip.id,'b');assert.equal(p.video.currentTime,2.7);
  assert.equal(p.video.seeks,1,'seek once to the current playhead after waiting for data');
 }finally{p.destroy();}
});

test('continuous handover retains outgoing picture and audio until a replacement frame is presented',async()=>{
 const videos=[];
 const p=new AnglePlayer([clips[0]],()=>{const v=new Video();v.style={};v.frames=new Map();v.requestVideoFrameCallback=fn=>{v.frames.set(1,fn);return 1;};v.cancelVideoFrameCallback=id=>v.frames.delete(id);videos.push(v);return v;},()=>{},{continuous:true});
 const frame=v=>{const fn=v.frames.get(1);v.frames.delete(1);assert.ok(fn);fn(0,{mediaTime:v.currentTime});};
 try{
  p.muted=false;p.update(3000,true);await settle();assert.equal(p.ready,false);assert.equal(p.active,null);
  assert.equal(videos[0].muted,true,'warm-up never duplicates program sound');frame(videos[0]);await settle();const old=p.video;
  assert.equal(old.muted,false);assert.equal(old.style.zIndex,'1');
  p.clips=clips;p.update(3100,true);await settle();const standby=p.slots.find(s=>s!==p.active);
  assert.equal(standby.video.hidden,false,'standby stays in the compositor, behind the program');assert.equal(standby.video.style.zIndex,'0');
  p.update(5100,true);await settle();assert.equal(p.video,old);assert.equal(old.hidden,false);assert.equal(old.paused,false);assert.equal(standby.video.muted,true);
  frame(standby.video);await settle();assert.equal(p.video,standby.video);assert.equal(old.hidden,true);assert.equal(old.paused,true);assert.equal(p.video.style.zIndex,'1');assert.equal(p.video.muted,false);assert.equal(p.ready,true);
 }finally{p.destroy();}
});

test('closing during a frame-confirmed handover cancels the callback and cannot restart video',async()=>{
 const videos=[],p=new AnglePlayer([clips[0]],()=>{const v=new Video();v.frames=new Map();v.requestVideoFrameCallback=fn=>{v.frames.set(1,fn);return 1;};v.cancelVideoFrameCallback=id=>v.frames.delete(id);videos.push(v);return v;},()=>{},{continuous:true});
 p.update(0,true);await settle();assert.equal(videos[0].frames.size,1);p.destroy();await settle();
 assert.equal(videos[0].frames.size,0);assert.equal(videos[0].paused,true);assert.equal(p.active,null);
});

test('continuous output does not reset and nudge playback speed on every clock tick',async()=>{
 const rates=[],p=new AnglePlayer([clips[0]],()=>{const v=new Video();let rate=1;Object.defineProperty(v,'playbackRate',{get:()=>rate,set:value=>{rates.push(value);rate=value;}});return v;},()=>{},{continuous:true});
 try{
  p.update(3000,true);await settle();const v=p.video;rates.length=0;
  for(let t=3100;t<=4000;t+=100){v._time=t/1000-.12;p.update(t,true);await settle();}
  assert.deepEqual(rates,[],'normal 120 ms native/clock drift must not cause twenty rate changes per second');
 }finally{p.destroy();}
});

test('a needed live speed correction is held steady between once-per-second checks',async()=>{
 const rates=[],p=new AnglePlayer([clips[0]],()=>{const v=new Video();let rate=1;Object.defineProperty(v,'playbackRate',{get:()=>rate,set:value=>{rates.push(value);rate=value;}});return v;},()=>{},{continuous:true});
 try{
  p.update(3000,true);await settle();const v=p.video;rates.length=0;p.active.rateCorrectionAt=-10000;
  v._time=3.1;p.update(3500,true);await settle();assert.deepEqual(rates,[1.05]);
  for(let t=3600;t<=4100;t+=100){v._time=t/1000-.4;p.update(t,true);await settle();}
  assert.deepEqual(rates,[1.05],'keep the same rate instead of resetting and reapplying it');
  p.active.rateCorrectionAt=-10000;v._time=4.2;p.update(4200,true);await settle();assert.deepEqual(rates,[1.05,1]);
 }finally{p.destroy();}
});

test('footage that expires during a slow download is not briefly played before the current clip',async()=>{
 const p=new AnglePlayer([clips[0]],()=>new Video(),()=>{},{continuous:true});
 try{
  p.update(3000,true);await settle();const standby=p.slots.find(s=>s!==p.active);standby.video.readyState=1;
  p.clips=clips;p.update(5100,true);await settle();
  p.clips=[...clips,{id:'c',url:'/c',start_ms:8000,end_ms:13000}];p.update(9500,true);await settle();
  standby.video.readyState=4;standby.video.dispatchEvent(new Event('loadeddata'));await settle();
  assert.equal(p.active.clip.id,'c');assert.equal(p.video.currentTime,1.5);assert.equal(p.video.seeks,1,'never seek/play the expired b clip');
 }finally{p.destroy();}
});
