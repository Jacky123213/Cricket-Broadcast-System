"""Real Edge review workflow, with generated video and a disposable local studio."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.request
from unittest.mock import patch


def check(output, follow=False):
    import uvicorn
    from fastapi.responses import HTMLResponse
    from websockets.sync.client import connect
    from server.config import Settings
    from server.main import create_app
    from server.replay import now_ms
    from run import wait_for_server

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = create_app(Settings(data_root=output/'data', ssl_certfile=None, ssl_keyfile=None))
    app.state.scoreboard.save(dict(source='manual', team1='Backyard XI', team2='Visitors', color1='#e63b7a',
                                   color2='#ff9900', runs='42', wickets='2', overs='6.0'))
    app.state.devices.connected_snapshot = lambda:[dict(device_id=id,name=name,role=role) for id,name,role in
        [('wide','Wide camera','UMPIRE_POV'),('crease','Crease camera','CREASE_LEFT')]]

    @app.get('/diagnostic-drs')
    def diagnostic():
        return HTMLResponse('<!doctype html><body style="margin:0;background:#000;display:flex;gap:20px">'
            f'<iframe id="desk" src="{"/umpire" if follow else "/match-day"}" width="900" height="1080" style="border:0"></iframe>'
            '<iframe id="obs" src="/broadcast?follow=1&clean=1&client=obs&audio=0" width="960" height="540" style="border:0"></iframe>')

    fixture_task = None

    @app.get('/diagnostic-capture')
    async def diagnostic_capture():
        nonlocal fixture_task
        import asyncio
        async def capture():
            while not server.should_exit:
                seed()
                await asyncio.sleep(1.5)
        if fixture_task is None:
            fixture_task = asyncio.create_task(capture())
        return {'ok':True}

    server = uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=0,log_config=None))
    thread = threading.Thread(target=server.run,daemon=True)
    edge = Path(os.environ.get('PROGRAMFILES(X86)',r'C:\Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe'
    with patch('server.main.start_receiver'):
        thread.start()
        try:
            wait_for_server(server,thread)
            origin = 'http://127.0.0.1:'+str(server.servers[0].sockets[0].getsockname()[1])
            profile = Path(tempfile.mkdtemp(prefix='edge-review-',dir=output))
            process = subprocess.Popen([str(edge),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
                '--disable-background-networking','--no-proxy-server','--disable-extensions','--hide-scrollbars',
                '--autoplay-policy=no-user-gesture-required','--remote-debugging-address=127.0.0.1',
                '--remote-debugging-port=0',f'--user-data-dir={profile}','about:blank'],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            deadline = time.monotonic()+15
            while not (profile/'DevToolsActivePort').exists() and time.monotonic()<deadline:
                time.sleep(.1)
            debug = (profile/'DevToolsActivePort').read_text().splitlines()[0]
            targets = json.load(urllib.request.urlopen(f'http://127.0.0.1:{debug}/json/list'))
            socket = connect(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'),open_timeout=5,legacy=True)
            sequence = 0

            def call(method,params=None):
                nonlocal sequence
                sequence+=1
                own=sequence
                socket.send(json.dumps(dict(id=own,method=method,params=params or {})))
                while True:
                    message=json.loads(socket.recv(timeout=15))
                    if message.get('id')==own:
                        if 'error' in message:
                            raise RuntimeError(str(message['error']))
                        return message.get('result',{})

            def js(expression):
                result=call('Runtime.evaluate',dict(expression=expression,returnByValue=True,awaitPromise=True))
                if result.get('exceptionDetails'):
                    raise AssertionError(str(result['exceptionDetails']))
                return result.get('result',{}).get('value')

            def wait(expression,predicate=lambda value:bool(value),seconds=15):
                end=time.monotonic()+seconds
                result=None
                while time.monotonic()<end:
                    result=js(expression)
                    if predicate(result):
                        return result
                    time.sleep(.1)
                details=js("({desk:document.getElementById('desk')?.contentDocument.getElementById('drsError')?.textContent,ready:document.getElementById('desk')?.contentDocument.getElementById('drsReady')?.textContent,source:document.getElementById('desk')?.contentDocument.getElementById('shareReviewStatus')?.textContent,presentation:document.getElementById('desk')?.contentWindow.DRSReplay?.presentation(),obs:document.getElementById('obs')?.contentDocument.querySelector('.drs-processing')?.textContent})")
                snapshot=app.state.broadcast_desk.review.snapshot()
                if snapshot:
                    snapshot={key:snapshot.get(key) for key in ('id','phase','follow_status','follow_sequence','primary','secondary','position_ms','outputs')}
                raise AssertionError(f'Review browser check timed out: {expression}; {result}; details={details}; server_review={snapshot}')

            call('Page.enable')
            call('Emulation.setDeviceMetricsOverride',dict(width=1900,height=1100,deviceScaleFactor=1,mobile=False))
            call('Page.navigate',dict(url=origin+'/api/health'))
            time.sleep(.3)
            # Two short VP8 clips generated by the diagnostic browser, not user media.
            media=js("""(async()=>{return await Promise.all([0,1,2].map(async index=>{const c=document.createElement('canvas');c.width=640;c.height=360;const g=c.getContext('2d'),stream=c.captureStream(20),recorder=new MediaRecorder(stream,{mimeType:'video/webm;codecs=vp8'}),chunks=[];let frame=0;const draw=()=>{g.fillStyle=['#355266','#235b46','#69443a'][index];g.fillRect(0,0,640,360);g.fillStyle='#a88f62';g.fillRect(220,35,200,295);g.strokeStyle='#fff';g.lineWidth=3;g.beginPath();g.moveTo(190,280);g.lineTo(450,280);g.stroke();g.fillStyle='#f0d045';g.beginPath();g.arc(245+frame%140,245,8,0,7);g.fill();g.fillStyle='#fff';g.font='20px sans-serif';g.fillText(['WIDE CAMERA','CREASE CAMERA','REVERSE CAMERA'][index],20,30);g.fillText('SYNTHETIC TEST FOOTAGE',20,345);frame++;};draw();const timer=setInterval(draw,50);recorder.ondataavailable=e=>chunks.push(e.data);const done=new Promise(resolve=>recorder.onstop=resolve);recorder.start();await new Promise(r=>setTimeout(r,3100));recorder.stop();await done;clearInterval(timer);stream.getTracks().forEach(t=>t.stop());const bytes=new Uint8Array(await new Blob(chunks).arrayBuffer());let binary='';for(const b of bytes)binary+=String.fromCharCode(b);return btoa(binary);}));})()""")
            raw=[base64.b64decode(item) for item in media]

            seed_count=0
            def seed():
                nonlocal seed_count
                seed_count+=1
                base=now_ms()-(9000 if follow else 12000)
                for index,camera in enumerate(('wide','crease','reverse') if follow else ('wide','crease')):
                    for part in range(3):
                        key=f'{100+seed_count*100+index*10+part:032x}'
                        (app.state.replay_store.root/(key+'.clip')).write_bytes(raw[index])
                        app.state.replay_store.clips[key]=dict(id=key,device_id=camera,start_ms=base+part*2000,
                            end_ms=base+part*2000+3100,mime='video/webm',bytes=len(raw[index]),audio=False,
                            fps=20,uncertainty_ms=2,offset_ms=0,url='/api/clips/'+key)
                app.state.replay_store.audio={camera:[dict(t=base+n*100,peak=.1 if n%11 else .8,rms=.05,impact=n%11==0) for n in range(71)] for camera in ('wide','crease','reverse')}
                return dict(start=base,end=base+6500)

            desk="document.getElementById('desk').contentDocument"
            obs="document.getElementById('obs').contentDocument"
            window=seed()
            if follow:
                urllib.request.urlopen(origin+'/diagnostic-capture').read()
            call('Page.navigate',dict(url=origin+'/diagnostic-drs'))
            if follow:
                results=check_follow(call,js,wait,app,output,window)
                (output/'results.json').write_text(json.dumps(results,indent=2),'utf-8')
                print(json.dumps(results,indent=2),flush=True)
                return
            wait(f"{desk}.getElementById('drsPrepare')?.disabled",lambda value:value is False)
            # Force a slow media response so the loading/readiness gate is observable.
            call('Network.enable')
            results=[]
            before=app.state.scoreboard.snapshot()['score']
            for kind in ('caught_behind','run_out','lbw'):
                seed()
                js(f"{desk}.getElementById('drsReview').scrollIntoView();{desk}.getElementById('drsKind').value='{kind}';{desk}.getElementById('drsCamera1').value='wide';{desk}.getElementById('drsCamera2').value='crease';{desk}.getElementById('drsPrepare').click()")
                wait(f"{desk}.getElementById('drsStatus').textContent.includes('PRIVATE')")
                assert app.state.broadcast_desk.program['mode']=='live'
                assert js(f"{obs}.getElementById('drsAnnouncement').hidden") is True
                wait(f"{desk}.getElementById('drsTake').disabled",lambda value:value is False,seconds=25)
                js(f"{desk}.getElementById('drsAnnounce').click()")
                wait(f"{obs}.getElementById('graphic').contentDocument.getElementById('bannerText').textContent==='DECISION REVIEWED'")
                assert app.state.broadcast_desk.program['mode']=='live'
                js(f"{desk}.getElementById('drsTake').click()")
                wait(f"{obs}.querySelector('.drs-surface')?.dataset.visible==='true'")
                assert js(f"{obs}.getElementById('graphic').hidden") is True
                assert js(f"{obs}.getElementById('replayBadge').hidden") is True
                wait(f"[...{obs}.querySelectorAll('.drs-angle video')].filter(v=>!v.hidden&&v.videoWidth===640).length>=2")
                js(f"window.reviewDownloads={obs}.defaultView.performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/clips/')).length")
                if kind=='caught_behind':
                    js(f"{desk}.getElementById('drsSpeed').value='1';{desk}.getElementById('drsSpeed').dispatchEvent(new Event('change',{{bubbles:true}}))")
                    wait(f"{desk}.getElementById('drsSpeed').value==='1'")
                    time.sleep(.25)
                    js(f"{desk}.getElementById('drsPlay').click()")
                    wait(f"parseFloat({desk}.getElementById('drsPosition').value)>7500",seconds=12)
                    js(f"{desk}.getElementById('drsPause').click()")
                    assert js(f"{obs}.defaultView.performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/clips/')).length===window.reviewDownloads")
                elif kind=='run_out':
                    js(f"{desk}.getElementById('drsMarkWicket').click()")
                    wait(f"{desk}.getElementById('drsMarker').textContent.includes('manually marked')")
                    # Actual source-page pointer events go through the private preview's message validation.
                    js(f"{desk}.getElementById('drsDrawCrease').click()")
                    time.sleep(.25)
                    js(f"(()=>{{const w={desk}.getElementById('drsPreview').contentWindow,v=w.document.querySelector('.drs-angle[data-primary=true] .drs-crop'),r=v.getBoundingClientRect(),video=v.querySelector('video:not([hidden])'),fit=w.DRSPlayback.fit(video.videoWidth,video.videoHeight,r.width,r.height);for(const x of [.3,.7])v.dispatchEvent(new w.MouseEvent('click',{{bubbles:true,clientX:r.left+fit.x+fit.width*x,clientY:r.top+fit.y+fit.height*.7}}));}})()")
                    wait(f"{obs}.querySelector('.drs-guide line')!==null")
                else:
                    js(f"{desk}.getElementById('drsPitching').value='outside_off';{desk}.getElementById('drsImpact').value='in_line';{desk}.getElementById('drsWickets').value='missing';{desk}.getElementById('drsApplyLbw').click()")
                    wait(f"{obs}.querySelector('.drs-lbw').textContent.includes('MISSING')")
                    assert js(f"{obs}.querySelector('.drs-decision').hidden") is True
                time.sleep(.2)
                shot=call('Page.captureScreenshot',dict(format='png',clip=dict(x=920,y=0,width=960,height=540,scale=1)))
                (output/(kind+'.png')).write_bytes(base64.b64decode(shot['data']))
                js(f"{desk}.querySelector('[data-drs-verdict=not_out]').click()")
                wait(f"{obs}.querySelector('.drs-decision')?.hidden===false")
                position=app.state.broadcast_desk.snapshot()['program']['position_ms']
                time.sleep(.4)
                assert app.state.broadcast_desk.snapshot()['program']['position_ms']==position
                shot=call('Page.captureScreenshot',dict(format='png',clip=dict(x=920,y=0,width=960,height=540,scale=1)))
                (output/(kind+'-decision.png')).write_bytes(base64.b64decode(shot['data']))
                js(f"{desk}.getElementById('drsEnd').click()")
                wait(f"{desk}.getElementById('drsWorking').hidden")
                wait(f"!{obs}.getElementById('graphic').hidden")
                assert app.state.broadcast_desk.program['mode']=='live'
                assert app.state.scoreboard.snapshot()['score']==before
                results.append(dict(kind=kind,private_did_not_take_air=True,obs_ready_before_take=True,
                    all_media_preloaded=True,manual_decision_held=True,score_unchanged=True,return_live=True))
                print('Passed '+kind,flush=True)
            call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
            call('Page.navigate',dict(url=origin+'/match-day#drsReview'))
            wait("document.getElementById('drsPrepare')?.disabled",lambda value:value is False)
            assert js('document.documentElement.scrollWidth<=innerWidth')
            (output/'mobile-controls.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['data']))
            results.append(dict(mobile_width=390,no_document_overflow=True))
            (output/'results.json').write_text(json.dumps(results,indent=2),'utf-8')
            print(json.dumps(results,indent=2),flush=True)
        finally:
            if 'socket' in locals():
                socket.close()
            if 'process' in locals():
                process.terminate()
                process.wait(timeout=10)
            server.should_exit=True
            thread.join(10)


def check_follow(call,js,wait,app,output,window):
    """Use the actual /umpire controls, not a synthetic stream of follow commands."""
    desk="document.getElementById('desk').contentDocument"
    source="document.getElementById('desk').contentWindow"
    obs="document.getElementById('obs').contentDocument"
    program="document.getElementById('obs').contentWindow"
    results=[]
    before=app.state.scoreboard.snapshot()['score']
    wait(f"!!{source}.DRSReplay")
    js(f"{source}.DRSReplay.openWindow({window['start']},{window['end']})")
    wait(f"{desk}.getElementById('replayState').textContent==='PAUSED'&&!{desk}.getElementById('replayPlay').disabled")

    def assign(slot,id):
        js(f"{desk}.getElementById('{slot}Empty').click();{desk}.getElementById('pickerCamera').value='{id}';{desk}.getElementById('pickerApply').click()")
    assign('preview','wide');assign('program','crease')
    wait(f"{source}.DRSReplay.presentation()?.available")
    wait(f"{desk}.getElementById('shareReviewLink').disabled",lambda value:value is False)
    js(f"{desk}.getElementById('reviewBroadcastControls').open=true;{desk}.getElementById('shareReviewKind').value='lbw';{desk}.getElementById('shareReviewOriginal').value='not_out';{desk}.getElementById('shareReviewLink').click()")
    wait(f"{desk}.getElementById('shareReviewLink').disabled&&{desk}.getElementById('shareReviewTake').disabled===false",seconds=25)
    assert app.state.broadcast_desk.program['mode']=='live'
    js(f"{desk}.getElementById('shareReviewAnnounce').click()")
    wait(f"{obs}.getElementById('graphic').contentDocument.getElementById('bannerText').textContent==='DECISION REVIEWED'")
    assert js(f"{obs}.getElementById('graphic').hidden") is False
    wait(f"{obs}.getElementById('graphic').contentDocument.getElementById('scorebar').hidden",lambda value:value is False)
    js(f"{desk}.getElementById('shareReviewTake').click()")
    wait(f"{obs}.querySelector('.drs-surface')?.dataset.visible==='true'")
    wait(f"{program}.CricketProgram.reviewEvidence()?.primary==='wide'")
    assert js(f"{obs}.querySelector('.drs-review-text').textContent")=='DECISION REVIEWED'
    assert js(f"{obs}.querySelector('.drs-lbw').hidden") is True
    assert js(f"{obs}.querySelector('.drs-wave').hidden") is True
    initial_fetches=js(f"{program}.performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/clips/')).length")
    js(f"{desk}.getElementById('replaySpeed').value='.25';{desk}.getElementById('replaySpeed').dispatchEvent(new Event('change'));{desk}.getElementById('replayPlay').click()")
    wait(f"{program}.CricketProgram.reviewEvidence()?.speed===0.25&&{program}.CricketProgram.reviewEvidence()?.playing")
    time.sleep(.4)
    js(f"{desk}.getElementById('replayPause').click();{desk}.getElementById('replayPosition').value=4200;{desk}.getElementById('replayPosition').dispatchEvent(new Event('input'))")
    wait(f"!{program}.CricketProgram.reviewEvidence()?.playing&&Math.abs({program}.CricketProgram.reviewEvidence()?.position_ms-{source}.DRSReplay.presentation()?.position_ms)<120")
    js(f"(()=>{{const d={desk},r=d.querySelector('#previewSlot .view-zoom input');r.value=3;r.dispatchEvent(new Event('input'));}})()")
    wait(f"{program}.CricketProgram.reviewEvidence()?.zoom.wide.zoom===3")
    pos=js(f"(()=>{{const r={desk}.querySelector('#previewSlot .angle-viewport').getBoundingClientRect();return{{x:r.left+r.width*.5,y:r.top+r.height*.5}}}})()")
    call('Input.dispatchMouseEvent',dict(type='mousePressed',x=pos['x'],y=pos['y'],button='left',clickCount=1))
    call('Input.dispatchMouseEvent',dict(type='mouseMoved',x=pos['x']+45,y=pos['y']+12,button='left',buttons=1))
    call('Input.dispatchMouseEvent',dict(type='mouseReleased',x=pos['x']+45,y=pos['y']+12,button='left',clickCount=1))
    wait(f"Math.abs({program}.CricketProgram.reviewEvidence()?.zoom.wide.x-{source}.DRSReplay.presentation()?.zoom.wide.x)<0.01&&{source}.DRSReplay.presentation()?.zoom.wide.x<.49")
    results.append(dict(source_pause_seek_speed_zoom_pan_mirrored=True,announcement_score_strip=True,private_not_auto_on_air=True))
    # Keep native fullscreen from covering both diagnostic iframes. Exercise the
    # real CSS focused view, as when Safari declines the Fullscreen API request.
    js(f"{desk}.getElementById('replayPanel').requestFullscreen=()=>Promise.reject(Error('Diagnostic embedded view'));[...{desk}.querySelectorAll('#programSlot button')].find(b=>b.textContent==='Fullscreen').click()")
    wait(f"{program}.CricketProgram.reviewEvidence()?.primary==='crease'&&{program}.CricketProgram.reviewEvidence()?.secondary===null")
    js(f"{desk}.getElementById('shareReviewWaveform').checked=true;{desk}.getElementById('shareReviewWaveform').dispatchEvent(new Event('change'))")
    wait(f"!{obs}.querySelector('.drs-wave').hidden")
    shot=call('Page.captureScreenshot',dict(format='png',clip=dict(x=920,y=0,width=960,height=540,scale=1)))
    (output/'follow-audio.png').write_bytes(base64.b64decode(shot['data']))
    js(f"{desk}.getElementById('shareReviewAssessment').checked=true;{desk}.getElementById('shareReviewAssessment').dispatchEvent(new Event('change'));{desk}.getElementById('sharePitching').value='outside_off';{desk}.getElementById('shareImpact').value='in_line';{desk}.getElementById('shareWickets').value='missing';{desk}.getElementById('shareApplyLbw').click()")
    wait(f"!{obs}.querySelector('.drs-lbw').hidden&&{obs}.querySelector('.drs-lbw').textContent.includes('MISSING')")
    js(f"{desk}.getElementById('shareReviewWaveform').checked=false;{desk}.getElementById('shareReviewWaveform').dispatchEvent(new Event('change'))")
    wait(f"{obs}.querySelector('.drs-wave').hidden")
    shot=call('Page.captureScreenshot',dict(format='png',clip=dict(x=920,y=0,width=960,height=540,scale=1)))
    (output/'follow-lbw.png').write_bytes(base64.b64decode(shot['data']))
    js(f"{desk}.getElementById('exitFocus').click();{desk}.querySelector('#previewSlot .change-camera').click();{desk}.getElementById('pickerCamera').value='reverse';{desk}.getElementById('pickerApply').click()")
    wait(f"{program}.CricketProgram.reviewEvidence()?.primary==='reverse'&&{program}.CricketProgram.reviewEvidence()?.secondary==='crease'")
    assert js(f"{obs}.querySelectorAll('.drs-angle:not([hidden])').length")==2
    assert js(f"{program}.performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/clips/')).length")==initial_fetches
    shot=call('Page.captureScreenshot',dict(format='png',clip=dict(x=920,y=0,width=960,height=540,scale=1)))
    (output/'follow-split.png').write_bytes(base64.b64decode(shot['data']))
    results.append(dict(fullscreen_camera_switch_mirrored=True,third_camera_already_preloaded=True,manual_lbw_only=True,audio_opt_in=True,no_stinger=True))
    js("document.getElementById('desk').width='390';document.getElementById('desk').height='844'")
    wait(f"{source}.innerWidth===390&&{program}.CricketProgram.reviewEvidence()?.primary==='reverse'&&{program}.CricketProgram.reviewEvidence()?.secondary===null")
    assert js(f"{desk}.documentElement.scrollWidth<={source}.innerWidth")
    js(f"{desk}.querySelector('[data-pane=program]').click()")
    wait(f"{program}.CricketProgram.reviewEvidence()?.primary==='crease'&&{program}.CricketProgram.reviewEvidence()?.secondary===null")
    js("document.getElementById('desk').width='900';document.getElementById('desk').height='1080'")
    wait(f"{program}.CricketProgram.reviewEvidence()?.primary==='reverse'&&{program}.CricketProgram.reviewEvidence()?.secondary==='crease'")
    results.append(dict(mobile_selected_view_follows=True,mobile_width=390,no_document_overflow=True))
    js(f"{source}.__originalFollowFetch={source}.fetch.bind({source});{source}.fetch=(url,options)=>String(url).endsWith('/review/follow')?Promise.reject(Error('Diagnostic dropped controller link')):{source}.__originalFollowFetch(url,options)")
    wait(f"{program}.CricketProgram.reviewEvidence()?.follow_status==='controller_lost'",seconds=8)
    frozen=app.state.broadcast_desk.snapshot()['program']['position_ms']
    time.sleep(.5)
    assert app.state.broadcast_desk.snapshot()['program']['position_ms']==frozen
    js(f"{source}.fetch={source}.__originalFollowFetch")
    wait(f"{program}.CricketProgram.reviewEvidence()?.follow_status==='ready'")
    results.append(dict(controller_loss_pauses_on_last_frame=True,controller_recovers=True))
    js(f"{desk}.querySelector('[data-share-verdict=not_out]').click()")
    wait(f"!{obs}.querySelector('.drs-decision').hidden")
    js(f"{desk}.getElementById('returnLive').click()")
    wait(f"{desk}.getElementById('replayPanel').hidden")
    wait(f"!{obs}.getElementById('graphic').hidden")
    assert app.state.broadcast_desk.review.session is None
    assert app.state.broadcast_desk.program['mode']=='live'
    assert app.state.scoreboard.snapshot()['score']==before
    results.append(dict(returning_umpire_live_ends_public_review=True,score_unchanged=True))
    return results


if __name__=='__main__':
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    check(sys.argv[1],follow='--follow' in sys.argv[2:])
