"""Source-only Firefox checks. No personal profile, camera, mic or saved match.

Run with a NEW disposable output folder inside .installer-test. Two black,
silent canvas tracks stand in for inactive virtual cameras. No privileged
browser scope or certificate-verification override is used.
"""
import asyncio
import base64
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.responses import HTMLResponse
import uvicorn
from websockets.sync.client import connect
from server.config import Settings,PROJECT_ROOT
from server.main import create_app
from run import wait_for_server


def check(output):
    output=Path(output).resolve()
    if output.exists(): raise ValueError('Use a new disposable diagnostic folder')
    output.mkdir(parents=True);profile=output/'firefox-profile';profile.mkdir()
    app=create_app(Settings(data_root=output/'data',host='127.0.0.1',ssl_certfile=None,ssl_keyfile=None))
    fixture="""<script>
    const black=document.createElement('canvas');black.width=640;black.height=360;
    black.getContext('2d').fillRect(0,0,640,360);const staticStream=black.captureStream(0);
    staticStream.getVideoTracks()[0].requestFrame?.();
    Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:async c=>{if(c.audio)throw Error('No microphone allowed in this diagnostic');return staticStream;},enumerateDevices:async()=>[{kind:'videoinput',deviceId:'synthetic-black',label:'Synthetic static black camera'}],addEventListener(){}}});
    </script>"""
    @app.get('/diagnostic-camera')
    def camera():
        return HTMLResponse((PROJECT_ROOT/'frontend/camera/index.html').read_text('utf-8').replace('</head>',fixture+'</head>'))

    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=0,log_config=None));thread=threading.Thread(target=server.run,daemon=True)
    process=None;ws=None
    with patch('server.main.start_receiver'):
        thread.start()
        try:
            wait_for_server(server,thread);port=server.servers[0].sockets[0].getsockname()[1]
            with socket.socket() as listener: listener.bind(('127.0.0.1',0));debug_port=listener.getsockname()[1]
            browser=Path(r'C:\Program Files\Mozilla Firefox\firefox.exe')
            process=subprocess.Popen([str(browser),'--headless','--no-remote','--profile',str(profile),'--remote-debugging-port',str(debug_port),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                try: ws=connect(f'ws://127.0.0.1:{debug_port}/session',open_timeout=1,proxy=None,legacy=True);break
                except OSError: time.sleep(.1)
            if not ws: raise RuntimeError('Isolated Firefox did not start')
            sequence=0
            def call(method,params=None):
                nonlocal sequence
                sequence+=1;own=sequence;ws.send(json.dumps({'id':own,'method':method,'params':params or {}}))
                while True:
                    result=json.loads(ws.recv(timeout=15))
                    if result.get('id')!=own: continue
                    if result.get('type')=='error': raise RuntimeError(str(result))
                    return result['result']
            call('session.new',{'capabilities':{}})
            def evaluate(context,expression):
                response=call('script.evaluate',{'target':{'context':context},'expression':expression,'awaitPromise':True})
                if response['type']=='exception': raise RuntimeError(str(response))
                return response.get('result',{}).get('value')
            def wait(context,expression,predicate,seconds=12):
                end=time.monotonic()+seconds;value=None
                while time.monotonic()<end:
                    value=evaluate(context,expression)
                    if predicate(value): return value
                    time.sleep(.1)
                raise AssertionError(f'Firefox timeout: {value}')
            cameras=[]
            for slot in (1,2):
                context=call('browsingContext.create',{'type':'tab'})['context'];cameras.append(context)
                call('browsingContext.navigate',{'context':context,'url':f'http://127.0.0.1:{port}/diagnostic-camera?slot={slot}','wait':'complete'})
                wait(context,'window.__drsCameraReady',bool)
                evaluate(context,"document.getElementById('connectButton').click();true")
                wait(context,"document.querySelector('#connectionPill span:last-child').textContent",lambda s:s=='Camera live')
                # Disable only camera page timers to emulate background timer
                # starvation; incoming network events must maintain the socket.
                evaluate(context,'clearInterval(heartbeatTimer);true')
            idle=call('browsingContext.create',{'type':'tab'})['context'];call('browsingContext.activate',{'context':idle})
            initial=app.state.devices.connected_snapshot();assert len(initial)==2
            seen={d:app.state.devices._devices[d].last_seen_monotonic for d in app.state.devices._devices}
            # More than the former 12-second application heartbeat timeout.
            end=time.monotonic()+17
            while time.monotonic()<end:
                assert len(app.state.devices.connected_snapshot())==2
                time.sleep(.25)
            results=[]
            for context in cameras:
                result=json.loads(evaluate(context,"JSON.stringify({device:deviceId,visibility:document.visibilityState,status:document.querySelector('#connectionPill span:last-child').textContent,audio:previewStream.getAudioTracks().length,direct:previewStream===staticStream,codec:rollingRecorder.mime,recorder:document.getElementById('recordingStatus').textContent})"))
                assert result['status']=='Camera live' and result['audio']==0 and result['direct']
                assert result['visibility']=='hidden' and 'opus' not in result['codec']
                clips=[c for c in app.state.replay_store.clips.values() if c['device_id']==result['device']]
                assert len(clips)>=3,f'No actual replay uploads: {result}'
                assert max(c['end_ms'] for c in clips)>time.time()*1000-7000
                assert all(not c['audio'] and c['bytes']>0 for c in clips)
                result['uploaded_clips']=len(clips);results.append(result)
            assert all(d.last_seen_monotonic>seen[d.device_id]+10 for d in app.state.devices._devices.values())
            call('browsingContext.activate',{'context':cameras[0]})
            # Exercise the native CSS transition with a real video frame.
            evaluate(cameras[0],"new Promise((resolve,reject)=>{const s=document.createElement('script');s.src='/broadcast-assets/program-transition.js';s.onload=()=>resolve(true);s.onerror=reject;document.head.append(s)})")
            evaluate(cameras[0],"(()=>{const stage=document.createElement('div');document.body.append(stage);window.nativeTransition=new DRSProgramTransition(stage);return nativeTransition.hold(preview);})()")
            assert evaluate(cameras[0],"nativeTransition.holding") is True
            midpoint=evaluate(cameras[0],"new Promise(resolve=>{nativeTransition.reveal();setTimeout(()=>resolve(Number(getComputedStyle(nativeTransition.canvas).opacity)),80)})")
            assert 0<float(midpoint)<1,midpoint
            wait(cameras[0],'nativeTransition.canvas===null',bool)
            saved={'browser':'Firefox','synthetic_static_silent_cameras':results,'no_timer_heartbeat_seconds':17,'native_fade_mid_opacity':midpoint,'hardware_tested':False}
            (output/'results.json').write_text(json.dumps(saved,indent=2),'utf-8');print(json.dumps(saved,indent=2))
            call('session.end')
        finally:
            if ws: ws.close()
            if process:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill();process.wait(timeout=5)
            server.should_exit=True;thread.join(10)


if __name__=='__main__': check(sys.argv[1])
