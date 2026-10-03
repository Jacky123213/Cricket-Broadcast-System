(function(){
 let focused=null;
 function exit(){if(!focused)return;focused.classList.remove('live-focused');document.body.classList.remove('angle-focused');focused=null;}
 window.DRSLiveInspect=article=>{
  const video=article.querySelector('video'),layer=document.createElement('div');layer.className='live-layer';video.replaceWith(layer);layer.append(video);const tools=document.createElement('div');tools.className='angle-toolbar live-view-toolbar';article.append(tools);
  window.DRSViewControls(article,layer,tools,()=>{if(focused===article){exit();return;}exit();focused=article;article.classList.add('live-focused');document.body.classList.add('angle-focused');});
  const close=document.createElement('button');close.className='btn live-exit';close.textContent='Exit fullscreen';close.onclick=exit;tools.append(close);
 };
 document.addEventListener('keydown',e=>{if(e.key==='Escape')exit();});window.addEventListener('drs-review',exit);
})();
