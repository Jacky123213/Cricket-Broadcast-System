const test=require('node:test'),assert=require('node:assert/strict');
const {PlaybackHealth,AudioMeter,intervals}=require('../frontend/broadcast/program-health.js');
const clip=(id,start_ms,end_ms)=>({id,start_ms,end_ms});
test('footage overlap is counted once; headroom stops at a real gap',()=>{
 const clips=[clip('a',0,3000),clip('b',2000,5000),clip('c',7000,9000)];
 assert.deepEqual(intervals(clips),[[0,5000],[7000,9000]]);
 const h=new PlaybackHealth();h.frame(2500,{},100);const r=h.snapshot(clips,7500,200);
 assert.equal(r.available_seconds,7);assert.equal(r.headroom_seconds,2.5);assert.equal(r.delay_seconds,5);assert.equal(r.last_frame_age_ms,100);assert.equal(r.dropped_frames,null);
});
test('late arrivals do not count historical startup clips or repeated snapshots',()=>{
 const h=new PlaybackHealth(),old=clip('old',0,2000),late=clip('late',1000,3000),onTime=clip('ok',5000,9000);
 h.ingest([old],10000,5000);assert.equal(h.late,0);h.ingest([old,late,onTime],10000,5000);assert.equal(h.late,1);h.ingest([old,late,onTime],11000,5000);assert.equal(h.late,1);
});
test('native dropped-frame counters accumulate across decoder slots and clip resets',()=>{
 const h=new PlaybackHealth();let a={droppedVideoFrames:2,totalVideoFrames:100},b={droppedVideoFrames:1,totalVideoFrames:20};const va={getVideoPlaybackQuality:()=>a},vb={getVideoPlaybackQuality:()=>b};
 h.frame(100,va,1);h.frame(101,va,2);h.frame(102,vb,3);assert.equal(h.dropped,3);assert.equal(h.total,120);
 a={droppedVideoFrames:1,totalVideoFrames:10};h.frame(103,va,4);assert.equal(h.dropped,4);assert.equal(h.total,130);
 va.src='/clips/new';a={droppedVideoFrames:5,totalVideoFrames:50};h.frame(104,va,5);assert.equal(h.dropped,9);assert.equal(h.total,180,'a new file may already have larger counters than the previous file');
 a={droppedVideoFrames:6,totalVideoFrames:5};h.frame(105,va,6);assert.equal(h.dropped,15);assert.equal(h.total,185,'a reset total resets both deltas, even if dropped count increased');
 h.errors({failures:new Map([['a',500]])});h.errors({failures:new Map([['a',500]])});assert.equal(h.decode,1);h.errors({failures:new Map([['a',600]])});assert.equal(h.decode,2);
});
test('audio is unavailable without samples, and suspended is not a zero/silence measurement',()=>{
 const m=new AudioMeter(),v={};assert.deepEqual(m.sample(v,true),{meter_state:'unavailable',meter_dbfs:null});assert.equal(m.sample(v,false).meter_state,'no_audio');
 m.context={state:'suspended'};m.nodes.set(v,{});assert.deepEqual(m.sample(v,true),{meter_state:'suspended',meter_dbfs:null});
 m.context.state='running';m.nodes.set(v,{data:new Float32Array(4),analyser:{getFloatTimeDomainData:data=>data.fill(.1)}});assert.ok(Math.abs(m.sample(v,true).meter_dbfs+20)<.01);
 m.nodes.get(v).analyser.getFloatTimeDomainData=data=>data.fill(0);assert.equal(m.sample(v,true).meter_dbfs,-120);
});
