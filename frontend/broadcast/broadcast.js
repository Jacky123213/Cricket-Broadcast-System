"use strict";

if(new URLSearchParams(location.search).get('follow')!=='1'){

const select = document.querySelector('#camera'), video = document.querySelector('#program');
const empty = document.querySelector('#empty'), status = document.querySelector('#status');
const graphic = document.querySelector('#graphic'), controls = document.querySelector('#controls');
const muteButton = document.querySelector('#mute'), soundStatus = document.querySelector('#sound');
const audioNotice = document.querySelector('#audioNotice');
const consoleId = 'broadcast-' + window.DRS.createClientId();
const parameters = new URLSearchParams(location.search);
const bufferedMode = parameters.get('delay') !== '0';
if(bufferedMode)graphic.src='/overlay?program=1';
let pinnedCamera = parameters.get('camera') || '';
let socket = null, current = null, devices = [], retryTimer = null, reconnectTimer = null;
let retryId = '';
let closing = false;
let audioRequested = parameters.get('audio') !== '0';
video.muted = !audioRequested;
controls.hidden = parameters.get('clean') === '1';

function updateSound() {
  const hasAudio = current?.buffered ? current.hasAudio : current?.stream?.getAudioTracks().some(track => track.readyState !== 'ended');
  muteButton.textContent = video.muted ? 'Enable camera audio' : 'Mute camera audio';
  soundStatus.textContent = !hasAudio ? 'Camera microphone off / not received' :
    video.muted ? 'Camera audio received · muted here' : 'Camera audio on';
}
async function playProgram(connection = current) {
  if (!connection || current !== connection) return;
  if(connection.buffered){connection.buffered.setMuted(video.muted);if(!video.muted||!audioRequested)audioNotice.hidden=true;connection.buffered.resume();return;}
  const attempt = connection.playAttempt = (connection.playAttempt || 0) + 1;
  try {
    await video.play();
    if (current === connection && connection.playAttempt === attempt && (!video.muted || !audioRequested)) audioNotice.hidden = true;
  } catch (error) {
    if (current !== connection || connection.playAttempt !== attempt || error.name === 'AbortError') return;
    if (!video.muted) {
      // Keep the picture visible when a browser blocks autoplay with sound.
      video.muted = true;
      audioNotice.hidden = !audioRequested;
      updateSound();
      try { await video.play(); return; } catch { /* Video also needs a gesture. */ }
    }
    if (current !== connection) return;
    status.textContent = 'Video connected · press Retry video to start playback';
    showEmpty('Playback needs a click', 'Press Retry video. In OBS, open Browser Source → Interact.');
  }
}
updateSound();

function savedCamera() {
  try { return localStorage.getItem('broadcast_camera') || ''; } catch { return ''; }
}
function showEmpty(title, detail = '') {
  empty.querySelector('strong').textContent = title;
  empty.querySelector('span').textContent = detail;
  empty.hidden = false;
}
function closePeer() {
  const previous = current;
  current = null;
  if (previous) {
    clearTimeout(previous.timeout);
    clearTimeout(previous.disconnectedTimer);
    previous.peer?.close();
    previous.buffered?.destroy();
  }
  video.srcObject = null;
  video.hidden=false;
  empty.hidden = false;
  updateSound();
}
function send(connection, signal) {
  if (current !== connection || socket?.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify({type: 'webrtc_signal', device_id: connection.id,
    signal: {...signal, session_id: connection.sessionId}}));
}
function retryCamera(connection, reason) {
  if (current !== connection || closing) return;
  const id = connection.id;
  closePeer();
  status.textContent = reason + ' · retrying';
  showEmpty(reason, 'Check the camera page and local network. The video link will retry automatically.');
  clearTimeout(retryTimer);
  retryId = id;
  retryTimer = setTimeout(() => {
    retryTimer = null;
    retryId = '';
    if (select.value === id && devices.some(device => device.device_id === id)) useCamera(id);
  }, 1500);
}
async function useCamera(id) {
  clearTimeout(retryTimer);
  retryTimer = null;
  retryId = '';
  closePeer();
  const chosen = devices.find(device => device.device_id === id);
  if (!chosen || socket?.readyState !== WebSocket.OPEN || closing) return;
  try { localStorage.setItem('broadcast_camera', id); } catch { /* OBS can restrict storage. */ }
  if(bufferedMode){
    const connection={id,name:chosen.name,mediaRevision:chosen.settings?.media_revision||0,microphone:Boolean(chosen.settings?.microphone),hasAudio:false,showing:false};
    current=connection;video.hidden=true;
    showEmpty('Buffering five-second broadcast','Keep the camera connected and its replay recorder running. Video, audio and graphics play together.');
    status.textContent='BUFFERING · '+chosen.name;
    connection.buffered=new window.DRSBufferedBroadcast(id,document.querySelector('#bufferedStage'),{
      onStatus:message=>{if(current===connection)status.textContent=message;},
      onMute:()=>{if(current===connection){video.muted=true;audioNotice.hidden=false;updateSound();}},
      onBuffering:()=>{if(current===connection){connection.showing=false;showEmpty('Buffering camera video','Waiting for the next recorded clip. Keep the camera page visible.');}},
      onFrame:frame=>{if(current!==connection)return;connection.showing=true;connection.hasAudio=frame.audio;empty.hidden=true;
        status.textContent='DELAYED '+frame.delay.toFixed(1)+' s · '+connection.name;updateSound();
        graphic.contentWindow?.postMessage({type:'broadcast-time',at:frame.at/1000},location.origin);}
    });
    connection.buffered.setMuted(video.muted);return;
  }
  status.textContent = 'Connecting ' + chosen.name + '…';
  showEmpty('Connecting ' + chosen.name, 'Receiving the same live camera used by DRS.');
  let connection;
  try {
    const peer = new RTCPeerConnection({iceServers: []});
    connection = {id, name: chosen.name, peer, stream: new MediaStream(),
      mediaRevision: chosen.settings?.media_revision || 0, microphone: Boolean(chosen.settings?.microphone),
      sessionId: window.DRS.createClientId(), candidates: [], outgoing: [],
      offerSent: false, signals: Promise.resolve(), showing: false};
    current = connection;
    peer.addTransceiver('video', {direction: 'recvonly'});
    peer.addTransceiver('audio', {direction: 'recvonly'});
    peer.addEventListener('track', event => {
      if (current !== connection) return;
      const tracks = event.streams?.[0]?.getTracks() || [event.track];
      for (const track of tracks) {
        if (!connection.stream.getTracks().some(existing => existing.id === track.id)) connection.stream.addTrack(track);
      }
      if (video.srcObject !== connection.stream) video.srcObject = connection.stream;
      updateSound();
      playProgram(connection);
    });
    peer.addEventListener('icecandidate', event => {
      if (!event.candidate || current !== connection) return;
      const candidate = event.candidate.toJSON();
      // Send the offer first, so the camera can create its peer before ICE arrives.
      if (connection.offerSent) send(connection, {candidate});
      else connection.outgoing.push(candidate);
    });
    peer.addEventListener('connectionstatechange', () => {
      if (current !== connection) return;
      if (peer.connectionState === 'connected') {
        clearTimeout(connection.disconnectedTimer);
        if (!connection.showing) status.textContent = 'Video connected · waiting for picture';
      } else if (peer.connectionState === 'failed') {
        retryCamera(connection, 'Camera video link failed');
      } else if (peer.connectionState === 'disconnected') {
        status.textContent = 'Camera link interrupted · reconnecting';
        clearTimeout(connection.disconnectedTimer);
        connection.disconnectedTimer = setTimeout(() => {
          if (peer.connectionState === 'disconnected') retryCamera(connection, 'Camera link interrupted');
        }, 2500);
      }
    });
    connection.timeout = setTimeout(() => {
      if (!connection.showing) retryCamera(connection, 'No camera picture received');
    }, 15000);
    const offer = await peer.createOffer();
    if (current !== connection) return;
    await peer.setLocalDescription(offer);
    if (current !== connection) return;
    send(connection, {description: peer.localDescription});
    connection.offerSent = true;
    for (const candidate of connection.outgoing.splice(0)) send(connection, {candidate});
  } catch (error) {
    if (connection && current === connection) retryCamera(connection, 'Could not start camera video');
    else if (!connection) {
      status.textContent = 'WebRTC video is unavailable';
      showEmpty('This browser cannot receive camera video', 'Use an up-to-date browser or OBS Browser Source.');
    }
    console.warn('Broadcast camera connection failed', error);
  }
}
video.addEventListener('playing', () => {
  if (!current || video.srcObject !== current.stream || !current.stream.getVideoTracks().length) return;
  current.showing = true;
  clearTimeout(current.timeout);
  empty.hidden = true;
  status.textContent = 'LIVE · ' + current.name;
});
function acceptSignal(message) {
  const connection = current, signal = message.signal;
  if (!connection || connection.buffered || message.device_id !== connection.id || !signal) return Promise.resolve();
  // Older camera pages have no session ID; accept them until the page is refreshed.
  if (signal.session_id && signal.session_id !== connection.sessionId) return Promise.resolve();
  connection.signals = connection.signals.then(async () => {
    if (current !== connection) return;
    if (signal.description) {
      if (signal.description.type !== 'answer' || connection.peer.remoteDescription) return;
      await connection.peer.setRemoteDescription(signal.description);
      if (current !== connection) return;
      for (const candidate of connection.candidates.splice(0)) await connection.peer.addIceCandidate(candidate);
    } else if (signal.candidate) {
      if (connection.peer.remoteDescription) await connection.peer.addIceCandidate(signal.candidate);
      else connection.candidates.push(signal.candidate);
    }
  }).catch(error => {
    console.warn('Broadcast signaling failed', error);
    retryCamera(connection, 'Camera negotiation failed');
  });
  return connection.signals;
}
function updateDevices(next) {
  devices = Array.isArray(next) ? next : [];
  const wanted = pinnedCamera || select.value || savedCamera();
  const chosen = devices.find(device => device.device_id === wanted) ||
    (!pinnedCamera && (devices.find(device => device.role === 'UMPIRE_POV') || devices[0]));
  const options = devices.map(device => Object.assign(document.createElement('option'), {
    value: device.device_id, textContent: device.name + ' · ' + window.DRS.formatRole(device.role)}));
  if (!chosen) options.unshift(Object.assign(document.createElement('option'), {
    value: '', textContent: pinnedCamera ? 'Selected camera is offline' : 'Waiting for cameras…'}));
  select.replaceChildren(...options);
  select.disabled = !devices.length;
  select.value = chosen?.device_id || '';
  if (!chosen) {
    clearTimeout(retryTimer);
    retryTimer = null;
    retryId = '';
    closePeer();
    status.textContent = pinnedCamera ? 'Selected camera is offline' : 'No connected cameras';
    showEmpty(status.textContent, 'Keep Studio running and connect a device through its camera page.');
  } else if ((current?.id !== chosen.device_id || (!bufferedMode && (current.mediaRevision !== (chosen.settings?.media_revision || 0) ||
              current.microphone !== Boolean(chosen.settings?.microphone)))) && (!retryTimer || retryId !== chosen.device_id)) {
    useCamera(chosen.device_id);
  } else if (current) {
    current.name = chosen.name;
    if (current.showing && !bufferedMode) status.textContent = 'LIVE · ' + chosen.name;
  }
}
function connect() {
  clearTimeout(reconnectTimer);
  if (closing) return;
  const nextSocket = new WebSocket(window.DRS.websocketUrl('/ws/umpire') + '?console_id=' + encodeURIComponent(consoleId));
  socket = nextSocket;
  nextSocket.addEventListener('message', event => {
    if (socket !== nextSocket) return;
    try {
      const message = JSON.parse(event.data);
      if (message.type === 'devices') updateDevices(message.devices);
      if (message.type === 'webrtc_signal') acceptSignal(message);
      if (message.type === 'webrtc_error' && message.device_id === current?.id) retryCamera(current, message.message || 'Camera offline');
    } catch (error) { console.warn('Invalid broadcast server message', error); }
  });
  nextSocket.addEventListener('close', () => {
    if (socket !== nextSocket) return;
    socket = null;
    clearTimeout(retryTimer);
    retryTimer = null;
    retryId = '';
    closePeer();
    select.disabled = true;
    status.textContent = 'Server link lost · retrying';
    showEmpty('Studio connection lost', 'Keep the Studio PC running. Reconnecting automatically…');
    if (!closing) reconnectTimer = setTimeout(connect, 1500);
  });
  nextSocket.addEventListener('error', () => {
    if (socket === nextSocket) status.textContent = 'Cannot reach Studio · check HTTPS and the local network';
  });
}
select.addEventListener('change', () => { pinnedCamera = ''; useCamera(select.value); });
controls.addEventListener('submit', event => event.preventDefault());
document.querySelector('#retry').addEventListener('click', () => {
  if (socket?.readyState === WebSocket.OPEN) useCamera(select.value);
  else { const previous = socket; socket = null; previous?.close(); connect(); }
});
document.querySelector('#showGraphic').addEventListener('change', event => { graphic.hidden = !event.target.checked; });
muteButton.addEventListener('click', () => {
  audioRequested = video.muted;
  video.muted = !audioRequested;
  audioNotice.hidden = true;
  updateSound();
  playProgram();
});
audioNotice.addEventListener('click', () => {
  audioRequested = true;
  video.muted = false;
  updateSound();
  playProgram();
});
document.querySelector('#copyOutput').addEventListener('click', async event => {
  if (!select.value) { status.textContent = 'Connect and select a camera first'; return; }
  const url = new URL(location.href);
  url.searchParams.set('camera', select.value);
  url.searchParams.set('clean', '1');
  url.searchParams.set('audio', audioRequested ? '1' : '0');
  try { await navigator.clipboard.writeText(url.href); event.target.textContent = 'OBS link copied'; }
  catch { status.textContent = 'OBS URL: ' + url.href; }
});
window.addEventListener('beforeunload', () => {
  closing = true; clearTimeout(reconnectTimer); clearTimeout(retryTimer); closePeer(); socket?.close();
});
connect();
}
