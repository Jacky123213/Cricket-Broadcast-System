(function(){
 'use strict';
 window.DRSViewControls=function(viewport,layer,toolbar,fullscreen){
  let zoom=1,x=0,y=0,gesture=null;const label=document.createElement('label');label.className='view-zoom';label.textContent='Zoom';
  const range=document.createElement('input');range.type='range';range.min=1;range.max=6;range.step=.05;range.value=1;range.setAttribute('aria-label','Inspection zoom');const out=document.createElement('output');out.textContent='1×';label.append(range,out);
  const reset=document.createElement('button');reset.className='btn';reset.textContent='Reset';const expand=document.createElement('button');expand.className='btn';expand.textContent='Fullscreen';
  toolbar.append(label,reset,expand);
  function apply(){const w=viewport.clientWidth,h=viewport.clientHeight;x=Math.max(-w*(zoom-1)/2,Math.min(w*(zoom-1)/2,x));y=Math.max(-h*(zoom-1)/2,Math.min(h*(zoom-1)/2,y));layer.style.transform=`translate(${x}px,${y}px) scale(${zoom})`;range.value=zoom;out.textContent=zoom.toFixed(1)+'×';viewport.classList.toggle('zoomed',zoom>1);}
  function set(z){zoom=Math.max(1,Math.min(6,z));if(zoom===1)x=y=0;apply();}
  range.oninput=()=>set(Number(range.value));reset.onclick=()=>set(1);expand.onclick=fullscreen;
  const distance=t=>Math.hypot(t[0].clientX-t[1].clientX,t[0].clientY-t[1].clientY);
  viewport.addEventListener('touchstart',e=>{if(e.target.closest('button,input,select,label,.focus-audio'))return;if(e.touches.length===2){e.preventDefault();gesture={d:distance(e.touches),z:zoom};}else if(zoom>1){e.preventDefault();gesture={px:e.touches[0].clientX,py:e.touches[0].clientY,x,y};}},{passive:false});
  viewport.addEventListener('touchmove',e=>{if(!gesture)return;if(e.touches.length===2&&gesture.d){e.preventDefault();set(gesture.z*distance(e.touches)/gesture.d);}else if(e.touches.length===1&&gesture.px!==undefined){e.preventDefault();x=gesture.x+e.touches[0].clientX-gesture.px;y=gesture.y+e.touches[0].clientY-gesture.py;apply();}},{passive:false});
  for(const type of ['touchend','touchcancel'])viewport.addEventListener(type,()=>gesture=null);
  viewport.addEventListener('pointerdown',e=>{if(e.target.closest('button,input,select,label,.focus-audio'))return;if(e.pointerType!=='mouse'||zoom===1)return;gesture={px:e.clientX,py:e.clientY,x,y};viewport.setPointerCapture(e.pointerId);});
  viewport.addEventListener('pointermove',e=>{if(e.pointerType==='mouse'&&gesture?.px!==undefined){x=gesture.x+e.clientX-gesture.px;y=gesture.y+e.clientY-gesture.py;apply();}});
  viewport.addEventListener('pointerup',()=>gesture=null);return {reset:()=>set(1)};
 };
})();
