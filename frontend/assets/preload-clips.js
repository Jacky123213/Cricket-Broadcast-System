/* Complete, cancellable local downloads for finite reviews/highlights only.
   Live broadcast continues using its adaptive rolling 8–10 second buffer. */
(function(root){'use strict';
 class ClipCache {
  constructor(report=()=>{},options={}){this.report=report;this.maxBytes=options.maxBytes||256*1024*1024;this.controller=new AbortController();this.files=new Map();this.bytes=0;this.completed=0;this.ready=false;this.closed=false;}
  async load(clips){
   const unique=[...new Map(clips.map(c=>[c.url,c])).values()];
   if(unique.length>500||unique.reduce((n,c)=>n+(Number(c.bytes)||0),0)>this.maxBytes)throw Error('Review exceeds the 256 MB preload budget. Choose a shorter review.');
   this.total=unique.length;let index=0;
   const progress=()=>{if(!this.closed)this.report({completed:this.completed,total:this.total,bytes:this.bytes});};progress();
   const download=async clip=>{
    const source=new URL(clip.url,location.href);
    if(source.origin!==location.origin||!['http:','https:'].includes(source.protocol))throw Error('Review media must come from this studio.');
    const timer=setTimeout(()=>this.controller.abort(),30000);
    try{
     const r=await fetch(source.href,{cache:'no-store',signal:this.controller.signal});if(!r.ok)throw Error('Clip download failed (HTTP '+r.status+'). Retry the review.');
     const type=r.headers.get('content-type')||clip.mime||'video/mp4',length=Number(r.headers.get('content-length'))||0;
     if(!type.startsWith('video/')||length>12*1024*1024)throw Error('Invalid or oversized review media.');
     let blob;
     if(r.body?.getReader){const reader=r.body.getReader(),parts=[];let size=0;try{while(true){const part=await reader.read();if(part.done)break;size+=part.value.byteLength;this.bytes+=part.value.byteLength;if(size>12*1024*1024||this.bytes>this.maxBytes)throw Error('Review exceeds the preload budget. Choose a shorter review.');parts.push(part.value);progress();}}finally{reader.releaseLock();}blob=new Blob(parts,{type});}
     else{blob=await r.blob();this.bytes+=blob.size;if(blob.size>12*1024*1024||this.bytes>this.maxBytes)throw Error('Review exceeds the preload budget. Choose a shorter review.');}
     if(this.closed||this.controller.signal.aborted)throw new DOMException('Review cancelled','AbortError');
     if(!blob.size||length&&blob.size!==length)throw Error('Clip download was incomplete. Retry the review.');
     this.files.set(clip.url,URL.createObjectURL(blob));this.completed++;progress();
    }finally{clearTimeout(timer);}
   };
   const worker=async()=>{while(!this.closed&&index<unique.length){const clip=unique[index++];await download(clip);}};
   try{await Promise.all([worker(),worker()]);if(this.closed)throw new DOMException('Review cancelled','AbortError');this.ready=true;return clips.map(c=>({...c,url:this.files.get(c.url)}));}
   catch(error){this.destroy();throw error;}
  }
  destroy(){this.closed=true;this.ready=false;this.controller.abort();for(const url of this.files.values())URL.revokeObjectURL(url);this.files.clear();}
 }
 root.DRSClipCache=ClipCache;
 if(typeof module!=='undefined')module.exports=ClipCache;
})(typeof window!=='undefined'?window:globalThis);
