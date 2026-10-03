(function(){
 'use strict';
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 window.DRSOptics={async create(raw,slider,label){
  const track=raw.getVideoTracks()[0],caps=track.getCapabilities?.()||{};
  let zoom=1,closed=false,timer=null,frameHandle=null,output=raw,source=null,canvas=null,pending=false,wanted=1;
  const native=caps.zoom&&Number.isFinite(caps.zoom.min)&&caps.zoom.max>caps.zoom.min;
  let min=native?caps.zoom.min:1,max=native?caps.zoom.max:4,step=native?(caps.zoom.step||.01):.01;
  let mode=native?'Camera zoom':'Digital zoom';
  if(!native){
   canvas=document.createElement('canvas');
   if(!canvas.captureStream){max=1;mode='Zoom unavailable in this browser';}
   else{
    source=document.createElement('video');source.autoplay=true;source.muted=true;source.playsInline=true;source.setAttribute('playsinline','');source.srcObject=raw;
    // Keep the source attached and playing for mobile browsers. Never mirror it.
    source.style.cssText='position:fixed;width:1px;height:1px;bottom:0;left:0;opacity:.01;pointer-events:none';document.body.append(source);
    try{
     await source.play();
     const settings=track.getSettings();canvas.width=source.videoWidth||settings.width||1280;canvas.height=source.videoHeight||settings.height||720;
     const ctx=canvas.getContext('2d');
     const draw=()=>{if(closed||source.readyState<2)return;const w=source.videoWidth,h=source.videoHeight;if(!w||!h)return;const cw=w/zoom,ch=h/zoom;const scale=Math.min(canvas.width/cw,canvas.height/ch),dw=cw*scale,dh=ch*scale;ctx.fillStyle="black";ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(source,(w-cw)/2,(h-ch)/2,cw,ch,(canvas.width-dw)/2,(canvas.height-dh)/2,dw,dh);};
     draw();const fps=Math.min(30,settings.frameRate||30);output=canvas.captureStream(fps);raw.getAudioTracks().forEach(t=>output.addTrack(t));if(source.requestVideoFrameCallback){let lastDraw=0;const next=now=>{if(closed)return;if(now-lastDraw>=1000/fps-2){draw();lastDraw=now;}frameHandle=source.requestVideoFrameCallback(next);};frameHandle=source.requestVideoFrameCallback(next);}else timer=setInterval(draw,1000/fps);
    }catch(e){source.pause();source.srcObject=null;source.remove();raw.getTracks().forEach(t=>t.stop());throw Error('Digital zoom could not start: '+e.message);}
   }
  }
  zoom=native?(track.getSettings().zoom||min):1;wanted=zoom;
  slider.min=min;slider.max=max;slider.step=step;slider.value=zoom;slider.disabled=max<=min;
  function report(extra=''){label.textContent=mode+' · '+zoom.toFixed(2)+'×'+extra;}
  async function set(value){
   wanted=clamp(Number(value)||min,min,max);
   if(!native){zoom=wanted;slider.value=zoom;report();return;}
   if(pending||closed)return;pending=true;
   try{while(!closed){const next=wanted;const snapped=clamp(min+Math.round((next-min)/step)*step,min,max);await track.applyConstraints({advanced:[{zoom:snapped}]});zoom=track.getSettings().zoom??snapped;slider.value=zoom;report();if(next===wanted)break;}}
   catch(e){slider.value=zoom;report(' · request failed: '+e.message);}finally{pending=false;}
  }
  slider.oninput=()=>set(slider.value);report();
  return {stream:output,set,get value(){return zoom;},close(){closed=true;clearInterval(timer);if(source){if(frameHandle!==null)source.cancelVideoFrameCallback?.(frameHandle);source.pause();source.srcObject=null;source.remove();}output.getTracks().forEach(t=>t.stop());raw.getTracks().forEach(t=>t.stop());slider.disabled=true;slider.oninput=null;}};
 }};
})();
