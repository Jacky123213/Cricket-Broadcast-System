/* Audio features use digital full scale, never calibrated acoustic dB SPL. */
(function(){
 'use strict';
 window.DRSAudioStart=async function(stream,id,clock,status,onMicrophone=()=>{}){
  // Construct/resume directly in the tap handler, before any permission await.
  const Audio=window.AudioContext||window.webkitAudioContext;
  if(!Audio)throw Error('Web Audio unavailable in this browser');
  const context=new Audio();let owned=null,source,analyser,silent;
  try{
   let timeout;
   try{await Promise.race([context.resume(),new Promise((_,reject)=>{timeout=setTimeout(()=>reject(Error('Audio is suspended. Keep page visible and tap again.')),5000);})]);}finally{clearTimeout(timeout);}
   if(context.state!=='running')throw Error('Audio is suspended. Tap Enable audio analysis again.');
   if(!stream?.getAudioTracks().some(t=>t.readyState==='live')){
    if(!navigator.mediaDevices?.getUserMedia)throw Error('Microphone requires trusted HTTPS');
    status('Allow microphone access when the browser asks…');
    owned=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false},video:false});
    stream=owned;
    // A camera that adopts this mic owns its lifetime; stopping analysis must
    // not silence its live broadcast or replay recording.
    if(await onMicrophone(owned)===true)owned=null;
   }
   source=context.createMediaStreamSource(stream);analyser=context.createAnalyser();
   analyser.fftSize=2048;source.connect(analyser);
   // Keep the processing graph connected without playing microphone feedback.
   silent=context.createGain();silent.gain.value=0;analyser.connect(silent);silent.connect(context.destination);
  }catch(e){owned?.getTracks().forEach(t=>t.stop());await context.close();throw e;}
  const samples=new Float32Array(analyser.fftSize);let points=[],pending=false,baseline=.015,lastImpact=0,uploadError="";
  const timer=setInterval(()=>{
   if(context.state!=='running'){status('Audio '+context.state+' — keep screen awake and tap Enable audio analysis to restart');return;}
   if(!stream.getAudioTracks().some(t=>t.readyState==='live'&&!t.muted)){status('Microphone track muted or ended — check permission and restart analysis');return;}
   analyser.getFloatTimeDomainData(samples);let sum=0,peak=0;
   for(const x of samples){sum+=x*x;peak=Math.max(peak,Math.abs(x));}
   const rms=Math.sqrt(sum/samples.length),t=clock()?.fresh()?clock().now():null;
   const impact=peak>.18&&rms>baseline*3&&performance.now()-lastImpact>300;
   if(impact)lastImpact=performance.now();baseline=baseline*.95+rms*.05;
   status(`${(20*Math.log10(Math.max(rms,.00001))).toFixed(0)} dBFS${impact?' · POSSIBLE IMPACT':''}${t===null?' · LOCAL TEST ONLY: connect and wait for clock sync':''}${uploadError?' · '+uploadError:''}`);
   if(t!==null)points.push({t,rms:Math.min(1,rms),peak:Math.min(1,peak),impact});
   if(points.length>100)points.shift();
  },40);
  const upload=setInterval(async()=>{
   if(pending||!points.length)return;pending=true;const batch=points;points=[];
   const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000);
   try{const r=await fetch('/api/audio/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({points:batch}),signal:controller.signal});if(!r.ok)throw Error('Audio upload '+r.status);uploadError='';}
   catch(e){uploadError=e.message;status(e.message);}finally{pending=false;clearTimeout(timeout);}
  },1000);
  return ()=>{clearInterval(timer);clearInterval(upload);source.disconnect();analyser.disconnect();silent.disconnect();owned?.getTracks().forEach(t=>t.stop());context.close();};
 };
})();
