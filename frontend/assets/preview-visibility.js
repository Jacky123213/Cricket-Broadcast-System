/* Suspend only local program previews when their operator page is hidden. */
(() => {
  'use strict';
  let pageActive=true;
  const frames=new Set(),visible=new WeakMap();
  const notify=frame=>frame.contentWindow?.postMessage({type:'cricket-preview-visibility',active:pageActive&&!document.hidden&&visible.get(frame)!==false},location.origin);
  const observer=typeof IntersectionObserver==='function'?new IntersectionObserver(entries=>{for(const entry of entries){visible.set(entry.target,entry.isIntersecting);notify(entry.target);}}):null;
  function scan(){for(const frame of document.querySelectorAll('iframe')){let preview=false;try{const url=new URL(frame.src,location.href);preview=url.origin===location.origin&&url.pathname==='/broadcast'&&url.searchParams.get('client')==='preview';}catch{}if(!preview||frames.has(frame))continue;frames.add(frame);frame.addEventListener('load',()=>notify(frame));observer?.observe(frame);notify(frame);}for(const frame of frames)if(!frame.isConnected){observer?.unobserve(frame);frames.delete(frame);}}
  window.addEventListener('message',event=>{if(window.parent!==window&&event.source===window.parent&&event.origin===location.origin&&event.data?.type==='cricket-page-visibility'){pageActive=event.data.active===true;for(const frame of frames)notify(frame);}});
  document.addEventListener('visibilitychange',()=>{for(const frame of frames)notify(frame);});
  new MutationObserver(scan).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['src']});scan();
})();
