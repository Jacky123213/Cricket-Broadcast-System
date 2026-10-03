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
