/* A receiving-only live camera for the local preview; never a program command. */
(() => {
  'use strict';
  window.DRSDirectPreview = class {
    constructor(id,mount,callbacks){
      this.id=id;this.callbacks=callbacks;this.closed=false;this.socket=null;this.connection=null;this.hasAudio=false;
      this.metrics=new window.DRSProgramHealth.PlaybackHealth();
      this.video=document.createElement('video');this.video.className='program-video';this.video.playsInline=true;this.video.muted=true;this.video.hidden=true;
      this.video.setAttribute('aria-label','Live camera preview with no added delay');mount.append(this.video);
      this.player={slots:[{video:this.video}],active:null};this.consoleId='preview-live-'+window.DRS.createClientId();
      this.connect();
    }
    status(text){if(!this.closed)this.callbacks.onStatus(text);}
    closePeer(){
      const previous=this.connection;this.connection=null;
      if(previous){clearTimeout(previous.timeout);clearTimeout(previous.interrupted);previous.peer.close();}
      if(this.frameCallback!==undefined)this.video.cancelVideoFrameCallback?.(this.frameCallback);
      clearInterval(this.frameTimer);this.video.pause();this.video.srcObject=null;this.player.active=null;this.video.hidden=true;
    }
    retry(connection,message){
      if(this.closed||this.connection!==connection)return;
      this.closePeer();this.status(message+' · retrying');this.callbacks.onBuffering();
      clearTimeout(this.retryTimer);this.retryTimer=setTimeout(()=>{this.retryTimer=null;if(!this.closed&&this.device)this.use(this.device);},1500);
    }
    send(connection,signal){
      if(this.closed||this.connection!==connection||this.socket?.readyState!==WebSocket.OPEN)return;
      this.socket.send(JSON.stringify({type:'webrtc_signal',device_id:this.id,signal:{...signal,session_id:connection.session}}));
    }
    async use(device){
      if(this.closed||this.socket?.readyState!==WebSocket.OPEN)return;
      this.device=device;const revision=JSON.stringify([device.settings?.media_revision||0,Boolean(device.settings?.microphone)]);
      if(this.connection?.revision===revision)return;
      clearTimeout(this.retryTimer);this.retryTimer=null;this.closePeer();this.hasAudio=false;this.status('Connecting live camera…');
      let c;
      try{
        const peer=new RTCPeerConnection({iceServers:[]});
        c={peer,revision,session:window.DRS.createClientId(),stream:new MediaStream(),incoming:[],outgoing:[],sent:false,signals:Promise.resolve()};this.connection=c;
        peer.addTransceiver('video',{direction:'recvonly'});peer.addTransceiver('audio',{direction:'recvonly'});
        peer.addEventListener('track',event=>{
          if(this.closed||this.connection!==c)return;
          for(const track of event.streams?.[0]?.getTracks()||[event.track])if(!c.stream.getTracks().some(t=>t.id===track.id))c.stream.addTrack(track);
          this.hasAudio=c.stream.getAudioTracks().some(t=>t.readyState!=='ended');
          if(this.video.srcObject!==c.stream){this.video.srcObject=c.stream;this.player.active={video:this.video};this.video.hidden=false;this.callbacks.onVideo?.(this.video);this.watchFrames(c);}
          this.resume();
        });
        peer.addEventListener('icecandidate',event=>{if(!event.candidate||this.connection!==c)return;const candidate=event.candidate.toJSON();if(c.sent)this.send(c,{candidate});else c.outgoing.push(candidate);});
        peer.addEventListener('connectionstatechange',()=>{
          if(this.closed||this.connection!==c)return;
          if(peer.connectionState==='connected')clearTimeout(c.interrupted);
          else if(peer.connectionState==='failed')this.retry(c,'Live camera link failed');
          else if(peer.connectionState==='disconnected'){clearTimeout(c.interrupted);c.interrupted=setTimeout(()=>{if(peer.connectionState==='disconnected')this.retry(c,'Live camera link interrupted');},2500);}
        });
        c.timeout=setTimeout(()=>{if(this.connection===c&&!c.showing)this.retry(c,'No live camera picture received');},15000);
        const offer=await peer.createOffer();if(this.closed||this.connection!==c)return;
        await peer.setLocalDescription(offer);if(this.closed||this.connection!==c)return;
        this.send(c,{description:peer.localDescription});c.sent=true;
        for(const candidate of c.outgoing.splice(0))this.send(c,{candidate});
      }catch(error){if(c)this.retry(c,'Could not connect live camera');else this.status('Live camera unavailable: '+error.message);}
    }
    watchFrames(connection){
      let last=-Infinity;
      const frame=()=>{
        if(this.closed||this.connection!==connection)return false;
        if(this.video.readyState>=2&&!this.video.paused){
          connection.showing=true;clearTimeout(connection.timeout);this.metrics.frame(null,this.video);
          this.callbacks.onFrame({at:null,delay:null,audio:this.hasAudio});
        }
        return true;
      };
      if(this.video.requestVideoFrameCallback){const next=()=>{if(frame())this.frameCallback=this.video.requestVideoFrameCallback(next);};this.frameCallback=this.video.requestVideoFrameCallback(next);}
      else this.frameTimer=setInterval(()=>{if(this.video.currentTime>last){last=this.video.currentTime;frame();}},100);
    }
    accept(message){
      const c=this.connection,s=message.signal;
      if(!c||message.device_id!==this.id||!s||s.session_id&&s.session_id!==c.session)return;
      c.signals=c.signals.then(async()=>{
        if(this.closed||this.connection!==c)return;
        if(s.description){if(s.description.type!=='answer'||c.peer.remoteDescription)return;await c.peer.setRemoteDescription(s.description);if(this.connection!==c)return;for(const candidate of c.incoming.splice(0))await c.peer.addIceCandidate(candidate);}
        else if(s.candidate){if(c.peer.remoteDescription)await c.peer.addIceCandidate(s.candidate);else c.incoming.push(s.candidate);}
      }).catch(()=>this.retry(c,'Live camera negotiation failed'));
    }
    connect(){
      if(this.closed)return;
      const socket=new WebSocket(window.DRS.websocketUrl('/ws/umpire')+'?console_id='+encodeURIComponent(this.consoleId));this.socket=socket;
      socket.addEventListener('message',event=>{
        if(this.closed||this.socket!==socket)return;
        try{const m=JSON.parse(event.data);
          if(m.type==='devices'){
            const device=m.devices.find(d=>d.device_id===this.id);
            if(device){this.device=device;if(!this.retryTimer)this.use(device);}
            else{clearTimeout(this.retryTimer);this.retryTimer=null;this.device=null;this.closePeer();this.status('Selected live camera offline');this.callbacks.onBuffering();}
          }else if(m.type==='webrtc_signal')this.accept(m);
          else if(m.type==='webrtc_error'&&m.device_id===this.id)this.retry(this.connection,m.message||'Live camera offline');
        }catch{this.status('Live camera control message unavailable');}
      });
      socket.addEventListener('close',()=>{
        if(this.closed||this.socket!==socket)return;this.socket=null;clearTimeout(this.retryTimer);this.retryTimer=null;this.closePeer();this.status('Live camera link reconnecting…');this.callbacks.onBuffering();this.reconnectTimer=setTimeout(()=>this.connect(),1500);
      });
      socket.addEventListener('error',()=>{if(this.socket===socket)this.status('Cannot reach live camera control link');});
    }
    resume(){this.video.play().catch(()=>this.status('Live preview needs a click to resume'));}
    setMuted(value){this.video.muted=value;}
    healthSnapshot(now){return {...this.metrics.snapshot([],now),delay_seconds:null,available_seconds:null,headroom_seconds:null,target_delay_seconds:0};}
    destroy(){this.closed=true;clearTimeout(this.retryTimer);clearTimeout(this.reconnectTimer);this.closePeer();const socket=this.socket;this.socket=null;socket?.close();this.video.remove();}
  };
})();
