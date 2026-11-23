/* Branding is independent of the scoreboard, camera choice and clean-output mode. */
(function () {
  'use strict';
  const logo = document.getElementById('broadcastLogo');
  if (!logo) return;
  let timer, stopped = false, blank = false, lastSettings = null;
  function render(settings) {
    lastSettings = settings;
    const source = settings.logo || '';
    const valid = /^data:image\/(png|jpeg);base64,/.test(source);
    if (valid && logo.getAttribute('src') !== source) logo.src = source;
    if (!valid) logo.removeAttribute('src');
    logo.hidden = blank || !valid || !settings.visible;
    const width = Number(settings.width_percent), margin = Number(settings.margin_percent);
    logo.style.width = (Number.isFinite(width) ? Math.min(25, Math.max(3, width)) : 8) + 'vw';
    logo.style.top = (Number.isFinite(margin) ? Math.min(10, Math.max(0, margin)) : 2) + 'vh';
    logo.style.right = (Number.isFinite(margin) ? Math.min(10, Math.max(0, margin)) : 2) + 'vw';
  }
  window.addEventListener('message',event=>{const frame=document.getElementById('graphic');if(frame&&event.source===frame.contentWindow&&event.origin===location.origin&&event.data?.type==='broadcast-graphics-status'){blank=event.data.blank===true;if(lastSettings)render(lastSettings);}});
  async function poll() {
    try {
      const response = await fetch('/api/broadcast/branding', {cache: 'no-store', signal: AbortSignal.timeout(3000)});
      if (response.ok && !stopped) render(await response.json());
    } catch { /* Preserve the last received logo during a short network interruption. */ }
    finally { if (!stopped) timer = setTimeout(poll, 2000); }
  }
  window.addEventListener('beforeunload', () => { stopped = true; clearTimeout(timer); });
  poll();
}());
