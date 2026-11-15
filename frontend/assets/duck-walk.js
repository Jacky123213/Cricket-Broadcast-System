/* User-supplied duck movie, with edge-connected white keyed out at playback.
   White inside the duck's outline is preserved. No microphone/audio is played. */
(function(root){'use strict';
 function removeBackground(data,w,h){const seen=new Uint8Array(w*h),queue=new Int32Array(w*h);let head=0,tail=0;const add=p=>{if(p<0||p>=w*h||seen[p])return;seen[p]=1;const n=p*4;if(Math.min(data[n],data[n+1],data[n+2])>=233)queue[tail++]=p;};for(let x=0;x<w;x++){add(x);add((h-1)*w+x);}for(let y=0;y<h;y++){add(y*w);add(y*w+w-1);}while(head<tail){const p=queue[head++];data[p*4+3]=0;const x=p%w;if(x)add(p-1);if(x<w-1)add(p+1);if(p>=w)add(p-w);if(p<w*(h-1))add(p+w);}return data;}
 const walkX=(width,size,progress)=>width-(width+size)*Math.max(0,Math.min(1,progress));
 if(typeof module!=='undefined')module.exports={removeBackground,walkX};
 if(!root.document)return;
 const canvas=document.createElement('canvas'),video=document.createElement('video'),source=document.createElement('canvas');
 canvas.id='duckWalk';canvas.hidden=true;canvas.setAttribute('aria-label','Duck dismissal animation');canvas.style.cssText='position:fixed;pointer-events:none;z-index:12;';canvas.width=128;canvas.height=128;
 video.muted=true;video.playsInline=true;video.preload='none';video.setAttribute('playsinline','');video.setAttribute('aria-hidden','true');video.style.display='none';
 document.body.append(canvas,video);const ctx=canvas.getContext('2d'),work=source.getContext('2d',{willReadFrequently:true});
 const style=document.createElement('style');style.textContent='body.duck-playing #wicketGraphic{visibility:hidden}';document.head.append(style);
 let enabled=false,seen=new Set(),running=false,generation=0,request=null,lastFrame=0;
 function stop(){generation++;running=false;canvas.hidden=true;document.body.classList.remove('duck-playing');video.pause();if(request!==null)cancelAnimationFrame(request);request=null;}
 function draw(){if(!running)return;request=requestAnimationFrame(draw);if(performance.now()-lastFrame<30||video.readyState<2)return;lastFrame=performance.now();
  const bar=document.getElementById('scorebar');if(!bar||bar.hidden){canvas.hidden=true;return;}
  const w=video.videoWidth,h=video.videoHeight;if(!w||!h)return;source.width=w;source.height=h;work.drawImage(video,0,0,w,h);const frame=work.getImageData(0,0,w,h);removeBackground(frame.data,w,h);work.putImageData(frame,0,0);
  let left=w,right=-1,top=h,bottom=-1;for(let y=0;y<h;y++)for(let x=0;x<w;x++)if(frame.data[(y*w+x)*4+3]){left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}
  ctx.clearRect(0,0,128,128);if(right<left){canvas.hidden=true;return;}const sw=right-left+1,sh=bottom-top+1,scale=Math.min(3,125/sw,125/sh);ctx.save();ctx.translate(128,0);ctx.scale(-1,1);ctx.drawImage(source,left,top,sw,sh,(128-sw*scale)/2,128-sh*scale,sw*scale,sh*scale);ctx.restore();
  const size=Math.max(36,Math.min(130,innerWidth*.07)),progress=(video.currentTime-.2)/9.5,rect=bar.getBoundingClientRect();canvas.style.width=canvas.style.height=size+'px';canvas.style.left=walkX(innerWidth,size,progress)+'px';canvas.style.top=(rect.top-size+2)+'px';canvas.hidden=false;
 }
 async function show(event,now,visible=true){if(!enabled||!visible||!event||seen.has(event.id)||!Number.isFinite(event.at)||now-event.at>20||now<event.at)return;seen.add(event.id);if(seen.size>50)seen=new Set([...seen].slice(-25));stop();const own=generation;video.src='/static/duck-out.mp4';video.currentTime=.2;try{await video.play();if(own!==generation)return;running=true;document.body.classList.add('duck-playing');draw();}catch{canvas.hidden=true;}}
 video.addEventListener('ended',stop);root.addEventListener('beforeunload',stop);
 async function settings(){try{const r=await fetch('/api/live/settings',{cache:'no-store',signal:AbortSignal.timeout(4000)});if(r.ok){enabled=(await r.json()).duck_enabled;if(!enabled)stop();}}catch{/* Last known preference; never block scoring. */}setTimeout(settings,5000);}
 root.CricketDuck={show,stop,removeBackground,walkX};settings();
})(typeof window!=='undefined'?window:globalThis);
