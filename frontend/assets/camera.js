"use strict";

const { createClientId, showToast, websocketUrl } = window.DRS;

const form = document.querySelector("#cameraForm");
const preview = document.querySelector("#preview");
const previewEmpty = document.querySelector("#previewEmpty");
const pill = document.querySelector("#connectionPill");
const connectionCard = document.querySelector("#connectionCard");
const peerConnections = new Map();
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
  if (previewStream?.active) return previewStream;
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
  for (const peer of peerConnections.values()) peer.close();
  peerConnections.clear();
}

async function handleSignal(message) {
  const { console_id: consoleId, signal } = message;
  if (!consoleId || !signal) return;
  if (signal.flush) { rollingRecorder?.flush(); return; }
  let peer = peerConnections.get(consoleId);

  if (signal.description?.type === "offer") {
    if (peer) peer.close();
    peer = new RTCPeerConnection({ iceServers: [] });
    peer.pendingCandidates = [];
    peerConnections.set(consoleId, peer);
    const stream = await ensureMedia();
    for (const track of stream.getTracks()) peer.addTrack(track, stream);
    peer.addEventListener("icecandidate", event => {
      if (event.candidate && socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
          type: "webrtc_signal",
          console_id: consoleId,
          signal: { candidate: event.candidate.toJSON() },
        }));
      }
    });
    peer.addEventListener("connectionstatechange", () => {
      document.querySelector("#streamStatusValue").textContent = peer.connectionState.toUpperCase();
      if (["failed", "closed"].includes(peer.connectionState)) {
        peerConnections.delete(consoleId);
      }
    });
    await peer.setRemoteDescription(signal.description);
    for (const candidate of peer.pendingCandidates.splice(0)) {
      await peer.addIceCandidate(candidate);
    }
    const answer = await peer.createAnswer();
    await peer.setLocalDescription(answer);
    socket.send(JSON.stringify({
      type: "webrtc_signal",
      console_id: consoleId,
      signal: { description: peer.localDescription },
    }));
    return;
  }

  if (signal.candidate && peer) {
    try {
      if (peer.remoteDescription) await peer.addIceCandidate(signal.candidate);
      else peer.pendingCandidates.push(signal.candidate);
    }
    catch (error) { console.warn("Rejected ICE candidate", error); }
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
  socket = new WebSocket(websocketUrl("/ws/camera"));
  document.querySelector("#cameraFacing").disabled=true;

  socket.addEventListener("open", () => {
    const videoTrack = previewStream.getVideoTracks()[0];
    const videoSettings = videoTrack?.getSettings?.() || {};
    socket.send(JSON.stringify({
      type: "register", device_id: deviceId, name, role,
      settings: {
        resolution: `${videoSettings.width || "?"}x${videoSettings.height || "?"}`,
        fps: videoSettings.frameRate || Number(document.querySelector("#fps").value),
        microphone: previewStream.getAudioTracks().length > 0,
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
    const message = JSON.parse(event.data);
    if (message.type === "registered") {
      setStatus(true, "Camera live");
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
      catch (error) { showToast(`Video link failed: ${error.message}`); }
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
    clearInterval(heartbeatTimer);
    rollingRecorder?.stop();
    stopAudio?.();stopAudio=null;
    closePeers();
    setStatus(false, "Not connected");
    document.querySelector("#streamStatusValue").textContent = "OFFLINE";
    if (!intentionalDisconnect) showToast(event.reason || "Connection lost — reconnect when ready");
  });
  socket.addEventListener("error", () => showToast("Could not reach the DRS server"));
}

function sendHeartbeat() {
  if (socket?.readyState !== WebSocket.OPEN) return;
  const sequence = ++heartbeatSequence;
  heartbeatSentAt.set(sequence, performance.now());
  socket.send(JSON.stringify({ type: "heartbeat", sequence, client_time_ms: Date.now() }));
}

form.addEventListener("submit", event => { event.preventDefault(); connect(); });
document.querySelector("#connectButton").addEventListener("click", connect);
document.querySelector("#previewButton").addEventListener("click", testCamera);
document.querySelector("#disconnectButton").addEventListener("click", () => {
  intentionalDisconnect = true;
  socket?.close(1000, "Device disconnected");
});
window.addEventListener("beforeunload", () => {
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

let stopAudio=null;
document.getElementById('enableAudio').onclick=async()=>{
 const status=document.getElementById('audioStatus'),button=document.getElementById('enableAudio');button.disabled=true;
 try{
  stopAudio?.();stopAudio=null;
  stopAudio=await window.DRSAudioStart(previewStream,deviceId,()=>rollingRecorder?.clock,text=>status.textContent=text,mic=>{
   if(previewStream){
    rollingRecorder?.stop();
    previewStream.getAudioTracks().filter(t=>t.readyState!=='live').forEach(t=>previewStream.removeTrack(t));
    mic.getAudioTracks().forEach(t=>previewStream.addTrack(t));
    if(socket?.readyState===WebSocket.OPEN)startReplayRecording();
   }
  });
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
