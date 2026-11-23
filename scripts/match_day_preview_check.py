"""Native WebRTC/cached-preview checks using two synthetic camera pages."""
import json
import time


def check_ui(app,output,js,wait,size,navigate,shot):
    results=[]
    size(1440,1000);navigate('/match-day')
    wait("document.getElementById('previewMode')&&window.CricketCameraTiles")
    js("for(let i=1;i<=2;i++){const f=document.createElement('iframe');f.id='syntheticCamera'+i;f.src='/diagnostic-camera?slot='+i+'&name=Synthetic%20'+i;f.style='position:fixed;left:-1500px;width:320px;height:240px';document.body.append(f);}")
    for n in (1,2):
        wait(f"document.getElementById('syntheticCamera{n}').contentWindow?.__drsCameraReady")
        js(f"document.getElementById('syntheticCamera{n}').contentDocument.getElementById('connectButton').click()")
    wait("document.getElementById('programCamera').options.length===2")
    wait("document.getElementById('programPreview').contentWindow?.CricketProgram?.health().state==='playing'",25)
    preview="document.getElementById('programPreview').contentWindow.CricketProgram.health()"
    delayed=js(preview);assert delayed['preview_mode']=='program' and delayed['delay_seconds']>=7,delayed
    before=js("fetch('/api/broadcast/program').then(r=>r.json()).then(d=>d.program)")
    # A real OBS-labelled browser remains separate while the local picker changes.
    js("const obs=document.createElement('iframe');obs.id='diagnosticObs';obs.src='/broadcast?follow=1&clean=1&client=obs&audio=0';obs.style='position:fixed;right:0;bottom:0;width:160px;height:90px';document.body.append(obs)")
    wait("document.getElementById('diagnosticObs').contentWindow?.CricketProgram?.health().state==='playing'",20)
    js("document.getElementById('previewMode').value='live';document.getElementById('previewMode').dispatchEvent(new Event('change'))")
    wait("document.getElementById('programPreview').contentWindow?.CricketProgram?.health().preview_mode==='live_camera'&&document.getElementById('programPreview').contentWindow.CricketProgram.health().state==='playing'",20)
    live=js(preview);after=js("fetch('/api/broadcast/program').then(r=>r.json()).then(d=>d.program)")
    assert live['delay_seconds'] is None and live['target_delay_seconds']==0 and live['muted'],live
    assert (after['revision'],after['camera_id'],after['mode'])==(before['revision'],before['camera_id'],before['mode'])
    obs=js("document.getElementById('diagnosticObs').contentWindow.CricketProgram.health()")
    assert obs['preview_mode']=='program' and obs['delay_seconds']>=7 and obs['state']=='playing',obs
    results.append(dict(real_live_preview_receiving_frames=True,obs_remains_delayed=True,choice_sends_no_program_command=True))
    cameras=app.state.devices.connected_snapshot();assert len(cameras)==2,cameras
    second=next(c['device_id'] for c in cameras if c['device_id']!=after['camera_id'])
    js("document.getElementById('programCamera').value="+json.dumps(second)+";document.getElementById('programCamera').dispatchEvent(new Event('change'))")
    wait("document.getElementById('programPreview').contentWindow.CricketProgram.health().camera_id==="+json.dumps(second)+"&&document.getElementById('programPreview').contentWindow.CricketProgram.health().state==='playing'",15)
    results.append(dict(live_follows_program_camera=True))
    js("document.querySelector('[data-program-replay=\"10\"]').click()")
    wait("document.getElementById('programTransport').hidden===false")
    wait("document.getElementById('programPreview').contentWindow.CricketProgram.health().state==='playing'")
    assert js(preview)['preview_mode']=='live_camera'
    assert js("document.getElementById('programPreview').contentDocument.getElementById('replayBadge').hidden")
    results.append(dict(live_view_continues_during_on_air_replay=True))
    js("document.getElementById('previewMode').value='delayed';document.getElementById('previewMode').dispatchEvent(new Event('change'))")
    wait("document.getElementById('programPreview').contentWindow?.CricketProgram?.health().mode==='replay'&&document.getElementById('programPreview').contentWindow.CricketProgram.health().preview_mode==='program'")
    results.append(dict(delayed_preview_follows_on_air_replay=True))
    js("document.getElementById('returnProgramLive').click();document.getElementById('previewMode').value='live';document.getElementById('previewMode').dispatchEvent(new Event('change'))")
    wait("document.getElementById('programPreview').contentWindow?.CricketProgram?.health().state==='playing'",15)
    for theme in ['dark','light']:
        js('CricketPreferences.save({theme:'+json.dumps(theme)+'})')
        for width,height in [(1440,1000),(1024,768),(390,844)]:
            size(width,height);time.sleep(.35)
            wait("document.getElementById('programPreview').contentWindow?.CricketProgram?.health().state==='playing'",15)
            picture=js("(()=>{const w=document.getElementById('programPreview').contentWindow,v=w.document.querySelector('#bufferedStage video'),c=w.document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;const x=c.getContext('2d');x.drawImage(v,0,0);return [...x.getImageData(c.width/2,c.height/2,1,1).data];})()")
            assert sum(picture[:3])>80,(theme,width,picture)
            assert js('document.documentElement.scrollWidth<=innerWidth+1')
            assert js("getComputedStyle(document.getElementById('previewMode')).display!=='none'&&!document.getElementById('previewHint').hidden")
            shot('preview-'+theme+'-'+str(width)+'.png')
            results.append(dict(theme=theme,width=width,preview_choice_visible=True,no_horizontal_overflow=True,decoded_picture_center=picture))
    assert js("localStorage.getItem('cricket.match-day.preview.v1')")=='live'
    return results
