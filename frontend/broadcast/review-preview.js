(function(){'use strict';let closed=false,timer;const status=document.getElementById('previewStatus');
 const player=new window.DRSReviewOutput(document.getElementById('reviewPreview'),{private:true,role:'review_preview',clientId:'review-preview-'+window.DRS.createClientId(),onStatus:text=>status.textContent=text,onGuide:points=>window.parent.postMessage({type:'drs-review-guide',review_id:player.id,points},location.origin)});
 window.CricketReviewPreview={position:()=>{const slot=player.player?.active;return slot&&!slot.video.hidden&&slot.video.readyState>=2?slot.clip.start_ms+slot.video.currentTime*1000-player.manifest.start_ms:null;}};
 async function poll(){if(closed)return;const start=performance.now();try{const r=await fetch('/api/broadcast/program',{cache:'no-store',signal:AbortSignal.timeout(3000)});if(!r.ok)throw Error('Control link unavailable');const data=await r.json();if(closed)return;player.update(data.drs,data.server_ms,(start+performance.now())/2);status.textContent=data.drs?'':'No prepared review';}catch(e){status.textContent=e.message;}finally{if(!closed)timer=setTimeout(poll,500);}}
 window.addEventListener('message',e=>{if(e.source===window.parent&&e.origin===location.origin&&e.data?.type==='draw-review-crease')player.armGuide();});
 window.addEventListener('beforeunload',()=>{closed=true;clearTimeout(timer);player.destroy();});poll();
})();
