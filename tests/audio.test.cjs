const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function setup(hasAudio){
 const calls=[],timers=[],track={readyState:'live',muted:false,stop(){calls.push('stop-track');}};
 const stream={getAudioTracks:()=>[track],getTracks:()=>[track]};
 class Context{constructor(){this.state='suspended';}resume(){calls.push('resume');this.state='running';return Promise.resolve();}close(){calls.push('close');return Promise.resolve();}createMediaStreamSource(){return {connect(){},disconnect(){}};}createAnalyser(){return {connect(){calls.push('graph');},disconnect(){},getFloatTimeDomainData(a){a.fill(.2);}};}createGain(){return {gain:{value:1},connect(){calls.push('destination');},disconnect(){}};}}
 const c={window:{AudioContext:Context},navigator:{mediaDevices:{getUserMedia:async()=>{calls.push('permission');return stream;}}},performance:{now:()=>1000},Float32Array,AbortController,setInterval:(f)=>{timers.push(f);return timers.length;},clearInterval(){},setTimeout,clearTimeout,fetch:async()=>({ok:true})};vm.createContext(c);vm.runInContext(fs.readFileSync('frontend/assets/audio.js','utf8'),c);return {c,calls,timers,stream:hasAudio?stream:null};
}
test('audio unlock precedes microphone permission; silent graph and local diagnostics work',async()=>{
 const {c,calls,timers}=setup(false),messages=[];
 const stop=await c.window.DRSAudioStart(null,'p',()=>null,m=>messages.push(m));
 assert.ok(calls.indexOf('resume')<calls.indexOf('permission'));assert.ok(calls.includes('destination'));
 timers[0]();assert.ok(messages.some(m=>m.includes('LOCAL TEST ONLY')));stop();assert.ok(calls.includes('stop-track'));
});
test('existing camera microphone is reused and not stopped by analysis cleanup',async()=>{
 const {c,calls,stream}=setup(true);const stop=await c.window.DRSAudioStart(stream,'p',()=>null,()=>{});stop();assert.ok(!calls.includes('permission'));assert.ok(!calls.includes('stop-track'));
});
test('microphone adopted by the camera survives analysis cleanup for live sound and replay',async()=>{
 const {c,calls}=setup(false);let adopted=false;
 const stop=await c.window.DRSAudioStart(null,'p',()=>null,()=>{},async()=>{adopted=true;return true;});
 assert.equal(adopted,true);stop();assert.ok(!calls.includes('stop-track'));
});
