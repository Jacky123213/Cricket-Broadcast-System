"""Native browser checks using only a synthetic match and the bundled duck video."""
import json
import shutil
import time
from pathlib import Path


def seed(app):
    from server.app_paths import RESOURCE_ROOT
    state=app.state.scoreboard
    state.save({'source':'manual','team1':'Blue XI','team2':'Red XI','color1':'#0055ff','color2':'#ef3479',
                'runs':'0','wickets':'0','overs':'0.0','batter1_name':'Duck batter','batter1_runs':'0','batter1_balls':'0','bowler':'Dee','striker':'1'})
    state.graphics.flush(time.time(),force=True)
    state.save({'wickets':'1','overs':'0.1','deliveries':'W','last_wicket_name':'Duck batter','last_wicket_runs':'0',
                'last_wicket_balls':'1','last_wicket_code':'b','last_wicket_bowler':'Dee'})
    state.graphics.flush(time.time(),force=True)
    live=app.state.live_match;live.save_settings({'clips_enabled':True,'stream_enabled':False,'duck_enabled':True})
    data=live.state();event=data['innings'][0]['deliveries'][0]['id'];key='f'*32
    folder=live.root/'media';folder.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(RESOURCE_ROOT/'frontend'/'assets'/'duck-out.mp4',folder/(key+'.clip'))
    live.highlights=[{'id':'native-test-clip','event_id':event,'match_id':data['match_id'],'innings':0,'title':'Synthetic wicket replay',
                      'kind':'wicket','ball':'0.1','partial':True,'start_ms':-2000,'end_ms':9500,
                      'clips':[{'id':key,'start_ms':0,'end_ms':10000,'device_id':'synthetic','mime':'video/mp4','url':'/api/live/media/'+key}]}]


def wait(window,script,predicate,timeout=15):
    deadline=time.monotonic()+timeout
    value=None
    while time.monotonic()<deadline:
        value=window.evaluate_js(script)
        if predicate(value): return value
        time.sleep(.1)
    raise AssertionError(f'Native live-page check timed out: {value}')


def check_live(window,origin,app):
    seed(app)
    window.load_url(origin+'/live')
    initial=wait(window,"({batter:document.querySelector('#panel-scorecard td.name')?.textContent,zeroes:[...document.querySelectorAll('#panel-scorecard table:first-of-type td')].map(e=>e.textContent),highlight:!!document.querySelector('#panel-scorecard button'),background:getComputedStyle(document.body).backgroundColor})",lambda v:v and v.get('batter')=='Duck batter')
    assert initial['highlight'] and initial['background']=='rgb(13, 17, 15)'
    window.evaluate_js("document.querySelector('[data-tab=balls]').click()")
    assert window.evaluate_js("document.querySelectorAll('#panel-balls button').length")==1
    window.evaluate_js("document.querySelector('[data-tab=graphs]').click()")
    assert window.evaluate_js("document.querySelectorAll('#graph svg').length")==1
    window.evaluate_js("document.querySelector('[data-graph=manhattan]').click()")
    assert window.evaluate_js("document.querySelectorAll('#graph rect').length")>=1
    window.evaluate_js("document.querySelector('[data-tab=summary]').click()")
    assert 'Match information' in window.evaluate_js("document.getElementById('panel-summary').textContent")
    window.evaluate_js("window.mediaCheck={};fetch('/api/live/media/'+'f'.repeat(32)).then(async r=>window.mediaCheck={status:r.status,type:r.headers.get('content-type'),bytes:(await r.arrayBuffer()).byteLength});window.mediaEvents=[];['loadstart','loadedmetadata','loadeddata','error','stalled','suspend','abort','emptied'].forEach(e=>document.addEventListener(e,x=>{if(x.target.tagName==='VIDEO')window.mediaEvents.push([e,x.target.readyState,x.target.error?.message]);},true))")
    window.evaluate_js("document.querySelector('[data-tab=highlights]').click();document.querySelector('.highlight-card button').click()")
    manifest=wait(window,"({open:!!document.getElementById('clipDialog')?.open,src:document.querySelector('#clipStage video')?.getAttribute('src'),network:window.mediaCheck})",lambda v:v and v.get('open') and v.get('src') and v.get('network',{}).get('bytes')==82954)
    window.evaluate_js("document.getElementById('closeClip').click()")
    app.state.live_match.save_settings({'stream_enabled':True})
    wait(window,"document.getElementById('streamSection')?.hidden",lambda v:v is False)
    window.evaluate_js("document.getElementById('watchStream').click()")
    assert 'follow=1' in window.evaluate_js("document.querySelector('#streamStage iframe').src")
    app.state.live_match.save_settings({'stream_enabled':False,'clips_enabled':False})
    wait(window,"({noStream:!document.querySelector('#streamStage iframe'),hidden:document.getElementById('highlightsTab')?.hidden})",lambda v:v and v.get('noStream') and v.get('hidden'))
    return {'live_tabs':True,'highlight_manifest_and_bytes':manifest,'stream_toggle':True,'clips_toggle':True,
            'app_palette':initial['background'],'media_limit':'Hidden WebView2 defers media; decoded playback is checked separately in headless Edge.'}


def capture_headless(output):
    """Real decoder/render QA in an isolated, non-user Edge profile."""
    import os
    import subprocess
    import sys
    import tempfile
    import threading
    import uvicorn
    import urllib.request
    from websockets.sync.client import connect
    from fastapi.responses import HTMLResponse
    from unittest.mock import patch
    from server.config import Settings
    from server.main import create_app
    from run import wait_for_server
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    edge=Path(os.environ.get('PROGRAMFILES(X86)',r'C:\Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe'
    app=create_app(Settings(data_root=output/'data',ssl_certfile=None,ssl_keyfile=None))
    seed(app)
    script=r"""<script>
const f=document.getElementById('stage'),mode=new URLSearchParams(location.search).get('mode');let started=false,first=null,playing=false,processing=false,missing=0,downloads=0,lateDownloads=0;const seen=new Set();
const poll=setInterval(()=>{try{const w=f.contentWindow,d=f.contentDocument;if(mode==='duck'){
 const c=d.getElementById('duckWalk');if(!c||c.hidden)return;const r=c.getBoundingClientRect(),bar=d.getElementById('scorebar').getBoundingClientRect();
 if(first===null){first=r.x;return;}if(r.x<w.innerWidth*.65&&r.x<first-2){document.body.dataset.result=JSON.stringify({duck:true,x:r.x,first,bottom:r.bottom,scoreTop:bar.top});clearInterval(poll);}
}else if(mode==='drs'){
 if(!w.DRSReplay)return;
 if(!started){started=true;const original=w.fetch.bind(w);w.fetch=(url,options)=>{if(String(url).includes('/api/clips/')){downloads++;if(playing)lateDownloads++;}return original(url,options);};w.DRSReplay.openWindow(window.reviewWindow.start,window.reviewWindow.end);}
 if(!d.getElementById('replayProcessing').hidden)processing=true;
 if(!playing&&d.getElementById('replayState').textContent==='PAUSED'&&!d.getElementById('replayPlay').disabled){for(const [slot,id]of [['preview','native-one'],['program','native-two']]){d.getElementById(slot+'Empty').click();d.getElementById('pickerCamera').value=id;d.getElementById('pickerApply').click();}d.getElementById('replayPlay').click();playing=true;}
 if(playing){const v=[...d.querySelectorAll('#previewSlot video')].find(v=>!v.hidden&&v.style.zIndex==='1');if(!v||v.readyState<2)missing++;else seen.add(v.currentSrc);if(seen.size===3&&v.currentTime>1.25){document.body.dataset.result=JSON.stringify({drs:true,processing,downloads,lateDownloads,missingFrames:missing,partsSeen:seen.size});clearInterval(poll);w.DRSReplay.pause();}}
}else{if(!w.CricketLive||!d.querySelector('#panel-scorecard td'))return;if(mode==='page'){document.body.dataset.result=JSON.stringify({page:true,width:w.innerWidth,overflow:d.documentElement.scrollWidth>w.innerWidth});clearInterval(poll);return;}
 if(!started){started=true;const original=w.fetch.bind(w);w.fetch=(url,options)=>{if(String(url).includes('/api/live/media/')){downloads++;if(playing)lateDownloads++;}return original(url,options);};d.querySelector('[data-tab=highlights]').click();d.querySelector('.highlight-card button').click();}
 if(!d.getElementById('clipLoading').hidden)processing=true;
 const ready=d.getElementById('clipDialog').getAttribute('aria-busy')==='false';if(ready&&!d.getElementById('clipPlay').disabled)playing=true;
 const v=[...d.querySelectorAll('#clipStage video')].find(v=>!v.hidden&&v.style.zIndex==='1');if(playing){if(!v||v.readyState<2)missing++;else seen.add(v.currentSrc);}if(seen.size===3&&v?.videoWidth&&v.currentTime>1.25){document.body.dataset.result=JSON.stringify({video:true,width:v.videoWidth,time:v.currentTime,ready:v.readyState,processing,downloads,lateDownloads,missingFrames:missing,partsSeen:seen.size});clearInterval(poll);v.pause();}
}}catch(e){document.body.dataset.error=e.message;}},50);</script>"""

    @app.get('/diagnostic-live')
    def fixture(mode:str='page',width:int=1280,height:int=720):
        page='/overlay' if mode=='duck' else '/umpire' if mode=='drs' else '/live'
        return HTMLResponse(f'<!doctype html><html><body style="margin:0"><iframe id="stage" style="display:block;border:0" width="{width}" height="{height}" src="{page}"></iframe><script>window.reviewWindow={json.dumps(review_window)};</script>{script}</body></html>')

    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=0,log_config=None));thread=threading.Thread(target=server.run,daemon=True)
    with patch('server.main.start_receiver'):
        thread.start()
        try:
            wait_for_server(server,thread);port=server.servers[0].sockets[0].getsockname()[1]
            # Three independent synthetic MP4 parts, with real local media
            # responses. Validate both handovers, not just the first frame.
            from server.app_paths import RESOURCE_ROOT
            from server.replay import now_ms
            source=RESOURCE_ROOT/'frontend/assets/duck-out.mp4';base=now_ms()-12000
            review_window={'start':base,'end':base+6500};archive=[]
            for part in range(3):
                key=f'{part+1:032x}';shutil.copyfile(source,app.state.live_match.root/'media'/(key+'.clip'))
                archive.append({'id':key,'start_ms':part*2000,'end_ms':part*2000+3000,'device_id':'synthetic','mime':'video/mp4','bytes':source.stat().st_size,'url':'/api/live/media/'+key})
                for index,camera in enumerate(('native-one','native-two')):
                    native_key=f'{(part+1)*100+index:032x}';shutil.copyfile(source,app.state.replay_store.root/(native_key+'.clip'))
                    app.state.replay_store.clips[native_key]={'id':native_key,'device_id':camera,'start_ms':base+part*2000,'end_ms':base+part*2000+3000,'mime':'video/mp4','bytes':source.stat().st_size,'audio':False,'fps':30,'uncertainty_ms':0,'offset_ms':0,'url':'/api/clips/'+native_key}
            app.state.live_match.highlights[0].update(clips=archive,start_ms=0,end_ms=6500)
            profile=Path(tempfile.mkdtemp(prefix='edge-live-',dir=output));results=[]
            process=subprocess.Popen([str(edge),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--no-proxy-server','--disable-extensions','--hide-scrollbars','--autoplay-policy=no-user-gesture-required','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            deadline=time.monotonic()+15
            while not (profile/'DevToolsActivePort').exists() and time.monotonic()<deadline: time.sleep(.1)
            debug_port=(profile/'DevToolsActivePort').read_text().splitlines()[0]
            targets=json.load(urllib.request.urlopen('http://127.0.0.1:'+debug_port+'/json/list'))
            socket=connect(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'),open_timeout=5,legacy=True)
            sequence=0;network=[]
            def call(method,params=None):
                nonlocal sequence
                sequence+=1;own=sequence;socket.send(json.dumps({'id':own,'method':method,'params':params or {}}))
                while True:
                    message=json.loads(socket.recv(timeout=10))
                    if message.get('method') in ('Network.loadingFailed','Network.responseReceived'): network.append(message)
                    if message.get('id')==own:
                        if 'error' in message: raise RuntimeError(str(message['error']))
                        return message.get('result',{})
            call('Network.enable');call('Page.enable')
            for mode,width,height in [('video',1280,720),('drs',1280,900),('duck',1920,1080),('page',1280,900),('page',390,844)]:
                app.state.scoreboard.graphics.innings[0]['wicket_events'][0]['at']=time.time()
                path=output/f'{mode}-{width}x{height}.png'
                call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':False})
                call('Page.navigate',{'url':f'http://127.0.0.1:{port}/diagnostic-live?mode={mode}&width={width}&height={height}'})
                deadline=time.monotonic()+18;result=None
                while time.monotonic()<deadline:
                    value=call('Runtime.evaluate',{'expression':'document.body?.dataset.result','returnByValue':True}).get('result',{}).get('value')
                    if value: result=json.loads(value);break
                    time.sleep(.1)
                if not result:
                    details=call('Runtime.evaluate',{'expression':"(()=>{const d=document.getElementById('stage').contentDocument;return {status:d.getElementById('clipStatus')?.textContent,video:[...d.querySelectorAll('video')].map(v=>({src:v.src,ready:v.readyState,time:v.currentTime,error:v.error?.message})),duck:d.getElementById('duckWalk')?.hidden}})()",'returnByValue':True})
                    failures=[m for m in network if m['method']=='Network.loadingFailed']
                    raise AssertionError(f'Headless {mode}: {details}; network failures: {failures}')
                import base64
                path.write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
                results.append(result)
                if mode=='duck': assert abs(result['bottom']-result['scoreTop']-2)<2
                if mode=='page': assert not result['overflow']
                if mode in ('video','drs'):
                    assert result['downloads']==(6 if mode=='drs' else 3) and result['lateDownloads']==0
                    assert result['partsSeen']==3 and result['missingFrames']==0 and result['processing']
                if mode=='duck':
                    app.state.live_match.save_settings({'duck_enabled':False})
                    deadline=time.monotonic()+7
                    while time.monotonic()<deadline:
                        disabled=call('Runtime.evaluate',{'expression':"document.getElementById('stage').contentDocument.getElementById('duckWalk').hidden",'returnByValue':True}).get('result',{}).get('value')
                        if disabled: break
                        time.sleep(.1)
                    assert disabled;result['toggle_off_hides']=True
            (output/'results.json').write_text(json.dumps(results,indent=2),'utf-8')
            print(json.dumps(results,indent=2))
        finally:
            if 'socket' in locals(): socket.close()
            if 'process' in locals(): process.terminate();process.wait(timeout=10)
            server.should_exit=True;thread.join(10)


if __name__=='__main__':
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    capture_headless(sys.argv[1])
