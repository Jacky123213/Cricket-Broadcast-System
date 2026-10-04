const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');

class Element {
  constructor() { this.listeners = {}; this.hidden = false; this.value = ''; this.children = []; this.textContent = ''; }
  addEventListener(type, handler) { (this.listeners[type] ||= []).push(handler); }
  emit(type, event = {}) { return Promise.all((this.listeners[type] || []).map(handler => handler({target: this, ...event}))); }
  replaceChildren(...children) { this.children = children; this.value = children[0]?.value || ''; }
}
class Stream {
  constructor(tracks = []) { this.tracks = [...tracks]; }
  getTracks() { return this.tracks; }
  getVideoTracks() { return this.tracks.filter(track => track.kind === 'video'); }
  getAudioTracks() { return this.tracks.filter(track => track.kind === 'audio'); }
  addTrack(track) { this.tracks.push(track); }
}
const camera = (id, role = 'OTHER', microphone = false) => ({device_id: id, name: id, role, settings: {microphone}});
const settle = async () => { await new Promise(resolve => setImmediate(resolve)); await new Promise(resolve => setImmediate(resolve)); };

function harness(search = '', options = {}) {
  if(!options.buffered){const params=new URLSearchParams(search);params.set('delay','0');search='?'+params;}
  const elements = Object.fromEntries(['camera','program','bufferedStage','empty','status','graphic','controls','retry','showGraphic','mute','copyOutput','sound','audioNotice'].map(id => ['#' + id, new Element()]));
  elements['#audioNotice'].hidden = true;
  const emptyTitle = new Element(), emptyDetail = new Element();
  elements['#empty'].querySelector = selector => selector === 'strong' ? emptyTitle : emptyDetail;
  const video = elements['#program']; video.muted = true; video.playCalls = 0;
  video.play = () => { video.playCalls++; if (options.play) return options.play(video); if (options.blockPlay || (options.blockSound && !video.muted)) return Promise.reject(Error('Playback blocked')); video.emit('playing'); return Promise.resolve(); };
  const peers = [], sockets = [], timers = new Map(), stored = new Map(), warnings = [], clipboard = [], buffers=[];
  elements['#graphic'].contentWindow={postMessage:(data,origin)=>buffers.at(-1).messages.push({data,origin})};
  class Buffered{constructor(id,mount,callbacks){this.id=id;this.mount=mount;this.callbacks=callbacks;this.messages=[];buffers.push(this);}setMuted(value){this.muted=value;}resume(){this.resumed=true;}destroy(){this.closed=true;}}
  let nextTimer = 0, nextId = 0;
  class Peer extends Element {
    constructor() { super(); this.connectionState = 'new'; this.transceivers = []; this.candidates = []; peers.push(this); }
    addTransceiver(kind) { this.transceivers.push(kind); }
    createOffer() { return options.offer ? options.offer(this) : Promise.resolve({type:'offer',sdp:'test-offer'}); }
    async setLocalDescription(description) { this.localDescription = description; if (options.earlyIce) this.emit('icecandidate',{candidate:{toJSON:()=>({candidate:'local-ice'})}}); }
    async setRemoteDescription(description) { this.remoteDescription = description; }
    async addIceCandidate(candidate) { assert.ok(this.remoteDescription, 'ICE must wait for the remote SDP'); this.candidates.push(candidate); }
    close() { this.closed = true; this.connectionState = 'closed'; this.emit('connectionstatechange'); }
  }
  class Socket extends Element {
    static OPEN = 1;
    constructor(url) { super(); this.url = url; this.readyState = 1; this.sent = []; sockets.push(this); }
    send(data) { this.sent.push(JSON.parse(data)); }
    close() { this.readyState = 3; this.emit('close'); }
    message(data) { return this.emit('message', {data: JSON.stringify(data)}); }
  }
  const context = {document:{querySelector: selector => { assert.ok(elements[selector], selector); return elements[selector]; }, createElement:()=>new Element()},
    window:{DRSBufferedBroadcast:Buffered,DRS:{createClientId:()=>String(++nextId),formatRole:role=>role.replaceAll('_',' '),websocketUrl:path=>'wss://local'+path},addEventListener(){}},
    location:{search,href:'https://local/broadcast'+search,origin:'https://local'},localStorage:{getItem:key=>stored.get(key),setItem:(key,value)=>stored.set(key,value)},
    navigator:{clipboard:{writeText:async text=>clipboard.push(text)}},URL,URLSearchParams,MediaStream:Stream,RTCPeerConnection:Peer,WebSocket:Socket,
    setTimeout:(fn,ms)=>{ const id=++nextTimer;timers.set(id,{fn,ms});return id; },clearTimeout:id=>timers.delete(id),console:{warn:(...items)=>warnings.push(items)}};
  vm.createContext(context); vm.runInContext(fs.readFileSync('frontend/broadcast/broadcast.js','utf8'),context);
  return {elements,peers,sockets,stored,warnings,clipboard,emptyTitle,context,buffers,
    async roster(list) { await sockets.at(-1).message({type:'devices',devices:list}); await settle(); },
    async signal(signal,id=elements['#camera'].value) { await sockets.at(-1).message({type:'webrtc_signal',device_id:id,signal}); await settle(); },
    async tick(ms) { for(const [id,timer] of [...timers]) if(timer.ms===ms) {timers.delete(id);timer.fn();} await settle(); }};
}

test('broadcast chooses umpire POV and does not restart on repeated device snapshots', async () => {
  const h = harness(); await h.roster([camera('crease'),camera('umpire','UMPIRE_POV')]);
  assert.equal(h.elements['#camera'].value,'umpire'); assert.equal(h.peers.length,1);
  assert.deepEqual(h.peers[0].transceivers,['video','audio']);
  await h.roster([camera('crease'),camera('umpire','UMPIRE_POV'),camera('extra')]);
  assert.equal(h.peers.length,1); assert.equal(h.sockets[0].sent.length,1);
});

test('default program uses delayed clips, sends actual frame time to graphics and keeps mic changes in sequence',async()=>{
  const h=harness('',{buffered:true});await h.roster([camera('umpire','UMPIRE_POV',true)]);
  assert.equal(h.peers.length,0);assert.equal(h.buffers.length,1);assert.equal(h.elements['#graphic'].src,'/overlay?program=1');
  const buffer=h.buffers[0];assert.equal(buffer.muted,false);
  buffer.callbacks.onFrame({at:100000,delay:5.1,audio:true});
  assert.equal(h.elements['#empty'].hidden,true);assert.match(h.elements['#status'].textContent,/DELAYED 5.1 s/);assert.equal(h.elements['#sound'].textContent,'Camera audio on');
  assert.equal(buffer.messages[0].data.at,100);assert.equal(buffer.messages[0].origin,'https://local');
  await h.roster([{...camera('umpire','UMPIRE_POV'),settings:{microphone:false,media_revision:2}}]);assert.equal(h.buffers.length,1);
  await h.elements['#mute'].emit('click');assert.equal(buffer.muted,true);assert.equal(buffer.resumed,true);
  await h.roster([camera('other')]);assert.equal(buffer.closed,true);assert.equal(h.buffers.length,2);
  buffer.callbacks.onFrame({at:90000,delay:15,audio:true});assert.equal(h.elements['#empty'].hidden,false,'stale camera must not display a frame');
});
test('early remote ICE is queued until the answer, and legacy camera replies still work', async () => {
  const h = harness(); await h.roster([camera('umpire')]);
  await h.signal({candidate:{candidate:'remote-ice'}}); assert.equal(h.peers[0].candidates.length,0);
  await h.signal({description:{type:'answer',sdp:'answer'}}); assert.equal(h.peers[0].candidates[0].candidate,'remote-ice');
  assert.equal(h.warnings.length,0);
});
test('camera gets the offer before local ICE generated during setLocalDescription', async () => {
  const h = harness('',{earlyIce:true}); await h.roster([camera('phone')]);
  const sent=h.sockets[0].sent; assert.equal(sent.length,2); assert.equal(sent[0].signal.description.type,'offer');
  assert.equal(sent[1].signal.candidate.candidate,'local-ice'); assert.equal(sent[0].signal.session_id,sent[1].signal.session_id);
});
test('streamless video track starts playback and removes the waiting panel', async () => {
  const h = harness(); await h.roster([camera('phone')]);
  await h.peers[0].emit('track',{track:{id:'video-1',kind:'video'},streams:[]}); await settle();
  assert.equal(h.elements['#program'].playCalls,1); assert.equal(h.elements['#program'].srcObject.getVideoTracks().length,1);
  assert.equal(h.elements['#empty'].hidden,true); assert.equal(h.elements['#status'].textContent,'LIVE · phone');
  const css=fs.readFileSync('frontend/broadcast/broadcast.css','utf8'); assert.match(css,/\[hidden\]\s*\{display:none!important\}/);
});
test('camera switching closes the old peer and ignores its late track and signals', async () => {
  const h = harness(); await h.roster([camera('a'),camera('b')]); const old=h.peers[0], oldSession=h.sockets[0].sent[0].signal.session_id;
  h.elements['#camera'].value='b'; await h.elements['#camera'].emit('change'); await settle();
  assert.equal(old.closed,true); assert.equal(h.peers.length,2);
  await old.emit('track',{track:{id:'old',kind:'video'},streams:[]}); assert.equal(h.elements['#program'].srcObject,null);
  await h.signal({session_id:oldSession,description:{type:'answer',sdp:'late'}},'b'); assert.equal(h.peers[1].remoteDescription,undefined);
  await h.peers[1].emit('track',{track:{id:'new',kind:'video'},streams:[]}); assert.equal(h.elements['#status'].textContent,'LIVE · b');
});
test('failed video retries automatically; removing that camera does not block a different feed', async () => {
  const h=harness(); await h.roster([camera('a'),camera('b')]); h.peers[0].connectionState='failed'; await h.peers[0].emit('connectionstatechange');
  await h.tick(1500); assert.equal(h.peers.length,2);
  h.peers[1].connectionState='failed'; await h.peers[1].emit('connectionstatechange');
  await h.roster([camera('b')]); assert.equal(h.elements['#camera'].value,'b'); assert.equal(h.peers.length,3);
});
test('server reconnect closes old video and creates a new link after the new roster', async () => {
  const h=harness(); await h.roster([camera('phone')]); h.sockets[0].close(); assert.equal(h.peers[0].closed,true);
  assert.equal(h.elements['#camera'].disabled,true); await h.tick(1500); assert.equal(h.sockets.length,2);
  await h.roster([camera('phone')]); assert.equal(h.peers.length,2); assert.equal(h.sockets[1].sent[0].device_id,'phone');
});
test('fixed clean OBS link waits for its requested camera, then starts it without visible controls', async () => {
  const h=harness('?camera=phone-b&clean=1'); await h.roster([camera('phone-a')]);
  assert.equal(h.elements['#controls'].hidden,true); assert.equal(h.peers.length,0); assert.equal(h.elements['#camera'].value,'');
  await h.roster([camera('phone-a'),camera('phone-b')]); assert.equal(h.peers.length,1); assert.equal(h.elements['#camera'].value,'phone-b');
  await h.elements['#copyOutput'].emit('click'); const url=new URL(h.clipboard[0]); assert.equal(url.searchParams.get('camera'),'phone-b'); assert.equal(url.searchParams.get('clean'),'1');
});
test('no-picture timeout retries instead of leaving a permanently black output', async () => {
  const h=harness(); await h.roster([camera('phone')]); await h.tick(15000);
  assert.match(h.elements['#status'].textContent,/No camera picture/); await h.tick(1500); assert.equal(h.peers.length,2);
});
test('obsolete asynchronous offers cannot signal or overwrite the selected camera', async () => {
  const waiting=[]; const h=harness('',{offer:()=>new Promise(resolve=>waiting.push(resolve))});
  await h.roster([camera('a'),camera('b')]); h.elements['#camera'].value='b'; await h.elements['#camera'].emit('change');
  waiting[0]({type:'offer',sdp:'old'}); waiting[1]({type:'offer',sdp:'new'}); await settle();
  assert.equal(h.sockets[0].sent.length,1); assert.equal(h.sockets[0].sent[0].device_id,'b');
});

test('enabling or replacing the camera mic renegotiates exactly once per media revision', async () => {
  const h=harness(); await h.roster([camera('phone')]);
  const enabled=camera('phone','UMPIRE_POV',true); enabled.settings.media_revision=1;
  await h.roster([enabled]); assert.equal(h.peers.length,2); assert.equal(h.peers[0].closed,true);
  await h.roster([enabled]); assert.equal(h.peers.length,2);
  enabled.settings.media_revision=2; await h.roster([enabled]); assert.equal(h.peers.length,3);
});

test('clean OBS URLs enable sound by default and preserve an explicit mute choice', async () => {
  const h=harness(); await h.roster([camera('phone','UMPIRE_POV',true)]);
  assert.equal(h.elements['#program'].muted,false);
  await h.elements['#copyOutput'].emit('click'); assert.equal(new URL(h.clipboard[0]).searchParams.get('audio'),'1');
  await h.elements['#mute'].emit('click'); await h.elements['#copyOutput'].emit('click');
  assert.equal(new URL(h.clipboard[1]).searchParams.get('audio'),'0');
  const muted=harness('?clean=1&audio=0'); assert.equal(muted.elements['#program'].muted,true);
});

test('blocked audio autoplay retains the live picture and exposes an unlock button in clean mode', async () => {
  const options={blockSound:true}, h=harness('?clean=1&audio=1',options);
  await h.roster([camera('phone','UMPIRE_POV',true)]);
  await h.peers[0].emit('track',{track:{id:'video',kind:'video'},streams:[]}); await settle();
  await h.peers[0].emit('track',{track:{id:'mic',kind:'audio',readyState:'live'},streams:[]}); await settle();
  assert.equal(h.elements['#empty'].hidden,true); assert.equal(h.elements['#program'].muted,true);
  assert.equal(h.elements['#audioNotice'].hidden,false); assert.match(h.elements['#sound'].textContent,/received/);
  options.blockSound=false; await h.elements['#audioNotice'].emit('click'); await settle();
  assert.equal(h.elements['#program'].muted,false); assert.equal(h.elements['#audioNotice'].hidden,true);
});

test('an obsolete play rejection during audio/video track arrival cannot mute the new playback', async () => {
  let rejectOld;
  const h=harness('',{play:video=>video.playCalls===1?new Promise((_,reject)=>rejectOld=reject):
    (video.emit('playing'),Promise.resolve())});
  await h.roster([camera('phone','UMPIRE_POV',true)]);
  await h.peers[0].emit('track',{track:{id:'video',kind:'video'},streams:[]});
  await h.peers[0].emit('track',{track:{id:'mic',kind:'audio'},streams:[]});
  rejectOld(Object.assign(Error('Replaced playback'),{name:'AbortError'}));await settle();
  assert.equal(h.elements['#program'].muted,false);assert.equal(h.elements['#empty'].hidden,true);
});
