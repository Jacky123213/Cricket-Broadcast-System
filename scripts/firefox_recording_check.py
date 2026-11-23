"""Record synthetic static/moving video in an isolated, hidden Firefox profile."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import threading


PAGE = r'''<!doctype html><meta charset="utf-8"><body><script src="/recording.js"></script><script>
const results=[];const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function check(label,timing,moving){
 const canvas=document.createElement('canvas');canvas.width=1280;canvas.height=720;document.body.append(canvas);const ctx=canvas.getContext('2d');let n=0;
 const paint=()=>{ctx.fillStyle=moving&&n++%2?'#aabbcc':'#112233';ctx.fillRect(0,0,1280,720);};paint();
 const timer=moving?setInterval(paint,33):null,source=canvas.captureStream(30),owner=new DRSRecorder('synthetic',source,()=>{});
 if(timing)await owner.videoTimingTrack();const stream=owner.stream,audio=stream.getAudioTracks().length>0;
 const mime=['video/mp4',audio?'video/webm;codecs=vp8,opus':'video/webm;codecs=vp8','video/webm'].find(t=>MediaRecorder.isTypeSupported(t));
 const chunks=[],recorder=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:3300000});recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
 await new Promise((resolve,reject)=>{recorder.onstop=resolve;recorder.onerror=e=>reject(Error('Recorder error'));recorder.start();setTimeout(()=>recorder.stop(),3000);setTimeout(()=>reject(Error('Recorder did not stop')),6500);});
 clearInterval(timer);const blob=new Blob(chunks,{type:mime}),video=document.createElement('video');video.muted=true;document.body.append(video);const url=URL.createObjectURL(blob);video.src=url;let failure=null;try{await Promise.race([video.play(),sleep(2000).then(()=>{throw Error('Playback did not start');})]);}catch(e){failure=e.message;}
 let maximum=0;for(let i=0;i<45;i++){await sleep(100);maximum=Math.max(maximum,video.currentTime);if(video.ended||video.error)break;}
 const row={label,mime,bytes:blob.size,timingTrack:!!owner.timing,sourceAudio:source.getAudioTracks().length,recordedAudio:stream.getAudioTracks().length,duration:String(video.duration),maximum,ended:video.ended,readyState:video.readyState,error:video.error?.code||failure||null};
 results.push(row);video.pause();video.removeAttribute('src');video.load();video.remove();URL.revokeObjectURL(url);owner.closeTimingTrack();source.getTracks().forEach(t=>t.stop());canvas.remove();
}
(async()=>{try{await check('static without clock',false,false);await check('static with clock',true,false);await check('moving without clock',false,true);await fetch('/result',{method:'POST',body:JSON.stringify({userAgent:navigator.userAgent,results})});}catch(e){await fetch('/result',{method:'POST',body:JSON.stringify({error:e.message,results})});}})();
</script>'''


def check(output):
    root=Path(__file__).resolve().parents[1];output=Path(output).resolve()
    if root not in output.parents:raise ValueError('Use a test folder inside the installer workspace')
    output.mkdir(parents=True,exist_ok=True);profile=output/'firefox-profile';profile.mkdir()
    (profile/'user.js').write_text('user_pref("media.autoplay.default",0);\nuser_pref("media.autoplay.block-webaudio",false);\nuser_pref("browser.shell.checkDefaultBrowser",false);\nuser_pref("network.proxy.type",0);\nuser_pref("datareporting.policy.dataSubmissionEnabled",false);\n','utf-8')
    event=threading.Event();result={}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            content=(root/'frontend/assets/recording.js').read_bytes() if self.path=='/recording.js' else PAGE.encode()
            self.send_response(200);self.send_header('Content-Type','application/javascript; charset=utf-8' if self.path=='/recording.js' else 'text/html; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        def do_POST(self):
            result.update(json.loads(self.rfile.read(int(self.headers['Content-Length']))));self.send_response(200);self.end_headers();event.set()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    process=subprocess.Popen([r'C:\Program Files\Mozilla Firefox\firefox.exe','--headless','--no-remote','--profile',str(profile),f'http://127.0.0.1:{server.server_port}/'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        if not event.wait(55):raise RuntimeError('Firefox synthetic recording test timed out')
        (output/'result.json').write_text(json.dumps(result,indent=2),'utf-8');print(json.dumps(result,indent=2),flush=True)
        if 'error' in result:raise AssertionError(result['error'])
        clock=result['results'][1]
        assert clock['timingTrack'] and clock['sourceAudio']==0 and clock['maximum']>=2.5 and not clock['error'],clock
    finally:
        process.terminate();process.wait(timeout=10);server.shutdown();server.server_close()


if __name__=='__main__':check(sys.argv[1])
