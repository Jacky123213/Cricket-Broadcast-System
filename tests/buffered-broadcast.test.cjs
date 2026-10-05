const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
test('five-second playout uses native clip timestamps and destroys polling/decoders',async()=>{
 const intervals=new Map(),timeouts=new Map(),frames=[],videos=[],statuses=[];let local=200,player;
 class Player{constructor(clips,makeVideo){this.clips=clips;this.slots=[0,1].map(()=>({video:makeVideo()}));player=this;}update(t,playing,rate){this.request={t,playing,rate};}play(){this.resumed=true;}destroy(){this.closed=true;}}
 const context={window:{DRSPlayback:{AnglePlayer:Player}},document:{createElement:()=>{const v={play:async()=>{},setAttribute(){}};videos.push(v);return v;}},performance:{now:()=>local},fetch:async()=>({ok:true,json:async()=>({server_ms:10000,clips:[{id:'one',start_ms:4000,end_ms:9000,audio:true}],recorder:null})}),AbortController,
 setTimeout:(fn,ms)=>{const id=timeouts.size+1;timeouts.set(id,{fn,ms});return id;},clearTimeout:id=>timeouts.delete(id),setInterval:(fn,ms)=>{intervals.set(1,{fn,ms});return 1;},clearInterval:id=>intervals.delete(id)};
 vm.createContext(context);vm.runInContext(fs.readFileSync('frontend/broadcast/buffered-broadcast.js','utf8'),context);
 const b=new context.window.DRSBufferedBroadcast('test',{append(){}},{onFrame:f=>frames.push(f),onStatus:s=>statuses.push(s),onBuffering(){},onMute(){}});
 await new Promise(r=>setImmediate(r));assert.equal(player.request.t,5000);assert.equal(player.request.playing,true);assert.equal(player.clips.length,1);
 b.setMuted(false);assert.ok(videos.every(v=>v.muted===false));
 player.ready=true;player.active={clip:player.clips[0],video:{hidden:false,paused:false,readyState:4,currentTime:1.05}};
 local=250;b.tick();assert.equal(frames[0].at,5050);assert.equal(frames[0].delay,5);assert.equal(frames[0].audio,true);
 b.resume();assert.equal(player.resumed,true);b.destroy();assert.equal(player.closed,true);assert.equal(intervals.size,0);assert.equal(timeouts.size,0);
});

test('blocked unmuted autoplay falls back to muted video with an unlock notice',async()=>{
 let player;let blocked=true,notices=0;
 class Player{constructor(clips,makeVideo){this.slots=[{video:makeVideo()}];player=this;}update(){}destroy(){}}
 const context={window:{DRSPlayback:{AnglePlayer:Player}},document:{createElement:()=>({muted:true,setAttribute(){},play:async function(){if(blocked&&!this.muted)throw Object.assign(Error('blocked'),{name:'NotAllowedError'});}})},performance:{now:()=>0},fetch:async()=>({ok:true,json:async()=>({server_ms:10000,clips:[]})}),AbortController,setTimeout:()=>1,clearTimeout(){},setInterval:()=>2,clearInterval(){}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('frontend/broadcast/buffered-broadcast.js','utf8'),context);
 const b=new context.window.DRSBufferedBroadcast('test',{append(){}},{onFrame(){},onStatus(){},onBuffering(){},onMute:()=>notices++});await new Promise(r=>setImmediate(r));
 b.setMuted(false);await player.slots[0].video.play();assert.equal(notices,1);assert.equal(player.slots[0].video.muted,true);b.destroy();
});

test('brief decoder swaps do not flash buffering; real stalls report once and recover',async()=>{
 let player,local=0,buffered=0;const frames=[];
 class Player{constructor(clips,makeVideo,status,options){this.slots=[{video:makeVideo()}];this.options=options;player=this;}update(){}destroy(){}}
 const context={window:{DRSPlayback:{AnglePlayer:Player}},document:{createElement:()=>({muted:true,setAttribute(){},play:async()=>{}})},performance:{now:()=>local},fetch:async()=>({ok:true,json:async()=>({server_ms:10000,clips:[]})}),AbortController,setTimeout:()=>1,clearTimeout(){},setInterval:()=>2,clearInterval(){}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('frontend/broadcast/buffered-broadcast.js','utf8'),context);
 const b=new context.window.DRSBufferedBroadcast('test',{append(){}},{onFrame:f=>frames.push(f),onStatus(){},onBuffering:()=>buffered++,onMute(){}});await new Promise(r=>setImmediate(r));
 assert.equal(player.options.continuous,true);
 player.ready=true;player.active={clip:{id:'a',start_ms:4000,audio:true},video:{hidden:false,paused:false,readyState:4,currentTime:1}};
 b.tick();assert.equal(frames.length,1);
 local=100;player.ready=false;player.active.video.paused=true;b.tick();
 local=300;b.tick();assert.equal(buffered,0);
 local=400;player.ready=true;player.active.video.paused=false;player.active.video.currentTime=1.4;b.tick();assert.equal(buffered,0);
 // A decoder can stall without setting paused. Actual timestamp progress counts.
 local=500;b.tick();local=1250;b.tick();local=1500;b.tick();assert.equal(buffered,1);
 local=1600;player.active.video.currentTime=2.6;b.tick();assert.equal(b.buffering,false);assert.equal(frames.at(-1).at,6600);b.destroy();
});

test('high-latency clock polls cannot jerk continuous playout',async()=>{
 let local=0;
 class Player{constructor(clips,makeVideo){this.slots=[{video:makeVideo()}];}update(){}destroy(){}}
 const context={window:{DRSPlayback:{AnglePlayer:Player}},document:{createElement:()=>({setAttribute(){},play:async()=>{}})},performance:{now:()=>local},fetch:async()=>({ok:true,json:async()=>({server_ms:10000,clips:[]})}),AbortController,setTimeout:()=>1,clearTimeout(){},setInterval:()=>2,clearInterval(){}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('frontend/broadcast/buffered-broadcast.js','utf8'),context);
 const b=new context.window.DRSBufferedBroadcast('test',{append(){}},{onFrame(){},onStatus(){},onBuffering(){},onMute(){}});await new Promise(r=>setImmediate(r));
 local=2000;const before=b.now();b.syncClock(20000,500,2000);assert.equal(b.now(),before,'a slow poll does not replace the best clock sample');
 // Even after old samples age out, a new estimate is slewed, not jumped.
 local=65000;const later=b.now();b.syncClock(90000,64990,65000);assert.ok(Math.abs(b.now()-later)<=25);b.destroy();
});
