"""Native browser workflows and responsive/theme checks with disposable data."""
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from unittest.mock import patch


def check(output):
    import uvicorn
    from websockets.sync.client import connect
    from server.config import Settings
    from server.main import create_app
    from server.broadcast_graphics import new_innings
    from run import wait_for_server

    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    app=create_app(Settings(data_root=output/'data',ssl_certfile=None,ssl_keyfile=None))
    score=app.state.scoreboard
    score.save(dict(source='manual',team1='Pavilion XI',team2='Creek XI',color1='#35a7df',color2='#00e76c',runs='94',wickets='4',overs='14.1',striker='1',batter1_name='A. Player',batter2_name='B. Player',batter1_runs='14',batter2_runs='24',batter1_balls='12',batter2_balls='26',bowler='C. Bowler',bowler_figures='2–7',bowler_overs='2.1',deliveries='W'))
    score.flush()
    first=new_innings(score.data)
    first.update(runs=94,wickets=4,balls=85,extras=5,tracked_from_start=True,
        batters=[dict(name=('Very long player name for overflow checking' if i==10 else 'Player '+str(i+1)),runs=14 if i==0 else 10-i if i<10 else 0,balls=12+i,active=i in (4,5),dismissal='not out' if i in (4,5) else 'c Fielder b Bowler',shots={},fours=0,sixes=0,dots=3) for i in range(11)],
        bowlers=[dict(name='Bowler '+str(i+1),figures=f'{i}–{12+i*4}',overs='3.0',maidens=0) for i in range(5)],
        samples={str(i*6):i*6 for i in range(15)},
        wicket_events=[dict(number=i+1,runs=(i+1)*12,balls=(i+1)*15,at=time.time()-60) for i in range(4)])
    first['last_wicket']={**copy.deepcopy(first['batters'][0]),'out_number':4}
    score.graphics.innings=[first];score.graphics.previous=copy.deepcopy(score.data)
    app.state.devices.connected_snapshot=lambda:[dict(device_id='camera1',name='Synthetic camera',role='UMPIRE_POV')]
    score.packs.save({'team':dict(team='Pavilion XI',featured='Player 1',players=[dict(name='Player '+str(i+1),role='allrounder' if i<5 else 'bowler',captain=i==0,age='25',matches='12',runs='140',wickets='8',average='28.0',strike_rate='115.2',economy='5.3',best='40*') for i in range(11)]),
                      'details':dict(career_label='ODI CAREER',toss_team='Creek XI',toss_choice='field',coming_title='Pavilion XI v Creek XI',coming_subtitle='Tomorrow · Backyard Oval',sponsor_name='Local Club',sponsor_caption='Supporting backyard cricket')})
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=0,log_config=None))
    thread=threading.Thread(target=server.run,daemon=True)
    edge=Path(os.environ.get('PROGRAMFILES(X86)',r'C:\Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe'
    with patch('server.main.start_receiver'):
        thread.start()
        try:
            wait_for_server(server,thread)
            origin='http://127.0.0.1:'+str(server.servers[0].sockets[0].getsockname()[1])
            profile=Path(tempfile.mkdtemp(prefix='edge-packs-',dir=output))
            process=subprocess.Popen([str(edge),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--no-proxy-server','--disable-extensions','--hide-scrollbars','--autoplay-policy=no-user-gesture-required','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            deadline=time.monotonic()+15
            while not (profile/'DevToolsActivePort').exists() and time.monotonic()<deadline:time.sleep(.1)
            port=(profile/'DevToolsActivePort').read_text().splitlines()[0]
            targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list'))
            socket=connect(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'),open_timeout=5,legacy=True)
            sequence=0

            def call(method,params=None):
                nonlocal sequence
                sequence+=1;own=sequence;socket.send(json.dumps(dict(id=own,method=method,params=params or {})))
                while True:
                    msg=json.loads(socket.recv(timeout=15))
                    if msg.get('method')=='Runtime.exceptionThrown':
                        print('BROWSER ERROR: '+json.dumps(msg['params']['exceptionDetails']),flush=True)
                    if msg.get('id')==own:
                        if 'error' in msg:raise RuntimeError(str(msg['error']))
                        return msg.get('result',{})

            def js(expression):
                result=call('Runtime.evaluate',dict(expression=expression,returnByValue=True,awaitPromise=True))
                if result.get('exceptionDetails'):raise AssertionError(str(result['exceptionDetails']))
                return result.get('result',{}).get('value')

            def wait(expression,seconds=15):
                until=time.monotonic()+seconds
                while time.monotonic()<until:
                    if js('Boolean('+expression+')'):return
                    time.sleep(.1)
                raise AssertionError('Browser wait: '+expression+'; '+str(js("({url:location.href,ready:document.readyState,error:document.getElementById('workspaceError')?.textContent,body:document.body.textContent.slice(0,500),scripts:[...document.scripts].map(s=>s.src)})")))

            def size(width,height):call('Emulation.setDeviceMetricsOverride',dict(width=width,height=height,deviceScaleFactor=1,mobile=False))
            def navigate(path):call('Page.navigate',dict(url=origin+path))
            def shot(name):(output/name).write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['data']))

            call('Page.enable');call('Runtime.enable')
            results=[]
            for route in ['match-day','umpire','scoreboard','match-setup','teams','graphics','highlights','connections','settings','help']:
                size(1440,900);navigate('/'+route)
                if route=='match-day':
                    wait("document.getElementById('programCameraTiles')&&document.getElementById('liveScore').textContent==='4–94'")
                elif route=='umpire':wait("document.querySelector('.section-toggle')")
                else:wait("document.getElementById('workspace')?.querySelector('.panel')&&!document.getElementById('workspaceError').textContent")
                for theme in ['dark','light']:
                    js("window.CricketPreferences.save({theme:"+json.dumps(theme)+"})")
                    for width,height in [(1440,900),(1024,768),(390,844)]:
                        size(width,height);time.sleep(.08)
                        measure=js("({width:innerWidth,scroll:document.documentElement.scrollWidth,theme:document.documentElement.dataset.theme,bg:getComputedStyle(document.body).backgroundColor,nav:document.querySelectorAll('.operator-rail .nav').length})")
                        if measure['scroll']>width+1:
                            shot(route+'-overflow.png')
                            print(js("[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.right>innerWidth+1&&getComputedStyle(e).position!=='fixed'}).slice(0,12).map(e=>({tag:e.tagName,id:e.id,cls:e.className,w:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right,text:e.textContent.slice(0,100)}))"),flush=True)
                        assert measure['scroll']<=width+1,(route,theme,measure)
                        assert measure['nav']==10,(route,measure)
                        assert measure['theme']==theme
                        results.append(dict(route=route,theme=theme,width=width,passed=True))
                        if width==1440:shot(route+'-'+theme+'.png')
                if route=='settings':
                    assert js("document.querySelector('[name=appearance][value=light]').checked")
            size(1440,900);navigate('/scoreboard#corrections')
            wait("document.getElementById('scoreCorrection')?.elements.runs.value==='94'")
            js("document.getElementById('scoreCorrection').elements.runs.value='95'")
            score.save({'wickets':'5','bowler':'Updated on another controller'})
            js("document.getElementById('scoreCorrection').requestSubmit()")
            wait("document.getElementById('workspaceStatus').textContent.includes('saved')")
            assert score.data['runs']=='95' and score.data['wickets']=='5'
            assert score.data['bowler']=='Updated on another controller'
            results.append(dict(scoped_score_save_preserves_concurrent_bluetooth_fields=True))
            navigate('/match-setup')
            wait("document.getElementById('matchRules')")
            js("document.getElementById('matchRules').elements.total_overs.value='25';document.getElementById('matchRules').requestSubmit()")
            wait("document.getElementById('workspaceStatus').textContent.includes('saved')")
            assert score.graphics.config['total_overs']==25
            js("document.querySelector('#matchLineups form input[type=checkbox]').click();document.querySelector('#matchLineups form').requestSubmit()")
            wait("document.querySelector('#matchLineups [data-save-state]').textContent==='Saved'")
            assert len(score.packs.snapshot()['lineups'][0]['players'])==1
            assert len(score.packs.snapshot()['teams'][0]['players'])==11
            results.append(dict(match_rules_and_selected_lineup_saved_without_changing_roster=True))
            navigate('/graphics')
            wait("document.getElementById('packForm')")
            js("document.getElementById('packForm').elements.pack.value='fox_odi';document.getElementById('packForm').requestSubmit()")
            wait("document.getElementById('workspaceStatus').textContent.includes('saved')")
            assert score.graphics.config['pack']=='fox_odi'
            js("document.querySelector('[data-kind=lineup]').click()")
            time.sleep(.3)
            assert score.graphics.active is None
            assert js("document.getElementById('graphicPreview').contentDocument.querySelectorAll('.fox-lineup-row').length")==1
            js("document.getElementById('takeGraphic').click()")
            wait("document.getElementById('workspaceStatus').textContent.includes('requested')")
            assert score.graphics.active['kind']=='lineup'
            assert score.graphics.active['until'] is None
            js("document.getElementById('clearGraphic').click()")
            wait("document.getElementById('workspaceStatus').textContent.includes('cleared')")
            assert score.graphics.active is None
            results.append(dict(private_graphic_preview_then_explicit_take_clear=True))
            navigate('/settings')
            wait("document.getElementById('settingsLiveViews')")
            js("document.querySelector('[name=appearance][value=dark]').click()")
            navigate('/')
            wait("document.querySelectorAll('#desktopRail .nav').length===10")
            wait("document.getElementById('matchDayFrame').contentDocument?.getElementById('programCameraTiles')")
            js("document.querySelector('[data-view=settings]').click()")
            wait("document.getElementById('settingsFrame').contentDocument?.getElementById('settingsLiveViews')")
            js("document.getElementById('settingsFrame').contentDocument.querySelector('[name=appearance][value=light]').click()")
            wait("document.documentElement.dataset.theme==='light'")
            assert js("document.getElementById('matchDayFrame').contentDocument.documentElement.dataset.theme==='light'")
            js("document.getElementById('settingsFrame').contentDocument.getElementById('settingsLiveViews').click()")
            wait("document.getElementById('matchDayFrame').getAttribute('src')==='about:blank'")
            assert js("document.getElementById('localLiveViews').checked") is False
            assert score.data['runs']=='95'
            shot('desktop-light-settings.png')
            results.append(dict(theme_synchronises_across_frames=True,local_previews_off_does_not_stop_server=True))
            (output/'results.json').write_text(json.dumps(results,indent=2),'utf-8')
            print(json.dumps(dict(passed=len(results),output=str(output)),indent=2),flush=True)
        finally:
            if 'socket' in locals():socket.close()
            if 'process' in locals():process.terminate();process.wait(timeout=10)
            server.should_exit=True;thread.join(10)


if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    check(sys.argv[1])
