"use strict";

const { createClientId, escapeHtml, formatRole, showToast, websocketUrl } = window.DRS;

const grid = document.querySelector("#cameraGrid");
const deviceList = document.querySelector("#deviceList");
const modal = document.querySelector("#editModal");
const consoleId = createClientId();
localStorage.setItem("drs_console_id", consoleId);

const peers = new Map();
let devices = [];
let socket;
let reconnectTimer;
let primaryCameraUrl = "";

function closePeer(deviceId) {
  const peer = peers.get(deviceId);
  peers.delete(deviceId);
  if (peer) peer.close();
}

function setStreamState(deviceId, label, connected = false) {
  const badge = [...document.querySelectorAll("[data-stream-state]")]
    .find(item => item.dataset.streamState === deviceId);
  if (!badge) return;
  badge.textContent = label;
  badge.classList.toggle("connected", connected);
}

async function acceptSignal(deviceId, signal) {
  const peer = peers.get(deviceId);
  if (!peer || (signal.session_id && signal.session_id !== peer.signalSession)) return;
  peer.signals = peer.signals.then(async () => {
    if (peers.get(deviceId) !== peer) return;
    if (signal.description) {
      if (signal.description.type !== 'answer' || peer.remoteDescription) return;
      await peer.setRemoteDescription(signal.description);
      if (peers.get(deviceId) !== peer) return;
      for (const candidate of peer.pendingCandidates.splice(0)) await peer.addIceCandidate(candidate);
    } else if (signal.candidate) {
      if (peer.remoteDescription) await peer.addIceCandidate(signal.candidate);
      else peer.pendingCandidates.push(signal.candidate);
    }
  }).catch(error => {
    if (peers.get(deviceId) === peer) closePeer(deviceId);
    throw error;
  });
  return peer.signals;
}

async function startPeer(device) {
  if (peers.has(device.device_id) || socket?.readyState !== WebSocket.OPEN) return;
  const peer = new RTCPeerConnection({ iceServers: [] });
  peer.pendingCandidates = [];
  peer.outgoingCandidates = [];
  peer.offerSent = false;
  peer.signals = Promise.resolve();
  peer.signalSession = createClientId();
  peer.mediaRevision = device.settings?.media_revision || 0;
  peer.microphone = Boolean(device.settings?.microphone);
  peer.stream = new MediaStream();
  peers.set(device.device_id, peer);
  setStreamState(device.device_id, "NEGOTIATING");

  peer.addTransceiver("video", { direction: "recvonly" });
  peer.addTransceiver("audio", { direction: "recvonly" });
  const send = signal => {
    if (peers.get(device.device_id) !== peer || socket?.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({type: 'webrtc_signal', device_id: device.device_id,
      signal: {...signal, session_id: peer.signalSession}}));
  };
  peer.addEventListener("track", event => {
    if (peers.get(device.device_id) !== peer) return;
    const video = [...document.querySelectorAll("[data-video-id]")]
      .find(item => item.dataset.videoId === device.device_id);
    if (!video) return;
    for (const track of event.streams?.[0]?.getTracks() || [event.track]) {
      if (!peer.stream.getTracks().some(existing => existing.id === track.id)) peer.stream.addTrack(track);
    }
    if (video.srcObject !== peer.stream) video.srcObject = peer.stream;
    video.hidden = false;
    video.play().catch(() => undefined);
  });
  peer.addEventListener("icecandidate", event => {
    if (!event.candidate || peers.get(device.device_id) !== peer) return;
    if (peer.offerSent) send({candidate: event.candidate.toJSON()});
    else peer.outgoingCandidates.push(event.candidate.toJSON());
  });
  peer.addEventListener("connectionstatechange", () => {
    if (peers.get(device.device_id) !== peer) return;
    const state = peer.connectionState;
    setStreamState(device.device_id, state === "connected" ? "VIDEO LIVE" : state.toUpperCase(), state === "connected");
    if (["failed", "closed"].includes(state)) closePeer(device.device_id);
  });

  const offer = await peer.createOffer();
  if (peers.get(device.device_id) !== peer) return;
  await peer.setLocalDescription(offer);
  if (peers.get(device.device_id) !== peer) return;
  send({description: peer.localDescription});
  peer.offerSent = true;
  for (const candidate of peer.outgoingCandidates.splice(0)) send({candidate});
}

function cameraTile(device) {
  const article = document.createElement("article");
  article.className = "camera-tile";
  article.dataset.deviceTile = device.device_id;
  article.innerHTML = `
    <video data-video-id="${escapeHtml(device.device_id)}" autoplay playsinline muted hidden></video>
    <div class="camera-placeholder"><div class="camera-icon" aria-hidden="true"></div><div>CONNECTING VIDEO</div></div>
    <div class="stream-state" data-stream-state="${escapeHtml(device.device_id)}">WAITING</div>
    <div class="camera-meta">
      <div><h3 class="camera-name"></h3><div class="camera-role"></div></div>
      <div class="live-tag">LIVE</div>
    </div>`;
  window.DRSLiveInspect?.(article);
  return article;
}

function render() {
  document.querySelector("#cameraCount").textContent = devices.length;
  document.querySelector("#onlineStat").textContent = devices.length;
  document.querySelector("#roleStat").textContent = new Set(devices.map(device => device.role)).size;
  const activeIds = new Set(devices.map(device => device.device_id));

  for (const existing of [...grid.querySelectorAll("[data-device-tile]")]) {
    if (!activeIds.has(existing.dataset.deviceTile)) {
      closePeer(existing.dataset.deviceTile);
      existing.remove();
    }
  }

  if (!devices.length) {
    if (!grid.querySelector(".empty-grid")) {
      grid.innerHTML = `<div class="panel empty-grid"><div><div class="camera-icon" aria-hidden="true"></div><h2>Waiting for cameras</h2><p>Open a camera link on a phone connected to this Wi-Fi.</p></div></div>`;
    }
    deviceList.innerHTML = `<p>No connected devices.</p>`;
    return;
  }

  grid.querySelector(".empty-grid")?.remove();
  for (const device of devices) {
    let tile = [...grid.querySelectorAll("[data-device-tile]")].find(item => item.dataset.deviceTile === device.device_id);
    if (!tile) {
      tile = cameraTile(device);
      grid.append(tile);
    }
    tile.querySelector(".camera-name").textContent = device.name;
    tile.querySelector(".camera-role").textContent = `${formatRole(device.role)} · ${device.settings?.resolution || "AUTO"} · ${device.settings?.fps || "—"} FPS`;
    const peer = peers.get(device.device_id);
    if (peer && (peer.mediaRevision !== (device.settings?.media_revision || 0) ||
                 peer.microphone !== Boolean(device.settings?.microphone))) closePeer(device.device_id);
    startPeer(device).catch(error => {
      setStreamState(device.device_id, "VIDEO ERROR");
      console.error("WebRTC setup failed", error);
    });
  }

  deviceList.innerHTML = devices.map(device => `
    <div class="device-row">
      <span class="connection-light"></span>
      <div><strong>${escapeHtml(device.name)}</strong><small>${escapeHtml(device.remote_address)} · ${escapeHtml(formatRole(device.role))}</small></div>
      <div class="device-actions">
        <button class="icon-btn edit-device" data-id="${escapeHtml(device.device_id)}" title="Edit camera" aria-label="Edit ${escapeHtml(device.name)}">✎</button>
        <button class="icon-btn disconnect-device" data-id="${escapeHtml(device.device_id)}" title="Disconnect camera" aria-label="Disconnect ${escapeHtml(device.name)}">×</button>
      </div>
    </div>`).join("");
}

function connectUmpire() {
  clearTimeout(reconnectTimer);
  socket = new WebSocket(`${websocketUrl("/ws/umpire")}?console_id=${encodeURIComponent(consoleId)}`);
  socket.addEventListener("open", () => {
    const pill = document.querySelector("#serverPill");
    pill.className = "status-pill online";
    pill.querySelector("span:last-child").textContent = "Server online";
  });
  socket.addEventListener("message", async event => {
    const message = JSON.parse(event.data);
    if (message.type === "devices") {
      devices = message.devices;
      render();
    }
    if (message.type === "webrtc_signal") {
      try { await acceptSignal(message.device_id, message.signal); }
      catch (error) {
        setStreamState(message.device_id, "VIDEO ERROR");
        console.error("WebRTC signal failed", error);
      }
    }
    if (message.type === "webrtc_error") setStreamState(message.device_id, "CAMERA OFFLINE");
  });
  socket.addEventListener("close", () => {
    for (const deviceId of [...peers.keys()]) closePeer(deviceId);
    const pill = document.querySelector("#serverPill");
    pill.className = "status-pill offline";
    pill.querySelector("span:last-child").textContent = "Reconnecting";
    reconnectTimer = setTimeout(connectUmpire, 1500);
  });
}

async function loadServerInfo() {
  try {
    const response = await fetch("/api/server-info");
    if (!response.ok) throw new Error("Server information unavailable");
    const info = await response.json();
    const urls = info.camera_urls?.length ? info.camera_urls : [info.camera_url];
    primaryCameraUrl = urls[0];
    document.querySelector("#sleepStatus").textContent = info.sleep_prevention || "Sleep status unavailable";
    document.querySelector("#cameraUrls").innerHTML = urls.map((url, index) =>
      `<a class="server-address" href="${escapeHtml(url)}" target="_blank" rel="noopener">${index ? "Alternative: " : "Camera: "}${escapeHtml(url)}</a>`
    ).join("");
    document.querySelector("#certificateLink").hidden = !info.certificate_url;
  } catch {
    document.querySelector("#cameraUrls").innerHTML = `<span class="server-address">Could not determine LAN address</span>`;
    showToast("Could not load the local server address");
  }
}

deviceList.addEventListener("click", async event => {
  const edit = event.target.closest(".edit-device");
  const disconnect = event.target.closest(".disconnect-device");
  if (edit) {
    const device = devices.find(item => item.device_id === edit.dataset.id);
    if (!device) return;
    document.querySelector("#editDeviceId").value = device.device_id;
    document.querySelector("#editName").value = device.name;
    document.querySelector("#editRole").value = device.role;
    modal.classList.add("open");
    document.querySelector("#editName").focus();
  }
  if (disconnect) {
    const response = await fetch(`/api/devices/${encodeURIComponent(disconnect.dataset.id)}/connection`, { method: "DELETE" });
    if (!response.ok) showToast("The camera was already disconnected");
  }
});

document.querySelector("#editForm").addEventListener("submit", async event => {
  event.preventDefault();
  const id = document.querySelector("#editDeviceId").value;
  const response = await fetch(`/api/devices/${encodeURIComponent(id)}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: document.querySelector("#editName").value, role: document.querySelector("#editRole").value }),
  });
  if (response.ok) { modal.classList.remove("open"); showToast("Camera updated"); }
  else showToast("Could not update camera");
});

document.querySelector("#cancelEdit").addEventListener("click", () => modal.classList.remove("open"));
document.querySelector("#copyButton").addEventListener("click", async () => {
  if (!primaryCameraUrl) return showToast("Camera address is not ready yet");
  try { await navigator.clipboard.writeText(primaryCameraUrl); showToast("Camera address copied"); }
  catch { showToast("Select and copy the address manually"); }
});

setInterval(() => { document.querySelector("#clock").textContent = new Date().toLocaleTimeString([], { hour12: false }); }, 250);
connectUmpire();
loadServerInfo();

window.DRSFlushCameras = function () {
  if(socket?.readyState === WebSocket.OPEN) for(const device of devices) socket.send(JSON.stringify({type:'webrtc_signal', device_id:device.device_id, signal:{flush:true}}));
};
