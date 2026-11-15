/* Hold only the last real decoded frame while the next camera warms up.
   The hold is bounded and never reported as fresh camera footage. */
(function(root){'use strict';
 class ProgramTransition {
  constructor(stage,onTimeout=()=>{}){this.stage=stage;this.onTimeout=onTimeout;this.canvas=null;this.generation=0;this.holding=false;this.fading=false;}
  hold(video){
   if(video&&!video.hidden&&video.readyState>=2&&video.videoWidth&&video.videoHeight){
    const canvas=document.createElement('canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;canvas.className='program-hold';canvas.setAttribute('aria-label','Previous camera picture held while switching');
    try{canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);this.canvas?.remove();this.canvas=canvas;this.stage.append(canvas);}catch{/* A protected/unavailable frame cannot be invented. */}
   }
   if(!this.canvas)return false;
   this.generation++;clearTimeout(this.deadline);clearTimeout(this.fadeTimer);this.holding=true;this.fading=false;this.canvas.style.transition='none';this.canvas.style.opacity='1';
   const generation=this.generation;this.deadline=setTimeout(()=>{if(generation!==this.generation)return;this.clear();this.onTimeout();},8000);return true;
  }
  reveal(){
   if(!this.canvas||this.fading)return;this.fading=true;clearTimeout(this.deadline);const generation=this.generation;
   this.canvas.getBoundingClientRect();this.canvas.style.transition='opacity 180ms linear';this.canvas.style.opacity='0';
   this.fadeTimer=setTimeout(()=>{if(generation===this.generation)this.clear();},200);
  }
  clear(){this.generation++;clearTimeout(this.deadline);clearTimeout(this.fadeTimer);this.canvas?.remove();this.canvas=null;this.holding=false;this.fading=false;}
 }
 root.DRSProgramTransition=ProgramTransition;
})(typeof window!=='undefined'?window:globalThis);
