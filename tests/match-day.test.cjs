/* Isolated program/desk integration tests. No production match or camera access. */
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
const read=p=>fs.readFileSync(p,'utf8'),settle=async()=>{await new Promise(setImmediate);await new Promise(setImmediate);};
const copy=v=>JSON.parse(JSON.stringify(v));
function page(path,url){
  const dom=new JSDOM(read(path),{url,runScripts:'outside-only'}),w=dom.window,timers=new Map();let id=0,elapsed=0;
  w.AbortSignal.timeout=()=>undefined;w.performance.now=()=>elapsed;w.Date.now=()=>1000000+elapsed;
  w.setTimeout=(fn,ms)=>{timers.set(++id,{fn,ms});return id;};w.setInterval=(fn,ms)=>{timers.set(++id,{fn,ms,interval:true});return id;};
  w.clearTimeout=w.clearInterval=id=>timers.delete(id);
  return {dom,w,d:w.document,timers,advance(ms){elapsed+=ms;},async tick(ms){for(const [id,t] of [...timers])if(t.ms===ms){if(!t.interval)timers.delete(id);await t.fn();}await settle();},close(){w.dispatchEvent(new w.Event('beforeunload'));w.close();}};
}
function payload(){return {server_ms:1000000,devices:[{device_id:'umpire',name:'Umpire',role:'UMPIRE_POV'},{device_id:'crease',name:'Crease',role:'OTHER'}],program:{revision:1,camera_id:'umpire',mode:'live',review_id:null,review:null,playing:true,position_ms:0,speed:1,anchor_ms:1000000,muted:false,retry_token:0}};}
async function output(search='?follow=1&clean=1&client=obs&audio=1'){
  const h=page('frontend/broadcast/index.html','https://local/broadcast'+search),{w,d}=h;let data=payload(),fail=false;const buffers=[],players=[],requests=[];
  w.DRS={createClientId:()=> 'client123456'};w.HTMLMediaElement.prototype.play=async function(){this._paused=false;};w.HTMLMediaElement.prototype.pause=function(){this._paused=true;};
  function video(v){v.hidden=false;v.currentTime=0;Object.defineProperty(v,'readyState',{get:()=>4});}
  class Buffered{
    constructor(id,mount,callbacks){this.id=id;this.callbacks=callbacks;const v=d.createElement('video');video(v);mount.append(v);this.player={slots:[{video:v}],active:{video:v}};this.h={delay_seconds:5,available_seconds:42,headroom_seconds:2,last_frame_age_ms:0,dropped_frames:null,total_frames:null,late_clips:0,decode_errors:0,poll_errors:0};buffers.push(this);}
    healthSnapshot(){return this.h;}setMuted(muted){this.muted=muted;for(const s of this.player.slots)s.video.muted=muted;}resume(){this.resumed=true;}destroy(){this.closed=true;this.player.slots.forEach(s=>s.video.remove());}
  }
  class Angle{
    constructor(clips,create){this.clips=clips;this.slots=[{video:create()},{video:create()}];this.slots.forEach(s=>video(s.video));this.active=this.slots[0];this.active.clip=clips[0];this.ready=true;this.waiting=false;this.failures=new Map();players.push(this);}
    update(at,playing,speed,force){this.last={at,playing,speed,force};this.active.video.currentTime=(at-this.active.clip.start_ms)/1000;this.active.video.hidden=false;}retry(){}destroy(){this.closed=true;this.slots.forEach(s=>s.video.remove());}
  }
  w.DRSBufferedBroadcast=Buffered;w.DRSPlayback={AnglePlayer:Angle};w.eval(read('frontend/broadcast/program-health.js'));
  class Meter{
    constructor(){this.nodes=new Map();this.context=null;this.outputMuted=true;this.closed=false;}
    async start(videos){this.context={state:'running'};videos.forEach(v=>this.nodes.set(v,{}));return true;}mute(v){this.outputMuted=v;}
    sample(video,audio){return {meter_state:audio&&this.nodes.has(video)?'active':audio?'unavailable':'no_audio',meter_dbfs:audio&&this.nodes.has(video)?-18:null};}
    reset(){this.nodes.clear();}close(){this.closed=true;this.reset();}
  }
  const meters=[];w.DRSProgramHealth.AudioMeter=class extends Meter{constructor(){super();meters.push(this);}};
  w.fetch=async(url,options={})=>{if(fail&&url==='/api/broadcast/program')throw Error('Offline');if(options.method==='POST'){const body=JSON.parse(options.body);requests.push({url,body});if(url.endsWith('/program')){data.program.revision++;if(body.action==='audio')data.program.muted=body.muted;if(body.action==='retry')data.program.retry_token++;}return {ok:true,json:async()=>copy(data)};}return {ok:true,json:async()=>copy(data)};};
  w.eval(read('frontend/broadcast/program-output.js'));await settle();
  return {...h,buffers,players,meters,requests,data,setData(v){data=v;},setFail(v){fail=v;},health:()=>w.CricketProgram.health()};
}
test('shared output follows commands without restarting on each poll; selected offline source never substitutes',async()=>{
  const h=await output();try{
    assert.equal(h.buffers.length,1);assert.equal(h.d.getElementById('controls').hidden,true);assert.equal(h.buffers[0].muted,false);
    await h.tick(750);assert.equal(h.buffers.length,1);
    h.data.program.camera_id='crease';h.data.program.revision++;await h.tick(750);assert.equal(h.buffers[0].closed,true);assert.equal(h.buffers[1].id,'crease');
    h.data.devices=h.data.devices.filter(d=>d.device_id!=='crease');await h.tick(750);assert.equal(h.buffers[1].closed,true);assert.equal(h.buffers.length,2);assert.equal(h.health().state,'offline');assert.equal(h.d.getElementById('camera').value,'crease');
    h.data.devices.push({device_id:'crease',name:'Crease',role:'OTHER'});await h.tick(750);assert.equal(h.buffers.length,3);
    h.data.program.retry_token++;h.data.program.revision++;await h.tick(750);assert.equal(h.buffers[2].closed,true);assert.equal(h.buffers.length,4);
  }finally{h.close();}assert.equal(h.timers.size,0);
});
test('playing health requires advancing decoded frames, authentic graphics reports, and a measured audio signal',async()=>{
  const h=await output();try{
    const b=h.buffers[0];b.callbacks.onFrame({at:995000,delay:5,audio:true});assert.equal(h.health().state,'playing');assert.equal(h.health().meter_state,'unavailable');
    const graphic=h.d.getElementById('graphic');h.w.dispatchEvent(new h.w.MessageEvent('message',{origin:'https://evil',source:graphic.contentWindow,data:{type:'broadcast-graphics-status',kind:'batting_card'}}));assert.equal(h.health().graphics_kind,null);
    h.w.dispatchEvent(new h.w.MessageEvent('message',{origin:'https://local',source:graphic.contentWindow,data:{type:'broadcast-graphics-status',kind:'batting_card',surge:false}}));assert.equal(h.health().graphics_kind,'batting_card');
    await h.w.CricketProgram.enableMeter();assert.equal(h.health().meter_dbfs,-18);assert.equal(h.meters[0].outputMuted,false);
    h.data.program.muted=true;await h.tick(750);assert.equal(h.health().muted,true);assert.equal(h.meters[0].outputMuted,true);assert.equal(h.health().meter_dbfs,-18,'meter is explicitly before playback mute');
    b.h.last_frame_age_ms=900;assert.equal(h.health().state,'buffering');assert.equal(h.health().meter_dbfs,null,'a stopped picture must not keep an active audio reading');
    b.h.last_frame_age_ms=0;h.setFail(true);await h.tick(750);assert.equal(h.health().state,'error');assert.equal(h.health().meter_dbfs,null);
    h.setFail(false);await h.tick(750);assert.equal(h.health().state,'playing');await h.tick(1000);assert.equal(h.requests.at(-1).body.role,'obs');assert.equal(h.requests.at(-1).body.client_id,'obs-client123456');
  }finally{h.close();}assert.equal(h.meters[0].closed,true);
});
test('preview can measure audio but remains silent across mute changes, retries and camera cuts',async()=>{
  const h=await output('?follow=1&client=preview&audio=1');try{
    const b=h.buffers[0];b.callbacks.onFrame({at:995000,delay:5,audio:true});assert.equal(b.muted,true);await h.w.CricketProgram.enableMeter();assert.equal(h.health().muted,true);assert.equal(h.meters[0].outputMuted,true);
    h.data.program.camera_id='crease';h.data.program.revision++;await h.tick(750);assert.equal(h.meters[0].outputMuted,true);assert.equal(h.health().muted,true);
    h.buffers[1].callbacks.onFrame({at:995000,delay:5,audio:true});assert.equal(h.health().meter_state,'active');
  }finally{h.close();}
});
test('shared replay hides live score, supports paused/seek/end hold, returns to delayed live',async()=>{
  const h=await output();try{
    Object.assign(h.data.program,{mode:'replay',revision:2,review_id:'review1',position_ms:0,playing:false,review:{id:'review1',start_ms:985000,end_ms:995000,clips:[{id:'r1',device_id:'umpire',start_ms:980000,end_ms:1000000,audio:true}]}});
    await h.tick(750);await h.tick(100);assert.equal(h.buffers[0].closed,true);assert.equal(h.players.length,1);assert.equal(h.d.getElementById('graphic').hidden,true);assert.equal(h.d.getElementById('replayBadge').hidden,false);assert.equal(h.health().state,'paused');assert.equal(h.health().graphics_kind,'hidden');assert.equal(h.d.getElementById('empty').hidden,true);
    h.advance(2000);await h.tick(100);assert.equal(h.health().state,'paused','age alone must not turn an intentionally held frame into buffering');
    h.data.program.position_ms=4000;h.data.program.revision++;await h.tick(750);await h.tick(100);assert.equal(h.players.length,1);assert.equal(h.players[0].last.at,989000);
    h.data.program.playing=true;await h.tick(750);h.advance(10000);await h.tick(100);assert.equal(h.health().state,'paused','replay end stays held, not an automatic live switch');
    h.players[0].ready=false;assert.equal(h.health().state,'playing','recent frame while preparing is not labelled intentional pause');h.advance(1000);await h.tick(100);assert.equal(h.health().state,'buffering');
    Object.assign(h.data.program,{mode:'live',review_id:null,review:null,revision:4});await h.tick(750);assert.equal(h.players[0].closed,true);assert.equal(h.buffers.length,2);assert.equal(h.d.getElementById('graphic').hidden,false);
  }finally{h.close();}assert.equal(h.timers.size,0);
});
test('fixed broadcast URL leaves shared engine disabled',async()=>{
  const h=page('frontend/broadcast/index.html','https://local/broadcast?camera=umpire&clean=1');try{h.w.eval(read('frontend/broadcast/program-output.js'));assert.equal(h.w.CricketProgram,undefined);assert.equal(h.timers.size,0);}finally{h.close();}
});
function score(){return {score:{source:'bluetooth',team1:'Test XI',runs:'44',wickets:'0',overs:'4.2',visible:true},last_score:995,server_time:1000,graphics:{innings:[{team:'Test XI'}],active:null,power_surge:false}};}
function report(role='preview'){return {client_id:role+'-client123456',role,camera_id:'umpire',mode:'live',revision:1,state:'playing',report_age_ms:200,delay_seconds:5.2,available_seconds:42,headroom_seconds:1.2,last_frame_age_ms:100,dropped_frames:2,total_frames:900,late_clips:1,decode_errors:0,poll_errors:0,muted:role==='preview',meter_state:'active',meter_dbfs:-20,graphics_kind:'batting_card',graphics_surge:false};}
async function desk(){const h=page('frontend/match-day/index.html','https://local/match-day'),data={program:payload(),score:score(),health:{server_ms:1000000,clients:[report()]}},requests=[];let fail=false;
  h.w.fetch=async(url,options={})=>{if(fail)throw Error('Network offline');if(options.method==='POST'){requests.push({url,body:JSON.parse(options.body)});return {ok:true,json:async()=>copy(data.program)};}const result=url==='/api/broadcast/program'?data.program:url==='/api/scoreboard/state'?data.score:url==='/api/broadcast/health'?data.health:{addresses:['https://192.168.1.68:8765']};return {ok:true,json:async()=>copy(result)};};
  h.w.eval(read('frontend/match-day/match-day.js'));await settle();return {...h,data,requests,setFail(v){fail=v;}};
}
test('desk distinguishes local/OBS playback, stale/wrong command reports, and clears all readings when disconnected',async()=>{
  const h=await desk(),text=id=>h.d.getElementById(id).textContent;try{
    assert.equal(text('healthSummary'),'LOCAL PREVIEW ONLY');assert.equal(text('liveScore'),'0–44');assert.match(text('sharedOutputUrl'),/follow=1&clean=1&client=obs&audio=1/);
    h.data.health.clients.push(report('obs'));await h.tick(1000);assert.equal(text('healthSummary'),'OBS PLAYING');assert.equal(text('healthDelay'),'5.2 s');assert.equal(text('healthGraphic'),'Batting card');assert.match(text('programAudioLevel'),/-20.0 dBFS/);
    h.data.health.clients[1].report_age_ms=4000;await h.tick(1000);assert.equal(text('healthSummary'),'OUTPUT STALE / OFFLINE');assert.equal(text('healthDelay'),'—');assert.equal(h.d.getElementById('programAudioMeter').value,-60);
    h.data.health.clients[1].report_age_ms=0;h.data.program.program.revision=2;await h.tick(1000);assert.equal(text('healthSummary'),'APPLYING COMMAND');assert.equal(text('healthDropped'),'Unavailable');
    h.data.health.clients[1].revision=2;await h.tick(1000);assert.equal(text('healthSummary'),'OBS PLAYING');h.setFail(true);await h.tick(1000);assert.equal(text('healthSummary'),'SERVER UNAVAILABLE');assert.equal(text('healthDelay'),'—');assert.equal(text('healthGraphic'),'—');assert.equal(text('programTally'),'CONTROL LINK LOST');
    h.setFail(false);await h.tick(1000);assert.equal(text('healthSummary'),'OBS PLAYING');
  }finally{h.close();}
});
test('desk actions send scoped production commands and leave corrections/end-match actions separate',async()=>{
  const h=await desk();try{
    h.d.querySelector('[data-program-replay="30"]').click();await settle();assert.deepEqual(h.requests.at(-1),{url:'/api/broadcast/program',body:{action:'replay',seconds:30}});
    h.d.querySelector('[data-graphic="batting_card"]').click();await settle();assert.deepEqual(h.requests.at(-1),{url:'/api/scoreboard/broadcast/action',body:{action:'show',kind:'batting_card',innings:0}});
    h.d.getElementById('programAudio').click();await settle();assert.equal(h.requests.at(-1).body.action,'audio');assert.equal(h.requests.at(-1).body.muted,true);
    h.d.getElementById('reopenProgramScore').click();await settle();assert.equal(h.requests.at(-1).body.action,'hide');
    assert.equal(h.d.querySelector('#endMatch,#newMatch,#statsEditor'),null);assert.ok(h.d.querySelector('a[href="/scoreboard#statsEditor"]'));
    h.data.health.clients[0].dropped_frames=null;h.data.health.clients[0].total_frames=null;h.data.health.clients[0].meter_state='unavailable';h.data.health.clients[0].meter_dbfs=null;await h.tick(1000);assert.equal(h.d.getElementById('healthDropped').textContent,'Unavailable');assert.match(h.d.getElementById('programAudioLevel').textContent,/unavailable/);
  }finally{h.close();}
});
test('initial no-camera report is offline, not stuck applying a null source',async()=>{
  const h=await desk();try{h.data.program.program.camera_id=null;h.data.program.program.revision=0;Object.assign(h.data.health.clients[0],{camera_id:'',revision:0,state:'offline'});await h.tick(1000);assert.equal(h.d.getElementById('programTally').textContent,'NO CAMERA');assert.equal(h.d.getElementById('healthSummary').textContent,'LOCAL · OFFLINE');}finally{h.close();}
});
