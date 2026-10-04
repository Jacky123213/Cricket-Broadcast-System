// Synthetic video for the opt-in local preview. No physical camera/mic access.
(() => {
  const canvas = document.createElement('canvas');
  canvas.width = 1280; canvas.height = 720;
  const ctx = canvas.getContext('2d');
  const name = new URLSearchParams(location.search).get('name') || 'DRS test camera';
  function draw() {
    ctx.fillStyle = '#1a4939'; ctx.fillRect(0, 0, 1280, 720);
    ctx.fillStyle = '#245943';
    for (let x = 0; x < 1280; x += 160) ctx.fillRect(x, 0, 80, 720);
    ctx.fillStyle = '#cfb989'; ctx.fillRect(490, 160, 300, 560);
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 4;
    for (const y of [260, 520]) { ctx.beginPath(); ctx.moveTo(420, y); ctx.lineTo(860, y); ctx.stroke(); }
    ctx.fillStyle = '#fff';
    for (const x of [621, 638, 655]) ctx.fillRect(x, 230, 8, 70);
    ctx.fillStyle = '#101e20'; ctx.fillRect(0, 0, 1280, 140);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 40px Arial'; ctx.fillText(name.toUpperCase(), 46, 62);
    ctx.font = '24px Arial'; ctx.fillText('Synthetic verification feed · production DRS camera code', 46, 108);
    ctx.fillStyle = '#fff574'; ctx.beginPath();
    ctx.arc(420 + (performance.now() / 12 % 440), 440, 18, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.font = '24px Arial'; ctx.fillText(new Date().toLocaleTimeString(), 1060, 65);
  }
  draw();
  const timer = setInterval(draw, 1000 / 30);
  const stream = canvas.captureStream(30);
  const contexts = [];
  async function microphone() {
    const context = new AudioContext();
    contexts.push(context);
    await context.resume();
    const tone = context.createOscillator(), gain = context.createGain();
    const output = context.createMediaStreamDestination();
    tone.frequency.value = 440; gain.gain.value = 0.1;
    tone.connect(gain); gain.connect(output); tone.start();
    return output.stream;
  }
  Object.defineProperty(navigator, 'mediaDevices', {configurable: true, value: {
    getUserMedia: async constraints => {
      if (constraints.video === false) return microphone();
      if (constraints.audio) {
        const audio = await microphone();
        audio.getAudioTracks().forEach(track => stream.addTrack(track));
      }
      return stream;
    },
    enumerateDevices: async () => [{kind:'videoinput',deviceId:'synthetic',label:'Synthetic verification camera'}],
    addEventListener() {},
  }});
  localStorage.setItem('drs_device_id', crypto.randomUUID());
  localStorage.setItem('drs_camera_name', name);
  localStorage.setItem('drs_camera_role', 'UMPIRE_POV');
  window.addEventListener('beforeunload', () => { clearInterval(timer); stream.getTracks().forEach(track => track.stop()); contexts.forEach(context => context.close()); });
})();
