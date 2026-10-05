"use strict";

const { createClientId, showToast, websocketUrl } = window.DRS;

const form = document.querySelector("#cameraForm");
const preview = document.querySelector("#preview");
const previewEmpty = document.querySelector("#previewEmpty");
const pill = document.querySelector("#connectionPill");
const connectionCard = document.querySelector("#connectionCard");
const peerConnections = new Map();
const viewerErrors = new Map();
let socket = null;
let heartbeatTimer = null;
let heartbeatSequence = 0;
let heartbeatSentAt = new Map();
let previewStream = null;
let optics=null;
let mediaBusy=false;
let intentionalDisconnect = false;
let rollingRecorder = null;
let recordingGeneration = 0;
let microphoneBusy = false;
const watchedMicrophones = new WeakSet();
let battery = null;
const stopBattery = window.DRSBattery?.watch(value => {
  battery = value;
  sendHeartbeat();
});

function liveMicrophones() {
  return previewStream?.getAudioTracks().filter(track => track.readyState === 'live' && track.enabled !== false) || [];
}
function publishMicrophone() {
  const enabled = liveMicrophones().length > 0;
  document.querySelector('#microphone').value = String(enabled);
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({type: 'media_changed', microphone: enabled}));
    startReplayRecording();
  }
}
function watchMicrophones(stream) {
  for (const track of stream.getAudioTracks()) {
    if (watchedMicrophones.has(track)) continue;
    watchedMicrophones.add(track);
    track.addEventListener('ended', () => {
      if (previewStream !== stream) return;
      stream.removeTrack(track);
      publishMicrophone();
      document.querySelector('#audioStatus').textContent = 'Microphone ended — enable it again to restore camera sound.';
    });
  }
}
function adoptMicrophone(microphone) {
  if (!previewStream?.active) return false;
  for (const track of previewStream.getAudioTracks()) {
    if (track.readyState !== 'live') previewStream.removeTrack(track);
  }
  rollingRecorder?.stop();
  for (const track of microphone.getAudioTracks()) previewStream.addTrack(track);
  watchMicrophones(previewStream);
  publishMicrophone();
  return true;
}
async function syncMicrophone() {
  if (!previewStream?.active) return;
  const enabled = document.querySelector('#microphone').value === 'true';
  if (enabled === (liveMicrophones().length > 0)) return;
  if (microphoneBusy) throw Error('Microphone is opening — please wait');
  microphoneBusy = true;
  document.querySelector('#microphone').disabled = true;
  const stream = previewStream;
  try {
    if (enabled) {
      const microphone = await navigator.mediaDevices.getUserMedia({video: false,
        audio: {echoCancellation: false, noiseSuppression: false, autoGainControl: false}});
      if (previewStream !== stream || !adoptMicrophone(microphone)) microphone.getTracks().forEach(track => track.stop());
    } else {
      stopAudio?.(); stopAudio = null;
      rollingRecorder?.stop();
      for (const track of stream.getAudioTracks()) { track.stop(); stream.removeTrack(track); }
      publishMicrophone();
      document.querySelector('#audioStatus').textContent = 'Camera microphone disabled.';
    }
  } finally {
    microphoneBusy = false;
    document.querySelector('#microphone').disabled = false;
    document.querySelector('#microphone').value = String(liveMicrophones().length > 0);
  }
}

const deviceId = localStorage.getItem("drs_device_id") || createClientId();
localStorage.setItem("drs_device_id", deviceId);
document.querySelector("#cameraName").value = localStorage.getItem("drs_camera_name") || `Camera ${deviceId.slice(0, 4).toUpperCase()}`;
document.querySelector("#cameraRole").value = localStorage.getItem("drs_camera_role") || "UMPIRE_POV";
document.querySelector("#secureWarning").hidden = window.isSecureContext;

function setStatus(online, text) {
  pill.className = `status-pill ${online ? "online" : "offline"}`;
  pill.querySelector("span:last-child").textContent = text;
  connectionCard.classList.toggle("active", online);
  document.body.classList.toggle("capture-connected",online);
  if(online)document.querySelector(".capture-settings").open=false;
  document.querySelector("#connectButton").disabled = online;
  document.querySelector("#cameraFacing").disabled=online||mediaBusy;
  document.querySelector("#cameraDevice").disabled=online||mediaBusy;
}

function selectedConstraints() {
  const [width, height] = document.querySelector("#resolution").value.split("x").map(Number);
  return {
    video: {
      width: { ideal: width },
      height: { ideal: height },
      frameRate: { ideal: Number(document.querySelector("#fps").value) },
      ...(document.querySelector("#cameraDevice").value
        ? { deviceId: { exact: document.querySelector("#cameraDevice").value } }
        : { facingMode: { ideal: document.querySelector("#cameraFacing").value } }),
    },
    audio: document.querySelector("#microphone").value === "true",
  };
}

async function ensureMedia() {
  if (previewStream?.active) { await syncMicrophone(); return previewStream; }
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("Camera access requires trusted HTTPS on this phone");
  }
  if(mediaBusy)throw Error('Camera is opening — please wait');
  mediaBusy=true;
  document.querySelector('#cameraFacing').disabled=true;
  try {
    const raw=await navigator.mediaDevices.getUserMedia(selectedConstraints());
    await refreshCameraDevices(raw.getVideoTracks()[0]?.getSettings?.().deviceId);
    optics=await window.DRSOptics.create(raw,document.querySelector('#cameraZoom'),document.querySelector('#zoomStatus'));
    previewStream=optics.stream;
    watchMicrophones(previewStream);
  } catch(e){throw Error(e.name==='OverconstrainedError'?'Selected camera unavailable. Choose the other camera.':e.message);}
  finally{mediaBusy=false;const locked=socket?.readyState===WebSocket.OPEN||socket?.readyState===WebSocket.CONNECTING;document.querySelector('#cameraFacing').disabled=locked;document.querySelector('#cameraDevice').disabled=locked;}
  preview.srcObject = previewStream;
  preview.hidden = false;
  previewEmpty.hidden = true;
  return previewStream;
}

async function testCamera() {
  if (mediaBusy || socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return showToast("Disconnect before changing the camera");
  try {
    if (previewStream) {
      stopAudio?.();stopAudio=null;
      optics?.close();optics=null;
      previewStream.getTracks().forEach(track => track.stop());
      previewStream = null;
    }
    await ensureMedia();
    showToast("Camera ready");
  } catch (error) {
    showToast(`Camera test failed: ${error.message}`);
  }
}

function closePeers() {
  const peers = [...peerConnections.values()];
  peerConnections.clear();
  viewerErrors.clear();
  for (const peer of peers) peer.close();
  refreshVideoStatus();
}

function refreshVideoStatus() {
  const peers = [...peerConnections.values()];
  const connected = peers.filter(peer => peer.connectionState === 'connected').length;
  const pending = peers.filter(peer => ['new','connecting','disconnected'].includes(peer.connectionState)).length;
  const value = document.querySelector('#streamStatusValue'), note = document.querySelector('#videoLinkNote');
  if (socket?.readyState !== WebSocket.OPEN) { value.textContent = 'OFFLINE'; note.textContent = 'Connect this camera to Studio.'; return; }
  value.textContent = connected ? 'LIVE · '+connected : pending ? 'CONNECTING' : viewerErrors.size ? 'VIEWER RETRY' : 'READY';
  note.textContent = connected ? connected+' live viewer link'+(connected===1?'':'s')+' working.' : 'Camera capture and replay are independent of live viewer links.';
  if (pending) note.textContent += ' '+pending+' viewer link'+(pending===1?' is':'s are')+' connecting/reconnecting.';
  if (viewerErrors.size) note.textContent += ' A viewer link needs retrying; other viewers and replay are not stopped. '+[...viewerErrors.values()].at(-1);
}

async function handleSignal(message) {
  const { console_id: consoleId, signal } = message;
  if (!consoleId || !signal) return;
  if (signal.flush) { rollingRecorder?.flush(); return; }
  let peer = peerConnections.get(consoleId);

  if (signal.description?.type === "offer") {
    const previous = peer;
    peer = new RTCPeerConnection({ iceServers: [] });
    peer.pendingCandidates = [];
    peer.signalSession = typeof signal.session_id === 'string' ? signal.session_id : '';
    peerConnections.set(consoleId, peer);
    // Replacing one viewer must not let the old peer overwrite the status or
    // report a negotiation cancelled by the replacement as a camera failure.
    previous?.close();
    viewerErrors.delete(consoleId);
    refreshVideoStatus();
    const signalSocket = socket;
    const currentPeer = () => peerConnections.get(consoleId) === peer && socket === signalSocket && socket?.readyState === WebSocket.OPEN;
    try {
    const stream = await ensureMedia();
    if (!currentPeer()) return;
    for (const track of stream.getTracks()) peer.addTrack(track, stream);
    peer.addEventListener("icecandidate", event => {
      if (event.candidate && peerConnections.get(consoleId) === peer && socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
          type: "webrtc_signal",
          console_id: consoleId,
          signal: { candidate: event.candidate.toJSON(), ...(peer.signalSession ? {session_id: peer.signalSession} : {}) },
        }));
      }
    });
    peer.addEventListener("connectionstatechange", () => {
      if (peerConnections.get(consoleId) !== peer) return;
      if (peer.connectionState === 'connected') viewerErrors.delete(consoleId);
      if (["failed", "closed"].includes(peer.connectionState)) {
        peerConnections.delete(consoleId);
        if (peer.connectionState === 'failed') { viewerErrors.set(consoleId,'Live viewer connection failed.'); peer.close(); }
      }
      refreshVideoStatus();
    });
    await peer.setRemoteDescription(signal.description);
    if (!currentPeer()) return;
    for (const candidate of peer.pendingCandidates.splice(0)) {
      await peer.addIceCandidate(candidate);
      if (!currentPeer()) return;
    }
    const answer = await peer.createAnswer();
    if (!currentPeer()) return;
    await peer.setLocalDescription(answer);
    if (!currentPeer()) return;
    socket.send(JSON.stringify({
      type: "webrtc_signal",
      console_id: consoleId,
      signal: { description: peer.localDescription, ...(peer.signalSession ? {session_id: peer.signalSession} : {}) },
    }));
    } catch (error) {
      if (!currentPeer()) return; // Cancelled/replaced/disconnected negotiation.
      peerConnections.delete(consoleId);peer.close();
      viewerErrors.set(consoleId,'Negotiation: '+error.message);
      refreshVideoStatus();
      console.warn('Current live viewer negotiation failed',error);
    }
    return;
  }

  if (signal.candidate && peer) {
    if (signal.session_id && signal.session_id !== peer.signalSession) return;
    try {
      if (peer.remoteDescription) await peer.addIceCandidate(signal.candidate);
      else peer.pendingCandidates.push(signal.candidate);
    }
    catch (error) { if (peerConnections.get(consoleId) === peer) console.warn("Rejected ICE candidate", error); }
  }
}

async function connect() {
  if(mediaBusy||socket?.readyState===WebSocket.OPEN||socket?.readyState===WebSocket.CONNECTING)return;
  intentionalDisconnect = false;
  const name = document.querySelector("#cameraName").value.trim();
  const role = document.querySelector("#cameraRole").value;
  if (!name) return;
  try {
    await ensureMedia();
  } catch (error) {
    showToast(error.message);
    return;
  }
  localStorage.setItem("drs_camera_name", name);
  localStorage.setItem("drs_camera_role", role);
  setStatus(false, "Connecting…");
  const nextSocket = new WebSocket(websocketUrl("/ws/camera"));
  socket = nextSocket;
  document.querySelector("#cameraFacing").disabled=true;

  socket.addEventListener("open", () => {
    if (socket !== nextSocket) return;
    const videoTrack = previewStream.getVideoTracks()[0];
    const videoSettings = videoTrack?.getSettings?.() || {};
    socket.send(JSON.stringify({
      type: "register", device_id: deviceId, name, role, battery,
      settings: {
        resolution: `${videoSettings.width || "?"}x${videoSettings.height || "?"}`,
        fps: videoSettings.frameRate || Number(document.querySelector("#fps").value),
        microphone: liveMicrophones().length > 0,
      },
      capabilities: {
        secure_context: window.isSecureContext,
        media_devices: Boolean(navigator.mediaDevices),
        webrtc: Boolean(window.RTCPeerConnection),
        user_agent: navigator.userAgent.slice(0, 180),
      },
    }));
  });

  socket.addEventListener("message", async event => {
    if (socket !== nextSocket) return;
    const message = JSON.parse(event.data);
    if (message.type === "registered") {
      setStatus(true, "Camera live");
      refreshVideoStatus();
      startReplayRecording();
      document.querySelector("#connectedName").textContent = name;
      const interval = (message.heartbeat_interval_seconds || 4) * 1000;
      clearInterval(heartbeatTimer);
      sendHeartbeat();
      heartbeatTimer = setInterval(sendHeartbeat, interval);
    }
    if (message.type === "heartbeat_ack") {
      const started = heartbeatSentAt.get(message.sequence);
      if (started) {
        document.querySelector("#latencyValue").textContent = `${Math.round(performance.now() - started)} ms`;
        heartbeatSentAt.delete(message.sequence);
      }
      document.querySelector("#heartbeatValue").textContent = message.sequence;
    }
    if (message.type === "webrtc_signal") {
      try { await handleSignal(message); }
      catch (error) {
        if (socket !== nextSocket) return;
        viewerErrors.set(message.console_id || 'viewer', 'Negotiation: '+error.message);
        refreshVideoStatus();
        console.warn('Live viewer signalling failed',error);
      }
    }
    if (message.type === "configuration") {
      document.querySelector("#cameraName").value = message.name;
      document.querySelector("#cameraRole").value = message.role;
      localStorage.setItem("drs_camera_name", message.name);
      localStorage.setItem("drs_camera_role", message.role);
      document.querySelector("#connectedName").textContent = message.name;
      showToast("Camera configuration updated by umpire");
    }
  });

  socket.addEventListener("close", event => {
    if (socket !== nextSocket) return;
    clearInterval(heartbeatTimer);
    rollingRecorder?.stop();
    stopAudio?.();stopAudio=null;
    closePeers();
    setStatus(false, "Not connected");
    document.querySelector("#streamStatusValue").textContent = "OFFLINE";
    if (!intentionalDisconnect) showToast(event.reason || "Connection lost — reconnect when ready");
  });
  socket.addEventListener("error", () => { if (socket === nextSocket) showToast("Could not reach the DRS server"); });
}

function sendHeartbeat() {
  if (socket?.readyState !== WebSocket.OPEN) return;
  const sequence = ++heartbeatSequence;
  heartbeatSentAt.set(sequence, performance.now());
  socket.send(JSON.stringify({ type: "heartbeat", sequence, client_time_ms: Date.now(), battery }));
}

form.addEventListener("submit", event => { event.preventDefault(); connect(); });
document.querySelector("#connectButton").addEventListener("click", connect);
document.querySelector("#previewButton").addEventListener("click", testCamera);
document.querySelector("#disconnectButton").addEventListener("click", () => {
  intentionalDisconnect = true;
  socket?.close(1000, "Device disconnected");
});
window.addEventListener("beforeunload", () => {
  stopBattery?.();
  closePeers();
  optics?.close();
  previewStream?.getTracks().forEach(track => track.stop());
});
window.__drsCameraReady = true;

function startReplayRecording() {
  const panel = document.querySelector('#recordingStatus');
  if (!previewStream || socket?.readyState !== WebSocket.OPEN) {
    panel.textContent = 'Connect the camera before starting replay recording.'; return;
  }
  const generation = ++recordingGeneration;
  rollingRecorder?.stop();
  const report = text => {
    if (recordingGeneration !== generation) return;
    panel.textContent = text;
    fetch('/api/recorder-status/' + encodeURIComponent(deviceId), {
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})
    }).catch(()=>{});
  };
  try {
    panel.textContent = 'Starting replay recorder…';
    rollingRecorder = new window.DRSRecorder(deviceId, previewStream, report);
    rollingRecorder.start().catch(e => report('Replay unavailable: ' + e.message + '. Press Start/retry replay.'));
  } catch(e) { panel.textContent = 'Replay startup failed: ' + e.message; }
}
document.querySelector('#retryRecording').addEventListener('click',startReplayRecording);
document.querySelector('#microphone').addEventListener('change', () => {
  syncMicrophone().catch(error => {
    document.querySelector('#audioStatus').textContent = 'Microphone: ' + error.message;
    showToast('Microphone: ' + error.message);
  });
});

let stopAudio=null;
document.getElementById('enableAudio').onclick=async()=>{
 const status=document.getElementById('audioStatus'),button=document.getElementById('enableAudio');button.disabled=true;
 try{
  stopAudio?.();stopAudio=null;
  stopAudio=await window.DRSAudioStart(previewStream,deviceId,()=>rollingRecorder?.clock,text=>status.textContent=text,adoptMicrophone);
 }catch(e){status.textContent='Microphone: '+e.message;}finally{button.disabled=false;}
};
document.getElementById('stopAudio').onclick=()=>{stopAudio?.();stopAudio=null;document.getElementById('audioStatus').textContent='Analysis stopped';};
window.addEventListener('beforeunload',()=>stopAudio?.());

const facing=document.querySelector('#cameraFacing');
facing.value=localStorage.getItem('drs_facing')==='user'?'user':'environment';
facing.addEventListener('change',()=>{localStorage.setItem('drs_facing',facing.value);testCamera();});
const cameraDevice=document.querySelector('#cameraDevice');
async function refreshCameraDevices(activeId=''){
 if(!navigator.mediaDevices?.enumerateDevices)return;
 const devices=(await navigator.mediaDevices.enumerateDevices()).filter(item=>item.kind==='videoinput');
 const saved=activeId||localStorage.getItem('drs_camera_device')||'';
 cameraDevice.innerHTML='<option value="">Automatic (recommended)</option>';
 devices.forEach((item,index)=>{const option=document.createElement('option');option.value=item.deviceId;option.textContent=item.label||`Camera ${index+1}`;cameraDevice.append(option);});
 if([...cameraDevice.options].some(option=>option.value===saved))cameraDevice.value=saved;
 document.querySelector('#cameraDeviceNote').textContent=devices.length?`${devices.length} camera${devices.length===1?'':'s'} available. Names differ between Apple, Android and Raspberry Pi browsers.`:'Camera names appear after permission is granted.';
}
cameraDevice.addEventListener('change',()=>{localStorage.setItem('drs_camera_device',cameraDevice.value);testCamera();});
navigator.mediaDevices?.addEventListener?.('devicechange',()=>refreshCameraDevices());
refreshCameraDevices();
document.querySelector('#resetZoom').onclick=()=>optics?.set(1);
let pinch=null;
const surface=document.querySelector('.preview-panel');
function distance(t){return Math.hypot(t[0].clientX-t[1].clientX,t[0].clientY-t[1].clientY);}
surface.addEventListener('touchstart',e=>{if(e.touches.length===2&&optics){e.preventDefault();pinch={distance:distance(e.touches),zoom:optics.value};}},{passive:false});
surface.addEventListener('touchmove',e=>{if(e.touches.length===2&&pinch&&pinch.distance>0){e.preventDefault();optics?.set(pinch.zoom*distance(e.touches)/pinch.distance);}},{passive:false});
for(const name of ['touchend','touchcancel'])surface.addEventListener(name,()=>{pinch=null;});
