const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
class Element {
  constructor() { this.value='';this.listeners={};this.options=[];this.classList={toggle(){}}; }
  addEventListener(type, handler) { (this.listeners[type] ||= []).push(handler); }
  async emit(type, event={}) { for(const handler of this.listeners[type] || []) await handler(event); }
  querySelector() { return new Element(); }
  append(element) { this.options.push(element); }
}
class Track extends Element {
  constructor(kind) { super();this.kind=kind;this.enabled=true;this.readyState='live'; }
  stop() { this.readyState='ended'; }
  getSettings() { return {width:1280,height:720,frameRate:30}; }
}
class Stream {
  constructor(tracks=[]) { this.tracks=[...tracks]; }
  get active() { return this.tracks.some(track=>track.readyState==='live'); }
  getTracks() { return [...this.tracks]; }
  getVideoTracks() { return this.tracks.filter(track=>track.kind==='video'); }
  getAudioTracks() { return this.tracks.filter(track=>track.kind==='audio'); }
  addTrack(track) { this.tracks.push(track); }
  removeTrack(track) { this.tracks=this.tracks.filter(item=>item!==track); }
}
function harness() {
  const elements=new Map(), requests=[], sockets=[], peers=[], recordings=[];
  const element=key=>{if(!elements.has(key))elements.set(key,new Element());return elements.get(key);};
  element('#resolution').value='1280x720';element('#fps').value='30';element('#microphone').value='false';
  class Socket extends Element {
    static OPEN=1;static CONNECTING=0;
    constructor(){super();this.readyState=0;this.sent=[];sockets.push(this);}
    send(text){this.sent.push(JSON.parse(text));}
    async open(){this.readyState=1;await this.emit('open');}
  }
  class Peer extends Element {
    constructor(){super();this.connectionState='new';this.tracks=[];peers.push(this);}
    addTrack(track){this.tracks.push(track);}
    async setRemoteDescription(description){this.remoteDescription=description;}
    async addIceCandidate(candidate){(this.candidates ||= []).push(candidate);}
    async createAnswer(){return {type:'answer',sdp:'answer'};}
    async setLocalDescription(description){this.localDescription=description;}
    close(){this.connectionState='closed';this.emit('connectionstatechange');}
  }
  class Recorder {
    constructor(id,stream){this.stream=stream;recordings.push(this);}
    async start(){} stop(){this.stopped=true;}
  }
  const context={document:{querySelector:element,getElementById:id=>element('#'+id),createElement:()=>new Element(),body:new Element()},
    window:{DRS:{createClientId:()=> 'camera-id',showToast(){},websocketUrl:path=>'wss://local'+path},isSecureContext:true,
      DRSOptics:{create:async raw=>({stream:raw,close(){},set(){}})},DRSRecorder:Recorder,addEventListener(){}},
    localStorage:{getItem(){return null;},setItem(){}},navigator:{userAgent:'Test',mediaDevices:{
      async getUserMedia(constraints){requests.push(constraints);return new Stream(constraints.video===false?[new Track('audio')]:[new Track('video'),...(constraints.audio?[new Track('audio')]:[])]);},
      async enumerateDevices(){return [];},addEventListener(){}}},
    WebSocket:Socket,RTCPeerConnection:Peer,setInterval(){},clearInterval(){},performance:{now:()=>0},fetch:async()=>({ok:true}),console};
  vm.createContext(context);vm.runInContext(fs.readFileSync('frontend/assets/camera.js','utf8'),context);
  return {elements,requests,sockets,peers,recordings,context,element,run:code=>vm.runInContext(code,context)};
}
test('mic changed after preview or connection reaches every peer without stopping video',async()=>{
  const h=harness();await h.run('ensureMedia()');const video=h.run('previewStream.getVideoTracks()[0]');
  h.element('#microphone').value='true';await h.run('ensureMedia()');
  assert.equal(h.requests.length,2);assert.equal(h.requests[1].video,false);
  await h.run('connect()');await h.sockets[0].open();
  assert.equal(h.sockets[0].sent[0].settings.microphone,true);
  h.element('#microphone').value='false';await h.run('syncMicrophone()');
  assert.equal(h.sockets[0].sent.at(-1).microphone,false);assert.equal(video.readyState,'live');
  h.element('#microphone').value='true';await h.run('syncMicrophone()');
  assert.equal(h.sockets[0].sent.at(-1).type,'media_changed');assert.equal(h.recordings.length,2);
  await h.run("handleSignal({console_id:'obs',signal:{session_id:'obs-1',description:{type:'offer',sdp:'obs'}}})");
  await h.run("handleSignal({console_id:'umpire',signal:{session_id:'u-1',description:{type:'offer',sdp:'umpire'}}})");
  assert.deepEqual(h.peers.map(peer=>peer.tracks.map(track=>track.kind)),[['video','audio'],['video','audio']]);
  const microphone=h.run('previewStream.getAudioTracks()[0]');microphone.stop();await microphone.emit('ended');
  assert.equal(h.sockets[0].sent.at(-1).microphone,false);assert.equal(video.readyState,'live');
});
test('adopting an analysis mic transfers ownership and updates live camera settings',async()=>{
  const h=harness();await h.run('connect()');await h.sockets[0].open();
  h.context.testMicrophone=new Stream([new Track('audio')]);
  assert.equal(h.run('adoptMicrophone(testMicrophone)'),true);
  assert.equal(h.element('#microphone').value,'true');assert.equal(h.sockets[0].sent.at(-1).microphone,true);
});
test('replaced camera peers ignore old ICE, answers and close events',async()=>{
  const h=harness();await h.run('connect()');await h.sockets[0].open();
  await h.run("handleSignal({console_id:'obs',signal:{session_id:'old',description:{type:'offer'}}})");
  await h.run("handleSignal({console_id:'obs',signal:{session_id:'new',description:{type:'offer'}}})");
  await h.peers[0].emit('connectionstatechange');
  assert.equal(h.run("peerConnections.get('obs') === undefined"),false);
  await h.run("handleSignal({console_id:'obs',signal:{session_id:'old',candidate:{candidate:'stale'}}})");
  assert.equal(h.peers[1].candidates,undefined);
  await h.run("handleSignal({console_id:'obs',signal:{session_id:'new',candidate:{candidate:'valid'}}})");
  assert.equal(h.peers[1].candidates[0].candidate,'valid');
  assert.equal(h.sockets[0].sent.at(-1).signal.session_id,'new');
});
