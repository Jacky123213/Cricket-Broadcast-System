/* Bounded rolling downloads: native decoders receive complete local files. */
(function(root){
  'use strict';
  class LiveClipCache{
    constructor(changed=()=>{},failed=()=>{}){this.changed=changed;this.failed=failed;this.files=new Map();this.pending=new Map();this.retry=new Map();this.desired=[];this.protected=new Set();this.bytes=0;this.closed=false;this.lastLoadMs=null;}
    update(clips,now,target,protectedUrls=[]){
      this.protected=new Set(protectedUrls);
      this.desired=clips.filter(c=>c.url&&c.end_ms>=now-14000&&c.start_ms<=now+1000).sort((a,b)=>{
        const priority=c=>c.start_ms<=target&&target<c.end_ms?0:c.start_ms>target?1:2;
        return priority(a)-priority(b)||a.start_ms-b.start_ms;
      }).slice(0,16);
      const keep=new Set([...this.desired.map(c=>c.url),...this.protected]);
      for(const [url,file]of this.files)if(!keep.has(url)){URL.revokeObjectURL(file.blobUrl);this.bytes-=file.bytes;this.files.delete(url);}
      for(const [url,job]of this.pending)if(!keep.has(url))job.controller.abort();
      for(const url of this.retry.keys())if(!keep.has(url))this.retry.delete(url);
      this.pump();
    }
    ready(clips){return clips.filter(c=>this.files.has(c.url)).map(c=>({...c,source_url:c.url,url:this.files.get(c.url).blobUrl}));}
    pump(){if(this.closed)return;for(const c of this.desired){if(this.pending.size>=2)break;if(this.files.has(c.url)||this.pending.has(c.url)||(this.retry.get(c.url)||0)>Date.now())continue;this.download(c);}}
    download(clip){const controller=new AbortController(),started=performance.now(),job={controller};this.pending.set(clip.url,job);
      const timer=setTimeout(()=>controller.abort(),8000);
      job.promise=(async()=>{
        const url=new URL(clip.url,location.href);if(url.origin!==location.origin||!['http:','https:'].includes(url.protocol))throw Error('Clip must come from this Studio');
        const response=await fetch(url.href,{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error('Clip HTTP '+response.status);
        const type=response.headers.get('content-type')||clip.mime||'video/webm',length=Number(response.headers.get('content-length'))||0;
        if(!type.startsWith('video/')||length>12*1024*1024)throw Error('Invalid clip size/type');
        const blob=await response.blob();if(this.closed||controller.signal.aborted)return;
        if(!blob.size||blob.size>12*1024*1024||length&&length!==blob.size)throw Error('Incomplete clip file');
        if(this.bytes+blob.size>48*1024*1024)throw Error('Live clip cache is full');
        this.files.set(clip.url,{blobUrl:URL.createObjectURL(blob),bytes:blob.size});this.bytes+=blob.size;this.lastLoadMs=performance.now()-started;
      })().catch(error=>{if(!this.closed&&!controller.signal.aborted){this.retry.set(clip.url,Date.now()+2000);this.failed(error);}else if(!this.closed&&this.desired.some(c=>c.url===clip.url)){this.retry.set(clip.url,Date.now()+2000);this.failed(Error('Clip download timed out'));}})
      .finally(()=>{clearTimeout(timer);this.pending.delete(clip.url);if(!this.closed){this.changed();this.pump();}});
    }
    destroy(){this.closed=true;for(const job of this.pending.values())job.controller.abort();for(const f of this.files.values())URL.revokeObjectURL(f.blobUrl);this.files.clear();this.retry.clear();this.bytes=0;}
  }
  root.DRSLiveClipCache=LiveClipCache;
  if(typeof module!=='undefined')module.exports=LiveClipCache;
})(typeof window!=='undefined'?window:globalThis);
