(function(){
 'use strict';
 const $=id=>document.getElementById(id);let manifest=null,lastViews=null,lastDetection=0,working=false;
 const status=t=>$('eventStatus').textContent=t;
 function button(text,fn){const b=document.createElement('button');b.className='btn';b.textContent=text;b.onclick=()=>Promise.resolve(fn()).catch(e=>status(e.message));return b;}
 for(const kind of ['RUN OUT','EDGE','CATCH','STUMPING','GENERAL'])$('reviewButtons').append(button(kind+' REVIEW',async()=>{
  if(working)return;working=true;
  try{
   const before=Number($('windowBefore').value),after=Number($('windowAfter').value);
   if(!Number.isFinite(before)||!Number.isFinite(after)||before<1||before>30||after<0||after>10)throw Error('Before must be 1–30 seconds; after 0–10.');
   const r=await fetch('/api/clock');if(!r.ok)throw Error('Clock unavailable');const now=(await r.json()).sent_ms,end=now+after*1000;
   const deadline=performance.now()+after*1000+12000;
   while(performance.now()<deadline){
    status(kind+' · waiting for post-incident footage…');const r=await fetch('/api/buffer');if(!r.ok)throw Error('Buffer unavailable');const b=await r.json(),c=Object.values(b.cameras).filter(v=>b.server_ms-v.end_ms<15000);
    if(b.server_ms>=end&&c.length&&c.every(v=>v.end_ms>=end))break;
    await new Promise(r=>setTimeout(r,700));
   }
   await window.DRSReplay.openWindow(now-before*1000,end);status(kind+' · manual review');
  }catch(e){status(e.message);}finally{working=false;}
 }));
 fetch('/api/server-info').then(r=>r.json()).then(info=>{info.camera_urls.forEach((url,i)=>{const o=document.createElement('option');o.value=i;o.textContent=url;$('qrAddress').append(o);});}).catch(e=>$('qrNote').textContent=e.message);
 $('qrAddress').onchange=()=>$('cameraQR').src='/api/camera-qr?index='+$('qrAddress').value;
 window.addEventListener('drs-audio',e=>{const entries=Object.entries(e.detail),peak=Math.max(0,...entries.map(([,v])=>v.peak));$('soundMeter').value=peak;$('soundLevel').textContent=entries.length?entries.map(([id,v])=>`${id.slice(0,6)}: ${Math.round(20*Math.log10(Math.max(v.rms,.00001)))} dBFS${v.impact?' · POSSIBLE IMPACT':''}`).join(' | '):'No audio analysis received';});
 function waveform(target){const c=$('waveform'),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);if(!manifest)return;const x=t=>(t-manifest.start_ms)/(manifest.end_ms-manifest.start_ms)*c.width;ctx.strokeStyle='#37dfc0';ctx.beginPath();for(const points of Object.values(manifest.audio||{}))for(const p of points){ctx.moveTo(x(p.t),45-p.peak*42);ctx.lineTo(x(p.t),45+p.peak*42);}ctx.stroke();if(target){ctx.strokeStyle='#ffffff';ctx.beginPath();ctx.moveTo(x(target),0);ctx.lineTo(x(target),90);ctx.stroke();}}
 window.addEventListener('drs-review',e=>{manifest=e.detail;$('timelineMarkers').replaceChildren();if(manifest){const marks=[];for(const pts of Object.values(manifest.audio||{}))for(const p of pts)if(p.impact)marks.push({t:p.t,label:'POSSIBLE IMPACT'});for(const m of marks.sort((a,b)=>a.t-b.t))if(m.t>=manifest.start_ms&&m.t<=manifest.end_ms)$('timelineMarkers').append(button(`${((m.t-manifest.start_ms)/1000).toFixed(2)} s · ${m.label}`,()=>window.DRSReplay.seek(m.t)));}waveform();});
 $('waveform').onclick=e=>{if(manifest){const box=e.currentTarget.getBoundingClientRect();window.DRSReplay.seek(manifest.start_ms+(e.clientX-box.left)/box.width*(manifest.end_ms-manifest.start_ms));}};
 const scratch=document.createElement('canvas');scratch.width=320;scratch.height=180;const ctx=scratch.getContext('2d',{willReadFrequently:true});
 function detect(views){let count=0;for(const v of views.values()){const canvas=v.canvas;canvas.width=320;canvas.height=180;const draw=canvas.getContext('2d');if(!$('detectBall').checked||v.video.hidden||!v.video.videoWidth)continue;try{ctx.drawImage(v.video,0,0,320,180);const hex=$('ballColour').value,colour=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));const candidates=window.DRSBallDetector.detect(ctx.getImageData(0,0,320,180).data,320,180,colour,Number($('ballTolerance').value));draw.strokeStyle='#ffd25c';draw.lineWidth=2;for(const p of candidates){draw.beginPath();draw.arc(p.x,p.y,p.radius+4,0,Math.PI*2);draw.stroke();}count+=candidates.length;}catch(e){$('detectionNote').textContent=e.message;return;}}
 if($('detectBall').checked)$('detectionNote').textContent=`${count} colour candidates across visible angles · experimental 2D only · false positives and missed balls expected`;}
 window.addEventListener('drs-position',e=>{waveform(e.detail.target);lastViews=e.detail.views;if(performance.now()-lastDetection>150){detect(lastViews);lastDetection=performance.now();}});
 for(const id of ['detectBall','ballColour','ballTolerance'])$(id).oninput=()=>{if(lastViews)detect(lastViews);};
})();
